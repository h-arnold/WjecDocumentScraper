"""Batch orchestrator for LLM categorisation using Gemini Batch API.

This module provides functionality to create and retrieve batch jobs for
asynchronous processing of language issues through the Gemini batch API.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from dataclasses import dataclass, asdict

from src.models import DocumentKey, PassCode
from src.llm.service import LLMService

from ..core.batcher import iter_batches
from ..core.document_loader import load_issues
from .persistence import save_batch_results
from .prompt_factory import build_prompts
from ..core.state_manager import StateManager


@dataclass
class BatchJobMetadata:
    """Metadata for tracking a batch job.
    
    Attributes:
        provider_name: Name of the LLM provider
        job_name: Unique job identifier from the provider
        subject: Subject name (e.g., "Art-and-Design")
        filename: Document filename (e.g., "gcse-art-and-design.md")
        batch_index: Zero-based batch index for this document
        issue_ids: List of issue IDs in this batch
        created_at: ISO timestamp when job was created
        status: Current status ("pending", "completed", "failed")
        error_message: Optional error message for failed jobs
    """
    
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
        """Initialize the tracker.
        
        Args:
            tracking_file: Path to JSON file for storing job metadata
        """
        self.tracking_file = tracking_file
        self._data: dict[str, dict[str, Any]] = {}
        self._load()
    
    def _load(self) -> None:
        """Load tracking data from file if it exists."""
        if self.tracking_file.exists():
            try:
                with open(self.tracking_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"Warning: Could not load tracking file: {e}")
    
    def _save(self) -> None:
        """Save tracking data to file atomically."""
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
        """Add a job to tracking."""
        self._data[metadata.job_name] = asdict(metadata)
        self._save()
    
    def update_job_status(self, job_name: str, status: str, error_message: str | None = None) -> None:
        """Update the status of a tracked job.
        
        Args:
            job_name: The job name to update
            status: New status value
            error_message: Optional error message for failed jobs
        """
        if job_name in self._data:
            self._data[job_name]["status"] = status
            if error_message is not None:
                self._data[job_name]["error_message"] = error_message
            self._save()
    
    def get_job(self, job_name: str) -> BatchJobMetadata | None:
        """Get metadata for a specific job."""
        if job_name not in self._data:
            return None
        return BatchJobMetadata(**self._data[job_name])
    
    def get_all_jobs(self) -> list[BatchJobMetadata]:
        """Get metadata for all tracked jobs."""
        return [BatchJobMetadata(**data) for data in self._data.values()]
    
    def get_pending_jobs(self) -> list[BatchJobMetadata]:
        """Get metadata for all pending jobs."""
        return [
            BatchJobMetadata(**data)
            for data in self._data.values()
            if data.get("status") == "pending"
        ]
    
    def get_completed_jobs_within_hours(self, hours: float) -> list[BatchJobMetadata]:
        """Get jobs completed within the specified number of hours.
        
        Args:
            hours: Number of hours to look back from now
            
        Returns:
            List of completed jobs within the time window
        """
        from datetime import datetime, timezone, timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        completed_jobs = []
        
        for data in self._data.values():
            if data.get("status") != "completed":
                continue
            
            try:
                # Parse created_at timestamp (ISO format)
                created_at_str = data.get("created_at", "")
                # Handle both 'Z' and timezone-aware formats
                if created_at_str.endswith('Z'):
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                else:
                    created_at = datetime.fromisoformat(created_at_str)
                
                # Ensure timezone-aware comparison
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                
                if created_at >= cutoff:
                    completed_jobs.append(BatchJobMetadata(**data))
            except (ValueError, TypeError) as e:
                # Skip jobs with invalid timestamps
                print(f"Warning: Skipping job with invalid timestamp: {e}")
                continue
        
        return completed_jobs


class BatchOrchestrator:
    """Orchestrates batch job creation and retrieval for LLM categorisation."""
    
    def __init__(
        self,
        llm_service: LLMService,
        tracker: BatchJobTracker,
        state: StateManager,
        batch_size: int = 10,
    ):
        """Initialize the orchestrator.
        
        Args:
            llm_service: LLM service for making batch API calls
            tracker: Job tracker for persisting metadata
            state: State manager for tracking completed batches
            batch_size: Number of issues per batch
        """
        self.llm_service = llm_service
        self.tracker = tracker
        self.state = state
        self.batch_size = batch_size
    
    def create_batch_jobs(
        self,
        report_path: Path,
        *,
        subjects: set[str] | None = None,
        documents: set[str] | None = None,
    ) -> dict[str, Any]:
        """Create batch jobs for all document batches.
        
        Skips batches that are already marked as completed in the state.
        
        Args:
            report_path: Path to language-check-report.csv
            subjects: Optional subject filter
            documents: Optional document filter
            
        Returns:
            Summary statistics dictionary
        """
        print(f"Loading issues from {report_path}...")
        grouped_issues = load_issues(report_path, subjects=subjects, documents=documents)
        
        if not grouped_issues:
            print("No issues found matching the filters")
            return {"total_documents": 0, "total_batches": 0, "created_jobs": 0, "skipped_batches": 0}
        
        print(f"Loaded {len(grouped_issues)} document(s) with issues")
        
        total_batches = 0
        created_jobs = 0
        skipped_batches = 0
        
        for key, issues in grouped_issues.items():
            print(f"\nProcessing {key} ({len(issues)} issues)...")
            
            # Get Markdown path
            markdown_path = Path("Documents") / key.subject / "markdown" / key.filename
            
            # Process batches for this document
            for batch in iter_batches(
                issues,
                self.batch_size,
                markdown_path,
                subject=key.subject,
                filename=key.filename,
            ):
                total_batches += 1
                
                # Check if this batch is already completed
                if self.state.is_batch_completed(key, batch.index):
                    print(f"  Batch {batch.index}: Already completed (skipping)")
                    skipped_batches += 1
                    continue
                
                # Build prompts
                prompts = build_prompts(batch)
                if len(prompts) > 1:
                    user_prompts = prompts[1:]  # Skip system prompt
                else:
                    user_prompts = prompts
                
                # Create batch job
                try:
                    # Wrap prompts in batch_payload format (list of prompt sequences)
                    batch_payload = [user_prompts]
                    
                    provider_name, job_name = self.llm_service.create_batch_job(
                        batch_payload,
                        filter_json=True
                    )
                    
                    # Store metadata
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
        
        print(f"\n{'=' * 60}")
        print(f"Summary:")
        print(f"  Total documents: {len(grouped_issues)}")
        print(f"  Total batches: {total_batches}")
        print(f"  Skipped (already completed): {skipped_batches}")
        print(f"  Created jobs: {created_jobs}")
        print(f"{'=' * 60}")
        
        return {
            "total_documents": len(grouped_issues),
            "total_batches": total_batches,
            "created_jobs": created_jobs,
            "skipped_batches": skipped_batches,
        }
    
    def fetch_batch_results(
        self,
        state: CategoriserState,
        *,
        job_names: list[str] | None = None,
        check_all_pending: bool = False,
        refetch_hours: float | None = None,
    ) -> dict[str, Any]:
        """Fetch results from completed batch jobs.
        
        Args:
            state: State manager for tracking completion
            report_path: Path to language-check-report.csv for loading original issues
            job_names: Optional list of specific job names to fetch
            check_all_pending: If True, check all pending jobs for completion
            refetch_hours: If specified, refetch jobs completed within this many hours
            
        Returns:
            Summary statistics dictionary
        """
        # Determine which jobs to check
        if job_names:
            jobs_to_check = [
                job for job in self.tracker.get_all_jobs()
                if job.job_name in job_names
            ]
        elif check_all_pending:
            jobs_to_check = self.tracker.get_pending_jobs()
        elif refetch_hours is not None:
            # Get completed jobs within the time window and reset them
            jobs_to_refetch = self.tracker.get_completed_jobs_within_hours(refetch_hours)
            print(f"Found {len(jobs_to_refetch)} job(s) completed within last {refetch_hours} hour(s)")
            
            if not jobs_to_refetch:
                print("No jobs to refetch")
                return {"checked_jobs": 0, "completed_jobs": 0, "failed_jobs": 0, "refetched": 0}
            
            # Reset jobs to pending and clear completed state
            for job in jobs_to_refetch:
                key = DocumentKey(subject=job.subject, filename=job.filename)
                # Remove batch completion from state so it will be reprocessed
                state.remove_batch_completion(key, job.batch_index)
                # Reset tracker status to pending
                self.tracker.update_job_status(job.job_name, "pending", None)
                print(f"Reset {job.job_name[:16]}... ({job.subject}/{job.filename} batch {job.batch_index}) to pending")
            
            # Now fetch these jobs
            jobs_to_check = jobs_to_refetch
        else:
            print("No jobs specified. Use --job-names, --check-all-pending, or --refetch-hours")
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
            
            print(f"\nJob {job_name[:16]}... ({job_metadata.subject}/{job_metadata.filename} batch {job_metadata.batch_index})")
            
            try:
                # Check job status
                status = self.llm_service.get_batch_job_status(
                    job_metadata.provider_name,
                    job_name
                )
                
                if not status.done:
                    print(f"  Status: {status.state} (still pending)")
                    still_pending += 1
                    continue
                
                # Check if job failed at the batch level
                if hasattr(status, 'error') and status.error:
                    error_msg = str(status.error)
                    print(f"  Error: Batch job failed - {error_msg}")
                    self.tracker.update_job_status(job_name, "failed", error_msg)
                    failed += 1
                    continue
                
                # Job is done, fetch results
                results = self.llm_service.fetch_batch_results(
                    job_metadata.provider_name,
                    job_name
                )
                
                # Results is a sequence of responses (one per request in the batch)
                # Since we send one request per batch, we get one response
                if not results or len(results) == 0:
                    error_msg = "No results returned"
                    print(f"  Error: {error_msg}")
                    self.tracker.update_job_status(job_name, "failed", error_msg)
                    failed += 1
                    continue
                
                response = results[0]  # Get the single response
                
                # Validate and process response
                validated_results = self._process_batch_response(
                    response,
                    job_metadata,
                    report_path
                )
                
                if validated_results:
                    # Create DocumentKey and save results
                    key = DocumentKey(
                        subject=job_metadata.subject,
                        filename=job_metadata.filename
                    )
                    
                    output_path = save_batch_results(key, validated_results, merge=True)
                    print(f"  Saved {len(validated_results)} result(s) to {output_path}")
                    
                    # Mark batch as completed in state
                    # Get total issues from metadata (we stored issue_ids)
                    total_issues = len(job_metadata.issue_ids)
                    state.mark_batch_completed(key, job_metadata.batch_index, total_issues)
                    
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
        print(f"Summary:")
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
        report_path: Path,
    ) -> list[dict[str, Any]]:
        """Process and validate a batch response.
        
        This mirrors the validation logic in CategoriserRunner._validate_response
        but adapted for batch results. Loads original issues from CSV and merges
        LLM categorisation fields with the complete issue data.
        
        Args:
            response: The LLM response (should be a list of issue dicts)
            job_metadata: Metadata for the job
            report_path: Path to language-check-report.csv
            
        Returns:
            List of validated issue dictionaries with all fields populated
        """
        validated_results: list[dict[str, Any]] = []
        
        # Response should be a list
        if not isinstance(response, list):
            print(f"  Error: Expected list, got {type(response)}")
            return validated_results
        
        if not response:
            print(f"  Warning: Response is empty")
            return validated_results
        
        # Process each issue in the response
        for issue_dict in response:
            if not isinstance(issue_dict, dict):
                print(f"  Warning: Skipping non-dict entry")
                continue
            
            # Extract issue_id to verify it's in our batch
            issue_id = issue_dict.get("issue_id")
            if issue_id not in job_metadata.issue_ids:
                print(f"  Warning: Issue ID {issue_id} not in batch, skipping")
                continue
            
            # Validate required LLM fields
            if not all(key in issue_dict for key in ["issue_id", "error_category", "confidence_score", "reasoning"]):
                print(f"  Warning: Issue {issue_id} missing required fields")
                continue
            
            # Merge LLM fields with original issue data
            if issue_id in issue_map:
                orig = issue_map[issue_id]
                merged = {
                    "filename": orig.filename,
                    "rule_id": orig.rule_id,
                    "message": orig.message,
                    "issue_type": orig.issue_type,
                    "replacements": orig.replacements,
                    "context": orig.context,
                    "highlighted_context": orig.highlighted_context,
                    "issue": orig.issue,
                    "page_number": orig.page_number,
                    "issue_id": orig.issue_id,
                    "pass_code": PassCode.LTC,  # Mark as LLM-categorised
                    # LLM fields from response
                    "error_category": issue_dict.get("error_category"),
                    "confidence_score": issue_dict.get("confidence_score"),
                    "reasoning": issue_dict.get("reasoning"),
                }
                
                # Validate merged result
                try:
                    from src.models.language_issue import LanguageIssue
                    validated = LanguageIssue(**merged)
                    validated_results.append(validated.model_dump())
                except Exception as e:
                    print(f"  Warning: Failed to validate issue {issue_id}: {e}")
                    continue
            else:
                print(f"  Warning: Original issue {issue_id} not found in issue map")
                continue
        
        return validated_results
    
    def list_jobs(self, status_filter: str | None = None, show_errors: bool = False) -> None:
        """List all tracked jobs.
        
        Args:
            status_filter: Optional status to filter by ("pending", "completed", "failed")
            show_errors: If True, display error messages for failed jobs
        """
        all_jobs = self.tracker.get_all_jobs()
        
        if status_filter:
            all_jobs = [j for j in all_jobs if j.status == status_filter]
        
        if not all_jobs:
            print("No jobs found")
            return
        
        print(f"\n{'=' * 80}")
        print(f"{'Job Name':<18} {'Status':<12} {'Subject':<20} {'Document':<25}")
        print(f"{'=' * 80}")
        
        for job in all_jobs:
            doc_name = job.filename[:22] + "..." if len(job.filename) > 25 else job.filename
            print(f"{job.job_name[:16]}... {job.status:<12} {job.subject:<20} {doc_name:<25}")
            
            # Show error details if requested and job has failed
            if show_errors and job.status == "failed" and job.error_message:
                print(f"  Error: {job.error_message}")
        
        print(f"{'=' * 80}")
        print(f"Total: {len(all_jobs)} job(s)")
        
        # Show summary of errors if there are failed jobs
        if not show_errors:
            failed_count = sum(1 for j in all_jobs if j.status == "failed")
            if failed_count > 0:
                print(f"\nNote: {failed_count} job(s) have failed. Use --show-errors to see error details.")
    
    def cancel_batch_jobs(
        self,
        *,
        job_names: list[str] | None = None,
        cancel_all_pending: bool = False,
    ) -> dict[str, Any]:
        """Cancel batch jobs.
        
        Args:
            job_names: Optional list of specific job names to cancel
            cancel_all_pending: If True, cancel all pending jobs
            
        Returns:
            Summary statistics dictionary
        """
        if not job_names and not cancel_all_pending:
            print("Error: Must specify either --job-names or --cancel-all-pending")
            return {"cancelled": 0, "failed": 0, "skipped": 0}
        
        # Determine which jobs to cancel
        if cancel_all_pending:
            jobs_to_cancel = self.tracker.get_pending_jobs()
            print(f"Found {len(jobs_to_cancel)} pending job(s) to cancel\n")
        else:
            jobs_to_cancel = []
            if job_names:
                for job_name in job_names:
                    job = self.tracker.get_job(job_name)
                    if job:
                        jobs_to_cancel.append(job)
                    else:
                        print(f"Warning: Job {job_name} not found in tracking")
        
        if not jobs_to_cancel:
            print("No jobs to cancel")
            return {"cancelled": 0, "failed": 0, "skipped": 0}
        
        cancelled = 0
        failed_to_cancel = 0
        skipped = 0
        
        for job in jobs_to_cancel:
            job_name = job.job_name
            print(f"Cancelling {job_name[:16]}... ({job.subject}/{job.filename})")
            
            # Skip if not pending
            if job.status != "pending":
                print(f"  Skipped: Job status is '{job.status}', not 'pending'")
                skipped += 1
                continue
            
            try:
                self.llm_service.cancel_batch_job(
                    job.provider_name,
                    job_name
                )
                print(f"  Successfully cancelled")
                # Update status in tracker to 'failed' with cancellation message
                self.tracker.update_job_status(
                    job_name, 
                    "failed", 
                    "Cancelled by user"
                )
                cancelled += 1
                
            except Exception as e:
                error_msg = str(e)
                print(f"  Error: {error_msg}")
                failed_to_cancel += 1
        
        print(f"\n{'=' * 60}")
        print(f"Summary:")
        print(f"  Cancelled: {cancelled}")
        print(f"  Failed to cancel: {failed_to_cancel}")
        print(f"  Skipped (not pending): {skipped}")
        print(f"{'=' * 60}")
        
        return {
            "cancelled": cancelled,
            "failed": failed_to_cancel,
            "skipped": skipped,
        }
