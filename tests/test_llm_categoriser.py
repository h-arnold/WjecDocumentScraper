"""Tests for the LLM categoriser modules."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.language_check.language_issue import LanguageIssue
from src.llm_review.llm_categoriser.data_loader import load_issues, _parse_csv
from src.llm_review.llm_categoriser.batcher import iter_batches
from src.llm_review.llm_categoriser.state import CategoriserState
from src.llm_review.llm_categoriser.persistence import save_batch_results, load_document_results
from src.models.document_key import DocumentKey


def test_parse_csv(tmp_path: Path) -> None:
    """Test CSV parsing with highlighted context."""
    csv_content = """Subject,Filename,Page,Rule ID,Type,Issue,Message,Suggestions,Highlighted Context
Art,test.md,1,RULE1,error,word,Test message,fix,"This is **word**"
"""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)
    
    issues = list(_parse_csv(csv_file))
    
    assert len(issues) == 1
    subject, issue = issues[0]
    assert subject == "Art"
    assert issue.filename == "test.md"
    assert issue.rule_id == "RULE1"
    assert issue.highlighted_context == "This is **word**"
    assert issue.page_number == 1
    assert issue.issue_id == -1  # Not yet assigned


def test_load_issues_assigns_issue_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that load_issues assigns sequential issue IDs per document."""
    # Change to tmp_path as working directory
    monkeypatch.chdir(tmp_path)
    
    # Create CSV
    csv_content = """Subject,Filename,Page,Rule ID,Type,Issue,Message,Suggestions,Highlighted Context
TestSub,doc1.md,1,RULE1,error,word1,Test,fix1,"context1"
TestSub,doc1.md,2,RULE2,error,word2,Test,fix2,"context2"
TestSub,doc2.md,1,RULE3,error,word3,Test,fix3,"context3"
"""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)
    
    # Create markdown files
    subject_dir = tmp_path / "Documents" / "TestSub" / "markdown"
    subject_dir.mkdir(parents=True)
    (subject_dir / "doc1.md").write_text("{1}----\nPage 1\n{2}----\nPage 2")
    (subject_dir / "doc2.md").write_text("{1}----\nPage 1")
    
    # Load issues
    grouped = load_issues(csv_file)
    
    # Check issue IDs
    key1 = DocumentKey(subject="TestSub", filename="doc1.md")
    key2 = DocumentKey(subject="TestSub", filename="doc2.md")
    
    assert key1 in grouped
    assert key2 in grouped
    
    assert grouped[key1][0].issue_id == 0
    assert grouped[key1][1].issue_id == 1
    assert grouped[key2][0].issue_id == 0


def test_batcher_creates_markdown_table(tmp_path: Path) -> None:
    """Test that batcher creates proper markdown table."""
    # Create test issues
    issues = [
        LanguageIssue(
            filename="test.md",
            rule_id="RULE1",
            message="Test",
            issue_type="error",
            replacements=["fix"],
            context="ctx",
            highlighted_context="**test**",
            issue="test",
            page_number=1,
            issue_id=0,
        )
    ]
    
    # Create markdown file with page markers
    md_file = tmp_path / "test.md"
    md_file.write_text("{1}----\nPage 1 content")
    
    # Generate batches
    batches = list(iter_batches(
        issues,
        batch_size=10,
        markdown_path=md_file,
        subject="Test",
        filename="test.md",
    ))
    
    assert len(batches) == 1
    batch = batches[0]
    
    assert batch.subject == "Test"
    assert batch.filename == "test.md"
    assert batch.index == 0
    assert len(batch.issues) == 1
    assert "| issue_id | page_number | issue | highlighted_context |" in batch.markdown_table
    assert "| 0 | 1 | test | **test** |" in batch.markdown_table


def test_state_tracks_completed_batches(tmp_path: Path) -> None:
    """Test state manager tracks completed batches."""
    state_file = tmp_path / "state.json"
    state = CategoriserState(state_file)
    
    key = DocumentKey(subject="Test", filename="test.md")
    
    # Initially not completed
    assert not state.is_batch_completed(key, 0)
    
    # Mark as completed
    state.mark_batch_completed(key, 0, total_issues=5)
    
    # Should be completed now
    assert state.is_batch_completed(key, 0)
    assert not state.is_batch_completed(key, 1)
    
    # Check count
    assert state.get_completed_count(key) == 1
    
    # Verify state file was created
    assert state_file.exists()
    
    # Load fresh state and verify persistence
    state2 = CategoriserState(state_file)
    assert state2.is_batch_completed(key, 0)


def test_state_clear_document(tmp_path: Path) -> None:
    """Test clearing state for a document."""
    state_file = tmp_path / "state.json"
    state = CategoriserState(state_file)
    
    key = DocumentKey(subject="Test", filename="test.md")
    
    # Mark batch as completed
    state.mark_batch_completed(key, 0)
    assert state.is_batch_completed(key, 0)
    
    # Clear document
    state.clear_document(key)
    assert not state.is_batch_completed(key, 0)


def test_persistence_saves_and_loads(tmp_path: Path) -> None:
    """Test persistence saves and loads results correctly."""
    key = DocumentKey(subject="Test", filename="test.md")
    
    results = {
        "page_1": [
            {
                "rule_from_tool": "RULE1",
                "type_from_tool": "error",
                "message_from_tool": "Test",
                "suggestions_from_tool": ["fix"],
                "context_from_tool": "ctx",
                "error_category": "SPELLING_ERROR",
                "confidence_score": 90,
                "reasoning": "Test reason"
            }
        ]
    }
    
    # Save results
    output_path = save_batch_results(key, results, output_dir=tmp_path)
    
    # Verify file was created
    assert output_path.exists()
    expected_path = tmp_path / "Test" / "document_reports" / "test.json"
    assert output_path == expected_path
    
    # Load and verify
    loaded = load_document_results(key, output_dir=tmp_path)
    assert loaded == results


def test_persistence_merges_results(tmp_path: Path) -> None:
    """Test that persistence merges results from multiple batches."""
    key = DocumentKey(subject="Test", filename="test.md")
    
    # Save first batch
    results1 = {
        "page_1": [{"rule_from_tool": "RULE1", "confidence_score": 90}]
    }
    save_batch_results(key, results1, merge=True, output_dir=tmp_path)
    
    # Save second batch with different page
    results2 = {
        "page_2": [{"rule_from_tool": "RULE2", "confidence_score": 85}]
    }
    save_batch_results(key, results2, merge=True, output_dir=tmp_path)
    
    # Load and verify merged
    loaded = load_document_results(key, output_dir=tmp_path)
    assert "page_1" in loaded
    assert "page_2" in loaded
    assert len(loaded["page_1"]) == 1
    assert len(loaded["page_2"]) == 1


def test_batch_handles_no_page_numbers(tmp_path: Path) -> None:
    """Test batcher handles documents without page numbers."""
    # Create issue without page number
    issues = [
        LanguageIssue(
            filename="test.md",
            rule_id="RULE1",
            message="Test",
            issue_type="error",
            replacements=[],
            context="",
            highlighted_context="test",
            issue="test",
            page_number=None,  # No page number
            issue_id=0,
        )
    ]
    
    # Create markdown file WITHOUT page markers
    md_file = tmp_path / "test.md"
    md_file.write_text("Simple document without page markers")
    
    # Generate batches
    batches = list(iter_batches(
        issues,
        batch_size=10,
        markdown_path=md_file,
        subject="Test",
        filename="test.md",
    ))
    
    assert len(batches) == 1
    batch = batches[0]
    
    # Should use entire document as page 0
    assert 0 in batch.page_context
    assert "Simple document without page markers" in batch.page_context[0]
