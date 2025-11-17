"""Integration tests for CategoriserRunner with rate-limited GeminiLLM."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import cast

import pytest
from google import genai

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.gemini_llm import GeminiLLM
from src.llm.service import LLMService
from src.llm_review.llm_categoriser.runner import CategoriserRunner
from src.llm_review.llm_categoriser.state import CategoriserState
from src.llm_review.llm_categoriser.batcher import Batch
from src.models import DocumentKey, LanguageIssue


class _DummyResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _TrackingModels:
    """Mock models that tracks API call times."""
    
    def __init__(self) -> None:
        self.call_times: list[float] = []
        self.calls: list[dict[str, object]] = []
        self._call_count = 0
    
    def generate_content(self, **kwargs: object) -> _DummyResponse:
        self.call_times.append(time.time())
        self.calls.append(kwargs)
        
        # Return valid JSON response with issue_id matching the call count
        # This ensures we return different issue_ids for different batches
        response_json = f'[{{"issue_id": {self._call_count}, "error_category": "SPELLING_ERROR", "confidence_score": 90, "reasoning": "test"}}]'
        self._call_count += 1
        return _DummyResponse(text=response_json)


class _TrackingClient:
    def __init__(self) -> None:
        self.models = _TrackingModels()


def test_categoriser_runner_respects_gemini_rate_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that CategoriserRunner with GeminiLLM respects GEMINI_MIN_REQUEST_INTERVAL."""
    # Set environment variable
    monkeypatch.setenv("GEMINI_MIN_REQUEST_INTERVAL", "0.2")
    
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")
    
    client = _TrackingClient()
    
    # Create GeminiLLM with rate limiting from environment
    gemini = GeminiLLM(
        system_prompt=system_prompt_path,
        client=cast(genai.Client, client),
    )
    
    service = LLMService([gemini])
    state = CategoriserState(tmp_path / "state.json")
    
    # CategoriserRunner also has rate limiting, but we set it to 0
    # to test that GeminiLLM's rate limiting is working
    runner = CategoriserRunner(
        llm_service=service,
        state=state,
        min_request_interval=0.0,  # Don't use runner's rate limiting
    )
    
    # Create test data
    issues = [
        LanguageIssue(
            filename="test.md",
            rule_id=f"RULE{i}",
            message="msg",
            issue_type="error",
            replacements=[],
            context="ctx",
            highlighted_context="ctx",
            issue="issue",
            page_number=1,
            issue_id=i,
        )
        for i in range(3)
    ]
    
    key = DocumentKey(subject="Test", filename="test.md")
    
    # Process 3 batches
    for i in range(3):
        batch = Batch(
            subject="Test",
            filename="test.md",
            index=i,
            issues=[issues[i]],
            page_context={1: "context"},
            markdown_table="table",
        )
        runner._process_batch(key, batch)
    
    # Verify rate limiting was enforced
    call_times = client.models.call_times
    assert len(call_times) == 3
    
    # Check intervals between consecutive calls
    for i in range(1, len(call_times)):
        interval = call_times[i] - call_times[i-1]
        # Should respect the 0.2s minimum (with some tolerance)
        assert interval >= 0.18, f"Interval {interval} is less than expected 0.2s"


def test_categoriser_runner_double_rate_limiting(tmp_path: Path) -> None:
    """Test that both CategoriserRunner and GeminiLLM rate limiting work together.
    
    Note: Both enforce rate limiting based on the same last_request_time,
    so the delays don't add up - only the maximum of the two is applied.
    """
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")
    
    client = _TrackingClient()
    
    # GeminiLLM with 0.1s rate limit
    gemini = GeminiLLM(
        system_prompt=system_prompt_path,
        client=cast(genai.Client, client),
        min_request_interval=0.1,
    )
    
    service = LLMService([gemini])
    state = CategoriserState(tmp_path / "state.json")
    
    # CategoriserRunner also with 0.1s rate limit
    runner = CategoriserRunner(
        llm_service=service,
        state=state,
        min_request_interval=0.1,
    )
    
    # Create test data
    issues = [
        LanguageIssue(
            filename="test.md",
            rule_id=f"RULE{i}",
            message="msg",
            issue_type="error",
            replacements=[],
            context="ctx",
            highlighted_context="ctx",
            issue="issue",
            page_number=1,
            issue_id=i,
        )
        for i in range(2)
    ]
    
    key = DocumentKey(subject="Test", filename="test.md")
    
    # Process 2 batches
    for i in range(2):
        batch = Batch(
            subject="Test",
            filename="test.md",
            index=i,
            issues=[issues[i]],
            page_context={1: "context"},
            markdown_table="table",
        )
        runner._process_batch(key, batch)
    
    # Both runner and GeminiLLM enforce 0.1s rate limit
    # Since they track the same last_request_time, the delay is 0.1s (not additive)
    call_times = client.models.call_times
    assert len(call_times) == 2
    
    interval = call_times[1] - call_times[0]
    # Should be at least 0.1s (with some tolerance for timing variations)
    assert interval >= 0.09, f"Interval {interval} is less than expected 0.1s"
