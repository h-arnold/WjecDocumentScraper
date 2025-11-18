from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.llm.service import LLMService
from src.models import DocumentKey, LanguageIssue

from .batcher import Batch, iter_batches
from .config import ReviewConfiguration
from .document_loader import load_issues
from .persistence import PersistenceManager
from .state_manager import StateManager


@dataclass
class BatchJobMetadata:
    """Metadata for tracking a batch job."""

    provider_name: str
    job_name: str
    subject: str
    filename: str
    batch_index: int
    issue_ids: list[int]
    created_at: str
    status: str = "pending"
    error_message: str | None = None


class BatchJobTracker:
    """Manages tracking of batch jobs in a JSON file."""

    def __init__(self, tracking_file: Path):
        self.tracking_file = tracking_file
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self.tracking_file.exists():
            try:
                with open(self.tracking_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"Warning: Could not load tracking file: {e}")

    def _save(self) -> None:
        self.tracking_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.tracking_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            temp_file.replace(self.tracking_file)
        except OSError as e:
            print(f"Warning: Could not save tracking file: {e}")
            if temp_file.exists():
                temp_file.unlink()

    def add_job(self, metadata: BatchJobMetadata) -> None:
        self._data[metadata.job_name] = asdict(metadata)
        self._save()

    def update_job_status(
        self, job_name: str, status: str, error_message: str | None = None
    ) -> None:
        if job_name in self._data:
            self._data[job_name]["status"] = status
            if error_message is not None:
                self._data[job_name]["error_message"] = error_message
            self._save()

    def get_job(self, job_name: str) -> BatchJobMetadata | None:
        if job_name not in self._data:
            return None
        return BatchJobMetadata(**self._data[job_name])

    def get_all_jobs(self) -> list[BatchJobMetadata]:
        return [BatchJobMetadata(**data) for data in self._data.values()]

    def get_pending_jobs(self) -> list[BatchJobMetadata]:
        return [
            BatchJobMetadata(**data)
            for data in self._data.values()
            if data.get("status") == "pending"
        ]

    def get_completed_jobs_within_hours(self, hours: float) -> list[BatchJobMetadata]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        completed_jobs = []

        for data in self._data.values():
            if data.get("status") != "completed":
                continue

            try:
                created_at_str = data.get("created_at", "")
                if created_at_str.endswith("Z"):
                    created_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                else:
                    created_at = datetime.fromisoformat(created_at_str)

                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)

                if created_at >= cutoff:
                    completed_jobs.append(BatchJobMetadata(**data))
            except (ValueError, TypeError) as e:
                print(f"Warning: Skipping job with invalid timestamp: {e}")
                continue

        return completed_jobs


class BatchOrchestrator(ABC):
    """Abstract base class for orchestrating batch jobs."""

    def __init__(
        self,
        llm_service: LLMService,
        tracker: BatchJobTracker,
        state: StateManager,
        config: ReviewConfiguration,
    ):
        self.llm_service = llm_service
        self.tracker = tracker
        self.state = state
        self.config = config
        self.persistence = PersistenceManager(config)

    def create_batch_jobs(
        self,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        """Create batch jobs for all document batches."""
        print(f"Loading issues from {self.config.input_csv_path}...")
        grouped_issues = load_issues(
            self.config.input_csv_path,
            subjects=self.config.subjects,
            documents=self.config.documents,
        )

        if not grouped_issues:
            print("No issues found matching the filters")
            return {
                "total_documents": 0,
                "total_batches": 0,
                "created_jobs": 0,
                "skipped_batches": 0,
            }

        print(f"Loaded {len(grouped_issues)} document(s) with issues")

        total_batches = 0
        created_jobs = 0
        skipped_batches = 0

        for key, issues in grouped_issues.items():
            print(f"\nProcessing {key} ({len(issues)} issues)...")

            markdown_path = Path("Documents") / key.subject / "markdown" / key.filename

            for batch in iter_batches(
                issues,
                self.config.batch_size,
                markdown_path,
                subject=key.subject,
                filename=key.filename,
            ):
                total_batches += 1

                if not force and self.state.is_batch_completed(key, batch.index):
                    print(f"  Batch {batch.index}: Already completed (skipping)")
                    skipped_batches += 1
                    continue

                prompts = self.build_prompts(batch)
                if len(prompts) > 1:
                    user_prompts = prompts[1:]
                else:
                    user_prompts = prompts

                try:
                    batch_payload = [user_prompts]

                    provider_name, job_name = self.llm_service.create_batch_job(
                        batch_payload, filter_json=True
                    )

                    metadata = BatchJobMetadata(
                        provider_name=provider_name,
                        job_name=job_name,
                        subject=key.subject,
                        filename=key.filename,
                        batch_index=batch.index,
                        issue_ids=[issue.issue_id for issue in batch.issues],
                        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        status="pending",
                    )
                    self.tracker.add_job(metadata)

                    print(f"  Batch {batch.index}: Created job {job_name[:16]}...")
                    created_jobs += 1

                except Exception as e:
                    print(f"  Batch {batch.index}: Failed to create job - {e}")
                    continue

        return {
            "total_documents": len(grouped_issues),
            "total_batches": total_batches,
            "created_jobs": created_jobs,
            "skipped_batches": skipped_batches,
        }

    def fetch_batch_results(
        self,
        *,
        job_names: list[str] | None = None,
        check_all_pending: bool = False,
        refetch_hours: float | None = None,
    ) -> dict[str, Any]:
        """Fetch results from completed batch jobs."""
        if job_names:
            jobs_to_check = [
                job for job in self.tracker.get_all_jobs() if job.job_name in job_names
            ]
        elif check_all_pending:
            jobs_to_check = self.tracker.get_pending_jobs()
        elif refetch_hours is not None:
            jobs_to_refetch = self.tracker.get_completed_jobs_within_hours(
                refetch_hours
            )
            print(
                f"Found {len(jobs_to_refetch)} job(s) completed within last {refetch_hours} hour(s)"
            )

            if not jobs_to_refetch:
                print("No jobs to refetch")
                return {
                    "checked_jobs": 0,
                    "completed_jobs": 0,
                    "failed_jobs": 0,
                    "refetched": 0,
                }

            for job in jobs_to_refetch:
                key = DocumentKey(subject=job.subject, filename=job.filename)
                self.state.remove_batch_completion(key, job.batch_index)
                self.tracker.update_job_status(job.job_name, "pending", None)
                print(
                    f"Reset {job.job_name[:16]}... ({job.subject}/{job.filename} batch {job.batch_index}) to pending"
                )

            jobs_to_check = jobs_to_refetch
        else:
            print(
                "No jobs specified. Use --job-names, --check-all-pending, or --refetch-hours"
            )
            return {"checked_jobs": 0, "completed_jobs": 0, "failed_jobs": 0}

        if not jobs_to_check:
            print("No jobs to check")
            return {"checked_jobs": 0, "completed_jobs": 0, "failed_jobs": 0}

        print(f"Checking {len(jobs_to_check)} job(s)...")

        checked = 0
        completed = 0
        failed = 0
        still_pending = 0

        for job_metadata in jobs_to_check:
            checked += 1
            job_name = job_metadata.job_name

            print(
                f"\nJob {job_name[:16]}... ({job_metadata.subject}/{job_metadata.filename} batch {job_metadata.batch_index})"
            )

            try:
                status = self.llm_service.get_batch_job_status(
                    job_metadata.provider_name, job_name
                )

                if not status.done:
                    print(f"  Status: {status.state} (still pending)")
                    still_pending += 1
                    continue

                if hasattr(status, "error") and status.error:
                    error_msg = str(status.error)
                    print(f"  Error: Batch job failed - {error_msg}")
                    self.tracker.update_job_status(job_name, "failed", error_msg)
                    failed += 1
                    continue

                results = self.llm_service.fetch_batch_results(
                    job_metadata.provider_name, job_name
                )

                if not results or len(results) == 0:
                    error_msg = "No results returned"
                    print(f"  Error: {error_msg}")
                    self.tracker.update_job_status(job_name, "failed", error_msg)
                    failed += 1
                    continue

                response = results[0]

                validated_results = self._process_batch_response(
                    response,
                    job_metadata,
                )

                if validated_results:
                    key = DocumentKey(
                        subject=job_metadata.subject, filename=job_metadata.filename
                    )

                    output_path = self.persistence.save_batch_results(
                        key, validated_results, merge=True
                    )
                    print(
                        f"  Saved {len(validated_results)} result(s) to {output_path}"
                    )

                    total_issues = len(job_metadata.issue_ids)
                    self.state.mark_batch_completed(
                        key, job_metadata.batch_index, total_issues
                    )

                    self.tracker.update_job_status(job_name, "completed")
                    completed += 1
                else:
                    error_msg = "No valid results after processing"
                    print(f"  Warning: {error_msg}")
                    self.tracker.update_job_status(job_name, "failed", error_msg)
                    failed += 1

            except Exception as e:
                error_msg = str(e)
                print(f"  Error processing job: {error_msg}")
                self.tracker.update_job_status(job_name, "failed", error_msg)
                failed += 1
                continue

        print(f"\n{'=' * 60}")
        print("Summary:")
        print(f"  Checked: {checked}")
        print(f"  Completed: {completed}")
        print(f"  Failed: {failed}")
        print(f"  Still pending: {still_pending}")
        if refetch_hours is not None:
            print(f"  Refetched: {len(jobs_to_check)}")
        print(f"{'=' * 60}")

        result = {
            "checked_jobs": checked,
            "completed_jobs": completed,
            "failed_jobs": failed,
            "still_pending": still_pending,
        }

        if refetch_hours is not None:
            result["refetched"] = len(jobs_to_check)

        return result

    def _process_batch_response(
        self,
        response: Any,
        job_metadata: BatchJobMetadata,
    ) -> list[dict[str, Any]]:
        """Process and validate a batch response."""
        key = DocumentKey(subject=job_metadata.subject, filename=job_metadata.filename)
        grouped_issues = load_issues(
            self.config.input_csv_path,
            subjects={key.subject},
            documents={key.filename},
        )

        if key not in grouped_issues:
            print(f"    Error: Could not find issues for {key}")
            return []

        all_issues = grouped_issues[key]
        batch_issues = [i for i in all_issues if i.issue_id in job_metadata.issue_ids]

        if not batch_issues:
            print(f"    Error: Could not find batch issues for {key}")
            return []

        validated, failed, errors = self.validate_response(response, batch_issues)

        if failed:
            print(f"    Warning: {len(failed)} issue(s) failed validation")

        return validated

    @abstractmethod
    def build_prompts(self, batch: Batch) -> list[str]:
        """Build prompts for the LLM."""
        pass

    @abstractmethod
    def validate_response(
        self, response: Any, issues: list[LanguageIssue]
    ) -> tuple[list[dict[str, Any]], set[int], dict[object, list[str]]]:
        """Validate LLM response."""
        pass
