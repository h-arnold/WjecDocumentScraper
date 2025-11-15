"""Integration test for LLM categoriser with Gemini model.

This test ensures the categoriser can process documents correctly using the Gemini LLM.
It verifies that:
1. The Gemini model name is valid and compatible with the API
2. The categoriser can handle document filtering
3. The full workflow (load -> batch -> process -> save) works end-to-end

This test uses a mocked Gemini client to avoid real API calls and network dependencies.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from google import genai
from google.genai import types

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.gemini_llm import GeminiLLM
from src.llm.service import LLMService
from src.llm_review.llm_categoriser.runner import CategoriserRunner
from src.llm_review.llm_categoriser.state import CategoriserState


class _MockResponse:
    """Mock response from Gemini API."""
    
    def __init__(self, text: str) -> None:
        self.text = text


class _MockModels:
    """Mock models interface."""
    
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
    
    def generate_content(self, **kwargs: Any) -> _MockResponse:
        """Mock generate_content to capture calls and return valid JSON."""
        self.calls.append(kwargs)
        # Return a mock categorisation response with valid JSON
        # Return the minimal categoriser output (issue_id + LLM fields)
        response_text = json.dumps([{
            "issue_id": 0,
            "error_category": "STYLISTIC_PREFERENCE",
            "confidence_score": 95,
            "reasoning": "Test categorisation"
        }])
        return _MockResponse(text=response_text)


class _MockGeminiClient:
    """Mock Gemini client for testing."""
    
    def __init__(self) -> None:
        self.models = _MockModels()


def test_gemini_model_name_is_valid() -> None:
    """Test that GeminiLLM uses a valid model name."""
    assert GeminiLLM.MODEL == "gemini-2.5-flash"
    # Ensure it's not the old broken name
    assert GeminiLLM.MODEL != "gemini-flash-2.5"


def test_gemini_llm_generates_with_correct_model_param(tmp_path: Path) -> None:
    """Test that GeminiLLM passes the correct model name to the API."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System instruction", encoding="utf-8")
    
    client = _MockGeminiClient()
    llm = GeminiLLM(
        system_prompt=system_prompt_path,
        client=cast(genai.Client, client),
    )
    
    # Generate with the mocked client
    _ = llm.generate(["Test prompt"])
    
    # Verify the correct model name was used
    assert len(client.models.calls) == 1
    call = client.models.calls[0]
    assert call["model"] == "gemini-2.5-flash"
    assert call["model"] == GeminiLLM.MODEL


def test_gemini_llm_has_thinking_config(tmp_path: Path) -> None:
    """Test that Gemini LLM includes extended thinking config."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    
    client = _MockGeminiClient()
    llm = GeminiLLM(
        system_prompt=system_prompt_path,
        client=cast(genai.Client, client),
    )
    
    _ = llm.generate(["Prompt"])
    
    # Verify thinking config is set
    call = client.models.calls[0]
    config = call["config"]
    assert isinstance(config, types.GenerateContentConfig)
    assert config.thinking_config is not None
    assert config.thinking_config.thinking_budget == GeminiLLM.MAX_THINKING_BUDGET


def test_categoriser_runner_with_mocked_gemini(tmp_path: Path) -> None:
    """Test the full categoriser runner workflow with mocked Gemini."""
    # Setup fixture data
    fixture_dir = tmp_path / "Documents"
    art_subject_dir = fixture_dir / "Art-and-Design" / "markdown"
    art_subject_dir.mkdir(parents=True)
    
    # Create a test markdown file with page markers
    test_doc = art_subject_dir / "gcse-art-and-design---guidance-for-teaching.md"
    test_doc.write_text(
        "{1}------------------------------------------------\n"
        "Page 1 content: This is a test document.\n"
        "{2}------------------------------------------------\n"
        "Page 2 content: More test content here.\n"
    )
    
    # Create a language-check-report.csv with test issues
    report_path = tmp_path / "language-check-report.csv"
    report_path.write_text(
        "Subject,Filename,Page,Rule ID,Type,Issue,Message,Suggestions,Highlighted Context\n"
        "Art-and-Design,gcse-art-and-design---guidance-for-teaching.md,1,STYLE_ISSUE,style,word,Test suggestion,correction,\"This is a **word** test\"\n"
        "Art-and-Design,gcse-art-and-design---guidance-for-teaching.md,1,GRAMMAR_ISSUE,grammar,are,Subject-verb agreement,is,\"Students **are** learning\"\n"
    )
    
    # Setup mocked LLM
    system_prompt_file = tmp_path / "system_prompt.md"
    system_prompt_file.write_text("Categorise language issues")
    
    mock_client = _MockGeminiClient()
    gemini_llm = GeminiLLM(
        system_prompt=system_prompt_file,
        client=cast(genai.Client, mock_client),
    )
    
    # Create LLM service
    llm_service = LLMService([gemini_llm])
    
    # Create state in temp directory
    state_path = tmp_path / "llm_categoriser_state.json"
    state = CategoriserState(state_file=state_path)
    
    # Create and run categoriser runner
    runner = CategoriserRunner(
        llm_service=llm_service,
        state=state,
        batch_size=10,
    )
    
    # Change to temp directory for the test
    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = runner.run(report_path, force=True)
    finally:
        os.chdir(original_cwd)
    
    # Verify results
    assert result["total_documents"] == 1
    assert result["total_batches"] == 1
    assert result["total_issues"] == 2
    # The runner should have made at least one call to the mocked LLM
    assert len(mock_client.models.calls) > 0
    # Verify the model name used is correct
    for call in mock_client.models.calls:
        assert call["model"] == "gemini-2.5-flash"


def test_categoriser_runner_dry_run_with_documents_filter(tmp_path: Path) -> None:
    """Test dry-run mode filters documents correctly and doesn't call LLM."""
    # Setup fixture data
    fixture_dir = tmp_path / "Documents"
    
    # Create multiple subject directories
    for subject in ["Art-and-Design", "Business"]:
        subject_dir = fixture_dir / subject / "markdown"
        subject_dir.mkdir(parents=True)
        
        # Create markdown files
        doc_file = subject_dir / f"gcse-{subject.lower()}.md"
        doc_file.write_text(
            "{1}------------------------------------------------\n"
            "Page 1 content\n"
        )
    
    # Create a language-check-report.csv with issues for both subjects
    report_path = tmp_path / "language-check-report.csv"
    report_path.write_text(
        "Subject,Filename,Page,Rule ID,Type,Issue,Message,Suggestions,Highlighted Context\n"
        "Art-and-Design,gcse-art-and-design.md,1,RULE1,style,word,Test,fix,\"test **word**\"\n"
        "Business,gcse-business.md,1,RULE2,grammar,are,Test,fix,\"They **are** here\"\n"
    )
    
    # Setup mocked LLM
    system_prompt_file = tmp_path / "system_prompt.md"
    system_prompt_file.write_text("Categorise")
    
    mock_client = _MockGeminiClient()
    gemini_llm = GeminiLLM(
        system_prompt=system_prompt_file,
        client=cast(genai.Client, mock_client),
    )
    
    llm_service = LLMService([gemini_llm])
    state_path = tmp_path / "llm_categoriser_state.json"
    state = CategoriserState(state_file=state_path)
    
    runner = CategoriserRunner(llm_service=llm_service, state=state)
    
    # Change to temp directory
    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        # Dry run with document filter
        result = runner.run(
            report_path,
            documents={"gcse-art-and-design.md"},
            dry_run=True
        )
    finally:
        os.chdir(original_cwd)
    
    # Verify only the specified document was loaded
    assert result["total_documents"] == 1
    assert result["total_batches"] == 1
    assert result["total_issues"] == 1
    # In dry-run mode, LLM should not be called
    assert len(mock_client.models.calls) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
