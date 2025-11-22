"""Test the append_results method in PersistenceManager."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure project root is importable (consistent with other tests)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm_review.core.persistence import PersistenceManager
from src.llm_review.llm_proofreader.config import ProofreaderConfiguration
from src.models import DocumentKey


@pytest.fixture
def persistence_manager(tmp_path) -> PersistenceManager:
    """Create a PersistenceManager with test configuration."""
    config = ProofreaderConfiguration(
        input_csv_path=tmp_path / "input.csv",
        output_base_dir=tmp_path / "output",
        output_subdir="test_reports",
        batch_size=10,
        max_retries=2,
        state_file=tmp_path / "state.json",
        subjects=None,
        documents=None,
        llm_provider=None,
        fail_on_quota=True,
        log_raw_responses=False,
        log_response_dir=tmp_path / "logs",
        output_csv_columns=[
            "issue_id",
            "page_number",
            "issue",
            "highlighted_context",
            "error_category",
            "confidence_score",
            "reasoning",
        ],
    )
    return PersistenceManager(config)


def test_append_results_assigns_issue_ids_starting_from_zero(
    persistence_manager: PersistenceManager, tmp_path
):
    """Test that append_results assigns issue IDs starting from 0."""
    key = DocumentKey("Subject", "doc.md")

    # First batch of results without issue_id
    new_results = [
        {
            "page_number": 1,
            "issue": "alpha",
            "highlighted_context": "Context with **alpha**.",
            "error_category": "spelling",
            "confidence_score": 90,
            "reasoning": "Detected spelling issue.",
        },
        {
            "page_number": 2,
            "issue": "beta",
            "highlighted_context": "Context with **beta**.",
            "error_category": "grammar",
            "confidence_score": 85,
            "reasoning": "Detected grammar issue.",
        },
    ]

    output_path = persistence_manager.append_results(key, new_results)
    assert output_path.exists()

    # Verify the content
    loaded = persistence_manager.load_document_results(key)
    assert len(loaded) == 2
    assert loaded[0]["issue_id"] == "0"
    assert loaded[0]["issue"] == "alpha"
    assert loaded[1]["issue_id"] == "1"
    assert loaded[1]["issue"] == "beta"


def test_append_results_continues_issue_ids_from_existing(
    persistence_manager: PersistenceManager, tmp_path
):
    """Test that append_results continues issue IDs from existing results."""
    key = DocumentKey("Subject", "doc.md")

    # First batch
    first_results = [
        {
            "page_number": 1,
            "issue": "alpha",
            "highlighted_context": "Context with **alpha**.",
            "error_category": "spelling",
            "confidence_score": 90,
            "reasoning": "Detected spelling issue.",
        },
    ]
    persistence_manager.append_results(key, first_results)

    # Second batch
    second_results = [
        {
            "page_number": 2,
            "issue": "beta",
            "highlighted_context": "Context with **beta**.",
            "error_category": "grammar",
            "confidence_score": 85,
            "reasoning": "Detected grammar issue.",
        },
        {
            "page_number": 3,
            "issue": "gamma",
            "highlighted_context": "Context with **gamma**.",
            "error_category": "spelling",
            "confidence_score": 95,
            "reasoning": "Another spelling issue.",
        },
    ]
    persistence_manager.append_results(key, second_results)

    # Verify all results
    loaded = persistence_manager.load_document_results(key)
    assert len(loaded) == 3
    assert loaded[0]["issue_id"] == "0"
    assert loaded[0]["issue"] == "alpha"
    assert loaded[1]["issue_id"] == "1"
    assert loaded[1]["issue"] == "beta"
    assert loaded[2]["issue_id"] == "2"
    assert loaded[2]["issue"] == "gamma"


def test_append_results_handles_empty_list(
    persistence_manager: PersistenceManager, tmp_path
):
    """Test that append_results handles empty list gracefully."""
    key = DocumentKey("Subject", "doc.md")

    # Append empty list - should return path but not create file
    output_path = persistence_manager.append_results(key, [])
    # File should not be created when there are no rows
    assert not output_path.exists()

    # Verify no results
    loaded = persistence_manager.load_document_results(key)
    assert len(loaded) == 0


def test_append_results_ignores_issue_id_in_input(
    persistence_manager: PersistenceManager, tmp_path
):
    """Test that append_results ignores issue_id if present in input."""
    key = DocumentKey("Subject", "doc.md")

    # Results with incorrect issue_id values (should be overwritten)
    new_results = [
        {
            "issue_id": 999,  # Should be ignored
            "page_number": 1,
            "issue": "alpha",
            "highlighted_context": "Context with **alpha**.",
            "error_category": "spelling",
            "confidence_score": 90,
            "reasoning": "Detected spelling issue.",
        },
    ]

    persistence_manager.append_results(key, new_results)

    # Verify the issue_id was overwritten to 0
    loaded = persistence_manager.load_document_results(key)
    assert len(loaded) == 1
    assert loaded[0]["issue_id"] == "0"
