"""Batch orchestrator for the categoriser verifier.

Handles creating and processing batch jobs for the verifier workflow.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.models import DocumentKey, ErrorCategory, LanguageIssue, PassCode

from ..core.batch_orchestrator import BatchJobMetadata, BatchOrchestrator
from ..core.batcher import Batch, iter_batches
from .data_loader import load_categorised_issues
from .prompt_factory import build_prompts


class VerifierBatchOrchestrator(BatchOrchestrator):
    """Orchestrates batch jobs for the categoriser verifier."""

    def create_batch_jobs(
        self,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        """Create batch jobs for all document batches.

        Overrides base method to use load_categorised_issues and filter false positives.
        """
        print(f"Loading issues from {self.config.input_csv_path}...")
        grouped_issues = load_categorised_issues(
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
            # Filter out FALSE_POSITIVE issues
            original_count = len(issues)
            issues = self._filter_false_positives(issues)
            filtered_count = len(issues)

            if filtered_count < original_count:
                print(
                    f"Filtered out {original_count - filtered_count} FALSE_POSITIVE issue(s) from {key}"
                )

            if not issues:
                print(f"  No issues left after filtering for {key}, skipping")
                continue

            print(f"\nProcessing {key} ({len(issues)} issues)...")

            # Get Markdown path - convert .csv filename to .md
            markdown_filename = key.filename
            if markdown_filename.endswith(".csv"):
                markdown_filename = markdown_filename[:-4] + ".md"
            markdown_path = (
                Path("Documents") / key.subject / "markdown" / markdown_filename
            )

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
                # For batch API, we usually send a list of prompts.
                # If prompts is [system, user], we might need to adjust depending on provider.
                # The base class assumes prompts[1:] are user prompts if len > 1.
                # But here build_prompts returns [system, user].
                # The base class does:
                # if len(prompts) > 1: user_prompts = prompts[1:] else: user_prompts = prompts
                # batch_payload = [user_prompts]
                # This seems to imply it sends only user prompts in the batch payload?
                # Let's check LLMService.create_batch_job.

                # Assuming the base class logic is correct for the provider (Gemini).
                # Gemini batch API usually takes a list of requests.
                # If we are using the standard create_batch_job, we should follow the pattern.

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

    def build_prompts(self, batch: Batch) -> list[str]:
        """Build prompts for the LLM."""
        return build_prompts(batch)

    def validate_response(
        self,
        response: Any,
        issues: list[LanguageIssue],
    ) -> tuple[list[dict[str, Any]], set[int], dict[object, list[str]]]:
        """Validate LLM response and return validated results, failed ids and error messages.

        Replicates logic from VerifierRunner.validate_response.
        """
        validated_results: list[dict[str, Any]] = []
        failed_issue_ids: set[int] = set(issue.issue_id for issue in issues)

        # Map of issue ids or 'batch_errors' to lists of messages
        error_messages: dict[object, list[str]] = {
            issue.issue_id: [] for issue in issues
        }
        error_messages.setdefault("batch_errors", [])

        # Only accept a top-level JSON array of objects from the LLM.
        if not isinstance(response, list):
            msg = "Expected top-level JSON array of objects"
            error_messages.setdefault("batch_errors", []).append(msg)
            return validated_results, failed_issue_ids, error_messages

        # Get filename from first issue (all issues in a batch are from same document)
        filename = issues[0].filename if issues else ""

        if not response:
            msg = "Response is empty; no issues to validate"
            error_messages.setdefault("batch_errors", []).append(msg)
            return validated_results, failed_issue_ids, error_messages

        # Build a map of original issues indexed by issue_id
        issue_map = {issue.issue_id: issue for issue in issues}

        # Process the flat response list
        for issue_dict in response:
            # Only accept dictionaries
            if not isinstance(issue_dict, dict):
                warn = "Entry in response array is not a JSON object"
                error_messages.setdefault("batch_errors", []).append(warn)
                continue

            try:
                iid = (
                    issue_dict.get("issue_id") if isinstance(issue_dict, dict) else None
                )

                if iid is not None and iid in issue_map:
                    # Merge verifier results into the original issue
                    orig = issue_map[iid]
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
                        "pass_code": PassCode.LTC,
                        # LLM fields (verified/updated)
                        "error_category": issue_dict.get("error_category"),
                        "confidence_score": issue_dict.get("confidence_score"),
                        "reasoning": issue_dict.get("reasoning"),
                    }
                    validated = LanguageIssue(**merged)
                else:
                    # Fall back to creating from full LLM response
                    validated = LanguageIssue.from_llm_response(
                        issue_dict, filename=filename
                    )
                validated_results.append(validated.model_dump())

                # If the LLM supplied an explicit issue_id, mark it as validated.
                if validated.issue_id >= 0:
                    failed_issue_ids.discard(validated.issue_id)

            except ValidationError as e:
                iid = (
                    issue_dict.get("issue_id") if isinstance(issue_dict, dict) else None
                )
                if iid is not None:
                    error_messages.setdefault(iid, []).append(str(e))
                else:
                    error_messages.setdefault("batch_errors", []).append(str(e))
                continue
            except Exception as e:
                iid = (
                    issue_dict.get("issue_id") if isinstance(issue_dict, dict) else None
                )
                if iid is not None:
                    error_messages.setdefault(iid, []).append(str(e))
                else:
                    error_messages.setdefault("batch_errors", []).append(str(e))
                continue

        if not validated_results:
            msg = "Response contained no valid issue objects"
            error_messages.setdefault("batch_errors", []).append(msg)

        return validated_results, failed_issue_ids, error_messages

    def _filter_false_positives(
        self, issues: list[LanguageIssue]
    ) -> list[LanguageIssue]:
        """Return a new list with any FALSE_POSITIVE issues removed."""
        filtered: list[LanguageIssue] = []
        for issue in issues:
            cat = issue.error_category
            if cat is None:
                filtered.append(issue)
                continue
            # Allow string or ErrorCategory enum
            if isinstance(cat, str):
                if cat != ErrorCategory.FALSE_POSITIVE.value:
                    filtered.append(issue)
            else:
                if cat != ErrorCategory.FALSE_POSITIVE:
                    filtered.append(issue)

        return filtered

    def list_jobs(
        self, status_filter: str | None = None, show_errors: bool = False
    ) -> None:
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
            doc_name = (
                job.filename[:22] + "..." if len(job.filename) > 25 else job.filename
            )
            print(
                f"{job.job_name[:16]}... {job.status:<12} {job.subject:<20} {doc_name:<25}"
            )

            # Show error details if requested and job has failed
            if show_errors and job.status == "failed" and job.error_message:
                print(f"  Error: {job.error_message}")

        print(f"{'=' * 80}")
        print(f"Total: {len(all_jobs)} job(s)")

        # Show summary of errors if there are failed jobs
        if not show_errors:
            failed_count = sum(1 for j in all_jobs if j.status == "failed")
            if failed_count > 0:
                print(
                    f"\nNote: {failed_count} job(s) have failed. Use --show-errors to see error details."
                )

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
                self.llm_service.cancel_batch_job(job.provider_name, job_name)
                print("  Successfully cancelled")
                # Update status in tracker to 'failed' with cancellation message
                self.tracker.update_job_status(job_name, "failed", "Cancelled by user")
                cancelled += 1

            except Exception as e:
                error_msg = str(e)
                print(f"  Error: {error_msg}")
                failed_to_cancel += 1

        print(f"\n{'=' * 60}")
        print("Summary:")
        print(f"  Cancelled: {cancelled}")
        print(f"  Failed to cancel: {failed_to_cancel}")
        print(f"  Skipped (not pending): {skipped}")
        print(f"{'=' * 60}")

        return {
            "cancelled": cancelled,
            "failed": failed_to_cancel,
            "skipped": skipped,
        }

    def fetch_batch_results(
        self,
        *,
        job_names: list[str] | None = None,
        check_all_pending: bool = False,
        refetch_hours: float | None = None,
    ) -> dict[str, Any]:
        """Fetch results from completed batch jobs.

        Overrides base method to accumulate results for aggregated CSV output.
        """
        # Import persistence manager
        from .persistence import VerifierPersistenceManager

        # Create fresh persistence manager for this fetch operation
        persistence = VerifierPersistenceManager(self.config)

        # Determine which jobs to check (same logic as base class)
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

                    # Add to persistence manager (accumulates in memory)
                    persistence.add_batch_results(key, validated_results)
                    print(f"  Validated {len(validated_results)} result(s)")

                    # Mark batch as completed in state
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

        # Write aggregated results to CSV if we have any
        if persistence.aggregated_results:
            output_path = self.config.aggregated_output_path or Path(
                "Documents/verified-llm-categorised-language-check-report.csv"
            )
            persistence.write_aggregated_results(output_path)

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
        """Process and validate a batch response.

        Overrides base method to use load_categorised_issues.
        """
        key = DocumentKey(subject=job_metadata.subject, filename=job_metadata.filename)

        # Use load_categorised_issues instead of load_issues
        grouped_issues = load_categorised_issues(
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
