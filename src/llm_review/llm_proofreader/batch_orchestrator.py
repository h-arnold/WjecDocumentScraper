"""Batch orchestrator for LLM proofreading using Gemini Batch API.

This module provides functionality to create and retrieve batch jobs for
asynchronous processing of proofreading issues through the Gemini batch API.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from src.llm.service import LLMService
from src.models import LanguageIssue, PassCode

from ..core.batch_orchestrator import Batch, BatchOrchestrator
from ..core.state_manager import StateManager
from .config import ProofreaderConfiguration
from .data_loader import load_proofreader_issues
from .prompt_factory import build_prompts as build_prompt_templates


class ProofreaderBatchOrchestrator(BatchOrchestrator):
    """Orchestrates batch processing for proofreader."""

    def __init__(
        self,
        llm_service: LLMService,
        tracker: Any,  # BatchJobTracker
        state: StateManager,
        config: ProofreaderConfiguration,
    ):
        """Initialize the orchestrator.

        Args:
            llm_service: LLM service for making batch API calls
            tracker: Job tracker for managing batch job metadata
            state: State manager for tracking progress
            config: Configuration for the proofreader
        """
        super().__init__(llm_service, tracker, state, config)

    def build_prompts(self, batch: Batch) -> list[str]:
        """Build prompts for the LLM.

        Args:
            batch: Batch of issues to process

        Returns:
            List of prompts (system prompt, then user prompt)
        """
        return build_prompt_templates(batch)

    def validate_response(
        self,
        response: Any,
        issues: list[LanguageIssue],
    ) -> tuple[list[dict[str, Any]], set[int], dict[object, list[str]]]:
        """Validate LLM response and return validated results, failed ids and error messages.

        Args:
            response: The raw LLM response
            issues: List of issues in the batch

        Returns:
            Tuple of (validated_results, failed_issue_ids, error_messages)
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

        # Build a map of original issues indexed by issue_id for merging LLM
        # proofreading results with the existing detection fields.
        issue_map = {issue.issue_id: issue for issue in issues}

        # Process the flat response list
        for issue_dict in response:
            # Only accept dictionaries
            if not isinstance(issue_dict, dict):
                warn = "Entry in response array is not a JSON object"
                error_messages.setdefault("batch_errors", []).append(warn)
                continue

            try:
                iid = issue_dict.get("issue_id")

                if iid is not None and iid in issue_map:
                    # Merge proofreader results into the original detection
                    # issue so we end up with a fully-populated LanguageIssue.
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
                        "pass_code": PassCode.LP,
                        # LLM fields
                        "error_category": issue_dict.get("error_category"),
                        "confidence_score": issue_dict.get("confidence_score"),
                        "reasoning": issue_dict.get("reasoning"),
                    }
                    validated = LanguageIssue(**merged)
                else:
                    # Fall back to creating from full LLM response mapping
                    validated = LanguageIssue.from_llm_response(
                        issue_dict, filename=filename
                    )
                    # Ensure pass_code is LP
                    validated = validated.model_copy(update={"pass_code": PassCode.LP})

                validated_results.append(validated.model_dump())

                # If the LLM supplied an explicit issue_id, mark it as validated.
                if validated.issue_id >= 0:
                    failed_issue_ids.discard(validated.issue_id)

            except ValidationError as e:
                iid = issue_dict.get("issue_id")
                if iid is not None:
                    error_messages.setdefault(iid, []).append(str(e))
                else:
                    error_messages.setdefault("batch_errors", []).append(str(e))
                continue
            except Exception as e:
                iid = issue_dict.get("issue_id")
                if iid is not None:
                    error_messages.setdefault(iid, []).append(str(e))
                else:
                    error_messages.setdefault("batch_errors", []).append(str(e))
                continue

        if not validated_results:
            msg = "Response contained no valid issue objects"
            error_messages.setdefault("batch_errors", []).append(msg)

        return validated_results, failed_issue_ids, error_messages

    def _process_batch_response(
        self,
        response: Any,
        job_metadata: Any,  # BatchJobMetadata
    ) -> list[dict[str, Any]]:
        """Process and validate a batch response using proofreader data loader.

        Args:
            response: The LLM response to validate
            job_metadata: Metadata about the batch job

        Returns:
            List of validated issue dictionaries
        """
        from src.models import DocumentKey

        key = DocumentKey(subject=job_metadata.subject, filename=job_metadata.filename)
        grouped_issues = load_proofreader_issues(
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

    def create_batch_jobs(
        self,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        """Create batch jobs for all document batches using proofreader data loader.

        This override ensures that only SPELLING_ERROR and ABSOLUTE_GRAMMATICAL_ERROR
        issues are included in batch jobs.

        Args:
            force: If True, create jobs even for already-completed batches

        Returns:
            Dictionary with job creation statistics
        """
        from pathlib import Path

        from ..core.batcher import iter_batches

        print(f"Loading issues from {self.config.input_csv_path}...")
        grouped_issues = load_proofreader_issues(
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

            # Convert CSV filename to MD for markdown path
            md_filename = key.filename
            if md_filename.endswith(".csv"):
                md_filename = md_filename[:-4] + ".md"
            elif not md_filename.endswith(".md"):
                md_filename = md_filename + ".md"

            markdown_path = Path("Documents") / key.subject / "markdown" / md_filename

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

                # Build prompts
                prompts = self.build_prompts(batch)

                # Create batch job
                try:
                    job_name = self.llm_service.create_batch_job(
                        prompts,
                        metadata={
                            "subject": key.subject,
                            "filename": key.filename,
                            "batch_index": batch.index,
                        },
                    )

                    # Track the job
                    from datetime import datetime, timezone

                    from ..core.batch_orchestrator import BatchJobMetadata

                    job_metadata = BatchJobMetadata(
                        provider_name=self.llm_service.providers[0].name,
                        job_name=job_name,
                        subject=key.subject,
                        filename=key.filename,
                        batch_index=batch.index,
                        issue_ids=[i.issue_id for i in batch.issues],
                        created_at=datetime.now(timezone.utc).isoformat(),
                        status="pending",
                    )
                    self.tracker.add_job(job_metadata)

                    print(f"  Batch {batch.index}: Created job {job_name[:16]}...")
                    created_jobs += 1

                except Exception as e:
                    print(f"  Batch {batch.index}: Failed to create job - {e}")
                    continue

        print(f"\n{'=' * 60}")
        print("Summary:")
        print(f"  Total documents: {len(grouped_issues)}")
        print(f"  Total batches: {total_batches}")
        print(f"  Created jobs: {created_jobs}")
        print(f"  Skipped (already done): {skipped_batches}")
        print(f"{'=' * 60}")

        return {
            "total_documents": len(grouped_issues),
            "total_batches": total_batches,
            "created_jobs": created_jobs,
            "skipped_batches": skipped_batches,
        }
