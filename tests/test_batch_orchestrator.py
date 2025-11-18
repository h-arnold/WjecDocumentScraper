"""Tests for batch orchestrator functionality."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Sequence
from unittest.mock import MagicMock


# Fix imports to work with pytest
try:
    from src.llm_review.llm_categoriser.batch_orchestrator import (
        BatchJobMetadata,
        BatchJobTracker,
        BatchOrchestrator,
    )
    from src.llm_review.core.state_manager import StateManager
    from src.llm.provider import LLMProvider
    from src.llm.service import LLMService
except ImportError:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from src.llm_review.llm_categoriser.batch_orchestrator import (
        BatchJobMetadata,
        BatchJobTracker,
        BatchOrchestrator,
    )
    from src.llm_review.core.state_manager import StateManager
    from src.llm.provider import LLMProvider
    from src.llm.service import LLMService


class _DummyProvider(LLMProvider):
    """Dummy provider for testing."""
    
    name = "dummy"
    
    def __init__(self) -> None:
        self.created_jobs = []
        self.job_statuses = {}
        self.job_results = {}
    
    def generate(self, user_prompts: Sequence[str], *, filter_json: bool = False) -> Any:
        return []
    
    def batch_generate(self, batch_payload: Sequence[Sequence[str]], *, filter_json: bool = False) -> Sequence[Any]:
        raise NotImplementedError()
    
    def create_batch_job(self, batch_payload: Sequence[Sequence[str]], *, filter_json: bool = False) -> str:
        job_name = f"job-{len(self.created_jobs)}"
        self.created_jobs.append((job_name, batch_payload))
        self.job_statuses[job_name] = MagicMock(done=False, state="PENDING")
        return job_name
    
    def get_batch_job(self, batch_job_name: str) -> Any:
        return self.job_statuses.get(batch_job_name)
    
    def fetch_batch_results(self, batch_job_name: str) -> Sequence[Any]:
        return self.job_results.get(batch_job_name, [])
    
    def health_check(self) -> bool:
        return True


def test_batch_job_tracker_add_and_get(tmp_path: Path) -> None:
    """Test adding and retrieving job metadata."""
    tracking_file = tmp_path / "jobs.json"
    tracker = BatchJobTracker(tracking_file)
    
    metadata = BatchJobMetadata(
        provider_name="dummy",
        job_name="job-123",
        subject="Geography",
        filename="gcse-geography.md",
        batch_index=0,
        issue_ids=[1, 2, 3],
        created_at="2024-01-01T00:00:00Z",
        status="pending",
    )
    
    tracker.add_job(metadata)
    
    # Retrieve the job
    retrieved = tracker.get_job("job-123")
    assert retrieved is not None
    assert retrieved.job_name == "job-123"
    assert retrieved.subject == "Geography"
    assert retrieved.batch_index == 0
    assert retrieved.issue_ids == [1, 2, 3]


def test_batch_job_tracker_update_status(tmp_path: Path) -> None:
    """Test updating job status."""
    tracking_file = tmp_path / "jobs.json"
    tracker = BatchJobTracker(tracking_file)
    
    metadata = BatchJobMetadata(
        provider_name="dummy",
        job_name="job-123",
        subject="Geography",
        filename="gcse-geography.md",
        batch_index=0,
        issue_ids=[1, 2, 3],
        created_at="2024-01-01T00:00:00Z",
        status="pending",
    )
    
    tracker.add_job(metadata)
    tracker.update_job_status("job-123", "completed")
    
    retrieved = tracker.get_job("job-123")
    assert retrieved.status == "completed"


def test_batch_job_tracker_get_pending_jobs(tmp_path: Path) -> None:
    """Test retrieving only pending jobs."""
    tracking_file = tmp_path / "jobs.json"
    tracker = BatchJobTracker(tracking_file)
    
    tracker.add_job(BatchJobMetadata(
        provider_name="dummy",
        job_name="job-1",
        subject="Geography",
        filename="gcse-geography.md",
        batch_index=0,
        issue_ids=[1],
        created_at="2024-01-01T00:00:00Z",
        status="pending",
    ))
    
    tracker.add_job(BatchJobMetadata(
        provider_name="dummy",
        job_name="job-2",
        subject="Geography",
        filename="gcse-geography.md",
        batch_index=1,
        issue_ids=[2],
        created_at="2024-01-01T00:00:00Z",
        status="completed",
    ))
    
    pending = tracker.get_pending_jobs()
    assert len(pending) == 1
    assert pending[0].job_name == "job-1"


def test_batch_job_tracker_persists_to_file(tmp_path: Path) -> None:
    """Test that tracker persists data to JSON file."""
    tracking_file = tmp_path / "jobs.json"
    tracker = BatchJobTracker(tracking_file)
    
    metadata = BatchJobMetadata(
        provider_name="dummy",
        job_name="job-123",
        subject="Geography",
        filename="gcse-geography.md",
        batch_index=0,
        issue_ids=[1, 2, 3],
        created_at="2024-01-01T00:00:00Z",
        status="pending",
    )
    
    tracker.add_job(metadata)
    
    # Create new tracker with same file
    tracker2 = BatchJobTracker(tracking_file)
    retrieved = tracker2.get_job("job-123")
    
    assert retrieved is not None
    assert retrieved.job_name == "job-123"


def test_batch_orchestrator_process_batch_response_validates_correctly(tmp_path: Path) -> None:
    """Test that batch response processing validates correctly."""
    
    tracker = BatchJobTracker(Path("/tmp/test_jobs.json"))
    state = StateManager(Path("/tmp/test_state.json"))
    orchestrator = BatchOrchestrator(
        llm_service=LLMService([]),
        tracker=tracker,
        state=state,
        batch_size=10,
    )
    
    metadata = BatchJobMetadata(
        provider_name="dummy",
        job_name="job-123",
        subject="Geography",
        filename="gcse-geography.md",
        batch_index=0,
        issue_ids=[1, 2, 3],
        created_at="2024-01-01T00:00:00Z",
        status="pending",
    )
    
    # Valid response
    response = [
        {
            "issue_id": 1,
            "error_category": "SPELLING_ERROR",
            "confidence_score": 95,
            "reasoning": "Clear typo",
        },
        {
            "issue_id": 2,
                "error_category": "ABSOLUTE_GRAMMATICAL_ERROR",
            "confidence_score": 90,
            "reasoning": "Grammar issue",
        },
    ]
    
    # Prepare a temporary language-check-report.csv with matching original issues
    report_path = Path("/tmp/test_batch_orchestrator_report.csv")
    # We need at least 4 issues so the issue_ids [1,2,3] exist
    report_path.write_text(
        "Subject,Filename,Page,Rule ID,Type,Issue,Message,Suggestions,Highlighted Context,Pass Code\n"
        "Geography,gcse-geography.md,1,RULE1,style,word,Test,fix,ctx,LT\n"
        "Geography,gcse-geography.md,1,RULE2,style,word,Test,fix,ctx,LT\n"
        "Geography,gcse-geography.md,1,RULE3,style,word,Test,fix,ctx,LT\n"
        "Geography,gcse-geography.md,1,RULE4,style,word,Test,fix,ctx,LT\n"
    )
    # Create matching markdown file so load_issues doesn't skip this document
    md_path = Path("Documents") / "Geography" / "markdown"
    md_path.mkdir(parents=True, exist_ok=True)
    (md_path / "gcse-geography.md").write_text("{1} Sample page")

    results = orchestrator._process_batch_response(response, metadata, report_path)
    
    assert len(results) == 2
    assert results[0]["issue_id"] == 1
    assert results[1]["issue_id"] == 2


def test_batch_orchestrator_process_batch_response_filters_invalid(tmp_path: Path) -> None:
    """Test that batch response processing filters out invalid entries."""
    
    tracker = BatchJobTracker(Path("/tmp/test_jobs.json"))
    state = StateManager(Path("/tmp/test_state.json"))
    orchestrator = BatchOrchestrator(
        llm_service=LLMService([]),
        tracker=tracker,
        state=state,
        batch_size=10,
    )
    
    metadata = BatchJobMetadata(
        provider_name="dummy",
        job_name="job-123",
        subject="Geography",
        filename="gcse-geography.md",
        batch_index=0,
        issue_ids=[1, 2],
        created_at="2024-01-01T00:00:00Z",
        status="pending",
    )
    
    # Response with valid, missing fields, and wrong ID
    response = [
        {
            "issue_id": 1,
            "error_category": "SPELLING_ERROR",
            "confidence_score": 95,
            "reasoning": "Clear typo",
        },
        {
            "issue_id": 2,
            # Missing error_category
            "confidence_score": 90,
            "reasoning": "Grammar issue",
        },
        {
            "issue_id": 999,  # Not in batch
            "error_category": "GRAMMAR_ERROR",
            "confidence_score": 90,
            "reasoning": "Wrong batch",
        },
    ]
    
    report_path = Path("/tmp/test_batch_orchestrator_report.csv")
    report_path.write_text(
        "Subject,Filename,Page,Rule ID,Type,Issue,Message,Suggestions,Highlighted Context,Pass Code\n"
        "Geography,gcse-geography.md,1,RULE1,style,word,Test,fix,ctx,LT\n"
        "Geography,gcse-geography.md,1,RULE2,style,word,Test,fix,ctx,LT\n"
    )
    md_path = Path("Documents") / "Geography" / "markdown"
    md_path.mkdir(parents=True, exist_ok=True)
    (md_path / "gcse-geography.md").write_text("{1} Sample page")

    results = orchestrator._process_batch_response(response, metadata, report_path)
    
    # Only first entry should be valid
    assert len(results) == 1
    assert results[0]["issue_id"] == 1


def test_batch_orchestrator_process_batch_response_handles_non_list(tmp_path: Path) -> None:
    """Test that non-list responses are handled gracefully."""
    
    tracker = BatchJobTracker(Path("/tmp/test_jobs.json"))
    state = StateManager(Path("/tmp/test_state.json"))
    orchestrator = BatchOrchestrator(
        llm_service=LLMService([]),
        tracker=tracker,
        state=state,
        batch_size=10,
    )
    
    metadata = BatchJobMetadata(
        provider_name="dummy",
        job_name="job-123",
        subject="Geography",
        filename="gcse-geography.md",
        batch_index=0,
        issue_ids=[0, 1],
        created_at="2024-01-01T00:00:00Z",
        status="pending",
    )
    
    # Non-list response
    response = {"error": "Invalid format"}
    
    report_path = Path("/tmp/test_batch_orchestrator_report.csv")
    report_path.write_text(
        "Subject,Filename,Page,Rule ID,Type,Issue,Message,Suggestions,Highlighted Context,Pass Code\n"
        "Geography,gcse-geography.md,1,RULE1,style,word,Test,fix,ctx,LT\n"
        "Geography,gcse-geography.md,1,RULE2,style,word,Test,fix,ctx,LT\n"
    )

    results = orchestrator._process_batch_response(response, metadata, report_path)
    
    assert len(results) == 0


def test_batch_tracker_get_completed_jobs_within_hours(tmp_path: Path) -> None:
    """Test getting jobs completed within a time window."""
    from datetime import datetime, timezone, timedelta
    
    tracking_file = tmp_path / "jobs.json"
    tracker = BatchJobTracker(tracking_file)
    
    # Create jobs with different timestamps
    now = datetime.now(timezone.utc)
    
    # Job completed 2 hours ago
    recent_job = BatchJobMetadata(
        provider_name="dummy",
        job_name="job-recent",
        subject="Geography",
        filename="gcse-geography.md",
        batch_index=0,
        issue_ids=[1, 2, 3],
        created_at=(now - timedelta(hours=2)).isoformat().replace('+00:00', 'Z'),
        status="completed",
    )
    tracker.add_job(recent_job)
    
    # Job completed 10 hours ago
    old_job = BatchJobMetadata(
        provider_name="dummy",
        job_name="job-old",
        subject="History",
        filename="gcse-history.md",
        batch_index=0,
        issue_ids=[4, 5, 6],
        created_at=(now - timedelta(hours=10)).isoformat().replace('+00:00', 'Z'),
        status="completed",
    )
    tracker.add_job(old_job)
    
    # Pending job (should not be returned)
    pending_job = BatchJobMetadata(
        provider_name="dummy",
        job_name="job-pending",
        subject="Math",
        filename="gcse-math.md",
        batch_index=0,
        issue_ids=[7, 8, 9],
        created_at=(now - timedelta(hours=1)).isoformat().replace('+00:00', 'Z'),
        status="pending",
    )
    tracker.add_job(pending_job)
    
    # Get jobs completed within last 6 hours
    jobs_within_6h = tracker.get_completed_jobs_within_hours(6.0)
    
    assert len(jobs_within_6h) == 1
    assert jobs_within_6h[0].job_name == "job-recent"
    
    # Get jobs completed within last 12 hours
    jobs_within_12h = tracker.get_completed_jobs_within_hours(12.0)
    
    assert len(jobs_within_12h) == 2
    job_names = {job.job_name for job in jobs_within_12h}
    assert job_names == {"job-recent", "job-old"}
    
    # Get jobs completed within last 1 hour
    jobs_within_1h = tracker.get_completed_jobs_within_hours(1.0)
    
    assert len(jobs_within_1h) == 0


def test_state_remove_batch_completion(tmp_path: Path) -> None:
    """Test removing batch completion from state."""
    from src.models import DocumentKey
    
    state_file = tmp_path / "state.json"
    state = CategoriserState(state_file)
    
    key = DocumentKey(subject="Geography", filename="gcse-geography.md")
    
    # Mark some batches as completed
    state.mark_batch_completed(key, 0, 10)
    state.mark_batch_completed(key, 1, 10)
    state.mark_batch_completed(key, 2, 10)
    
    assert state.is_batch_completed(key, 0)
    assert state.is_batch_completed(key, 1)
    assert state.is_batch_completed(key, 2)
    
    # Remove batch 1
    state.remove_batch_completion(key, 1)
    
    assert state.is_batch_completed(key, 0)
    assert not state.is_batch_completed(key, 1)
    assert state.is_batch_completed(key, 2)
    
    # Verify persistence
    state2 = CategoriserState(state_file)
    assert state2.is_batch_completed(key, 0)
    assert not state2.is_batch_completed(key, 1)
    assert state2.is_batch_completed(key, 2)

