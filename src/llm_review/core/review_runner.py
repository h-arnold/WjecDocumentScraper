from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from src.language_check.report_utils import build_issue_batch_table
from src.llm.provider import LLMQuotaError
from src.llm.service import LLMService
from src.models import DocumentKey, LanguageIssue

from .batcher import Batch, iter_batches
from .config import ReviewConfiguration
from .document_loader import load_issues
from .persistence import PersistenceManager
from .state_manager import StateManager


class ReviewRunner(ABC):
    """Abstract base class for orchestrating LLM review workflows."""

    def __init__(
        self,
        llm_service: LLMService,
        state: StateManager,
        config: ReviewConfiguration,
    ):
        self.llm_service = llm_service
        self.state = state
        self.config = config

        # Initialize persistence manager
        self.persistence = PersistenceManager(config)

    def run(
        self,
        *,
        force: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Run the review workflow."""
        print(f"Loading issues from {self.config.input_csv_path}...")
        grouped_issues = load_issues(
            self.config.input_csv_path,
            subjects=self.config.subjects,
            documents=self.config.documents,
        )

        if not grouped_issues:
            print("No issues found matching the filters")
            return {"total_documents": 0, "total_batches": 0, "total_issues": 0}

        print(f"Loaded {len(grouped_issues)} document(s) with issues")

        total_batches = 0
        total_issues = 0
        processed_batches = 0
        skipped_batches = 0

        for key, issues in grouped_issues.items():
            print(f"\nProcessing {key} ({len(issues)} issues)...")
            total_issues += len(issues)

            # Get Markdown path - this assumes a standard structure
            # We might need to make this configurable or part of config
            markdown_path = Path("Documents") / key.subject / "markdown" / key.filename

            # Clear state if force mode
            if force:
                self.state.clear_document(key)
                self.persistence.clear_document_results(key)

            # Process batches for this document
            for batch in iter_batches(
                issues,
                self.config.batch_size,
                markdown_path,
                subject=key.subject,
                filename=key.filename,
            ):
                total_batches += 1

                # Check if already completed
                if not force and self.state.is_batch_completed(key, batch.index):
                    print(f"  Batch {batch.index}: Already completed (skipping)")
                    skipped_batches += 1
                    continue

                if dry_run:
                    print(f"  Batch {batch.index}: Dry run (not calling LLM)")
                    continue

                # Process the batch
                success = self._process_batch(key, batch)
                if success:
                    processed_batches += 1
                    self.state.mark_batch_completed(key, batch.index, len(issues))

        print(f"\n{'=' * 60}")
        print("Summary:")
        print(f"  Total documents: {len(grouped_issues)}")
        print(f"  Total batches: {total_batches}")
        print(f"  Processed: {processed_batches}")
        print(f"  Skipped (already done): {skipped_batches}")
        print(f"  Total issues: {total_issues}")
        print(f"{'=' * 60}")

        return {
            "total_documents": len(grouped_issues),
            "total_batches": total_batches,
            "processed_batches": processed_batches,
            "skipped_batches": skipped_batches,
            "total_issues": total_issues,
        }

    def _process_batch(self, key: DocumentKey, batch: Batch) -> bool:
        """Process a single batch with retries."""
        print(f"  Batch {batch.index}: Processing {len(batch.issues)} issue(s)...")

        remaining_issues = batch.issues.copy()
        all_results: dict[int, dict[str, Any]] = {}
        agg_failed_errors: dict[object, list[str]] = {}

        for attempt in range(self.config.max_retries + 1):
            if not remaining_issues:
                break

            if attempt > 0:
                print(
                    f"    Retry {attempt}/{self.config.max_retries} for {len(remaining_issues)} issue(s)"
                )

            # Rebuild batch for retries (updating table)
            retry_batch = Batch(
                subject=batch.subject,
                filename=batch.filename,
                index=batch.index,
                issues=remaining_issues,
                page_context=batch.page_context,
                markdown_table=build_issue_batch_table(remaining_issues),
            )

            prompts = self.build_prompts(retry_batch)

            # Handle system/user prompts
            if len(prompts) > 1:
                user_prompts = prompts[1:]
            else:
                user_prompts = prompts

            response = self._call_llm(user_prompts, key, batch.index, attempt)
            if response is None:
                return False

            self._maybe_log_response(
                key, batch.index, attempt, response, remaining_issues
            )

            validated, failed, errors = self.validate_response(
                response, remaining_issues
            )

            # Collect validated results
            for issue_dict in validated:
                issue_id = (
                    issue_dict.get("issue_id") if isinstance(issue_dict, dict) else None
                )
                if issue_id is not None:
                    try:
                        all_results[int(issue_id)] = issue_dict
                    except (ValueError, TypeError):
                        continue

            # Update remaining issues
            remaining_issues = [i for i in remaining_issues if i.issue_id in failed]

            # Aggregate errors
            for k, msgs in errors.items():
                if msgs:
                    agg_failed_errors.setdefault(k, []).extend(msgs)

            if not remaining_issues:
                print("    All issues validated successfully")
                break

        # Handle failed issues
        if remaining_issues:
            print(
                f"    Warning: {len(remaining_issues)} issue(s) could not be validated"
            )
            try:
                err_path = self.persistence.save_failed_issues(
                    key, batch.index, remaining_issues, error_messages=agg_failed_errors
                )
                print(f"      Saved failed-issues details to {err_path}")
            except Exception as e:
                print(f"      Could not save failed issues: {e}")

        # Persist results
        if all_results:
            try:
                output_path = self.persistence.save_batch_results(
                    key, list(all_results.values()), merge=True
                )
                print(f"    Saved results to {output_path}")
                return True
            except Exception as e:
                print(f"    Error saving results: {e}")
                return False
        else:
            print("    No valid results to save")
            return False

    def _call_llm(
        self, prompts: Sequence[str], key: DocumentKey, batch_index: int, attempt: int
    ) -> Any | None:
        """Call the LLM service."""
        try:
            return self.llm_service.generate(prompts)
        except Exception as e:
            if isinstance(e, LLMQuotaError) and not self.config.fail_on_quota:
                print(f"    Quota exhausted (skipping batch): {e}")
                return None
            print(f"    LLM error: {e}")
            if self.config.fail_on_quota:
                raise
            return None

    def _maybe_log_response(
        self,
        key: DocumentKey,
        batch_index: int,
        attempt: int,
        response: Any,
        issues: list[LanguageIssue],
    ) -> None:
        if not self.config.log_raw_responses:
            return

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_dir = self.config.log_response_dir / key.subject
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = (
            log_dir
            / f"{key.filename}.batch-{batch_index}.try-{attempt}.{timestamp}.json"
        )

        log_data = {
            "timestamp": timestamp,
            "subject": key.subject,
            "filename": key.filename,
            "batch_index": batch_index,
            "attempt": attempt,
            "issues": [i.model_dump() for i in issues],
            "response": response,
        }

        try:
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(log_data, f, indent=2)
        except Exception as e:
            print(f"    Warning: Could not log raw response: {e}")

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
