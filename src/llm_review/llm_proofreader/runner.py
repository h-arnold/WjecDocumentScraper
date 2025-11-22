"""Orchestrate the LLM proofreading workflow with retries and validation.

This module coordinates the entire process: loading issues, batching, prompting the LLM,
validating responses, handling retries, and persisting results.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.llm.service import LLMService
from src.models import DocumentKey, LanguageIssue, PassCode

from ..core.batcher import Batch
from ..core.review_runner import ReviewRunner
from ..core.state_manager import StateManager
from .config import ProofreaderConfiguration
from .prompt_factory import build_prompts


class ProofreaderRunner(ReviewRunner):
    """Orchestrates the LLM proofreading workflow."""

    def __init__(
        self,
        llm_service: LLMService,
        state: StateManager,
        *,
        batch_size: int = 10,
        max_retries: int = 2,
        log_raw_responses: bool | None = None,
        log_response_dir: Path | None = None,
        fail_on_quota: bool = True,
    ):
        """Initialize the runner.

        Args:
            llm_service: LLM service for making API calls
            state: State manager for tracking progress
            batch_size: Number of issues per batch
            max_retries: Maximum retry attempts for failed validations
            log_raw_responses: Whether to log raw LLM responses (None = read from env)
            log_response_dir: Directory for response logs (None = use default)
            fail_on_quota: Whether to abort on quota exhaustion
        """
        # Handle environment variable defaults
        if log_raw_responses is None:
            env_flag = os.environ.get("LLM_PROOFREADER_LOG_RESPONSES", "")
            log_raw_responses = env_flag.strip().lower() in {"1", "true", "yes", "on"}

        if log_response_dir is None:
            log_response_dir = Path(
                os.environ.get(
                    "LLM_PROOFREADER_LOG_DIR", "data/llm_proofreader_responses"
                )
            )

        # Create a configuration object for the parent class
        config = ProofreaderConfiguration(
            input_csv_path=Path(
                "Documents/verified-llm-categorised-language-check-report.csv"
            ),
            output_base_dir=Path("Documents"),
            output_subdir="llm_proofreader_reports",
            batch_size=batch_size,
            max_retries=max_retries,
            state_file=Path("data/llm_proofreader_state.json"),
            subjects=None,
            documents=None,
            llm_provider=None,
            fail_on_quota=fail_on_quota,
            log_raw_responses=log_raw_responses,
            log_response_dir=Path(log_response_dir),
            output_csv_columns=[
                "issue_id",
                "page_number",
                "issue",
                "highlighted_context",
                "pass_code",
                "error_category",
                "confidence_score",
                "reasoning",
            ],
        )

        super().__init__(llm_service, state, config)

        if self.config.log_raw_responses:
            print(
                f"Raw response logging enabled -> "
                f"{self.config.log_response_dir} (subject folders will be created automatically)"
            )

        # Track sequential issue IDs per document so we can assign them after validation
        self._next_issue_id: dict[DocumentKey, int] = {}
        self._active_document_key: DocumentKey | None = None

    def run(
        self,
        *,
        force: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Run the proofreading workflow.

        Args:
            force: If True, reprocess all batches (ignore state)
            dry_run: If True, only validate data loading (don't call LLM)

        Returns:
            Summary statistics dictionary
        """
        # Import here to avoid circular import
        from ..core.batcher import iter_batches
        from .data_loader import load_proofreader_issues

        # Load issues using custom loader that filters error categories
        print(f"Loading issues from {self.config.input_csv_path}...")
        grouped_issues = load_proofreader_issues(
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

            # Ensure issue-id counter is initialised for this document
            self._initialise_issue_counter(key, reset=force)

            # Get Markdown path - convert .csv extension to .md if needed
            md_filename = key.filename
            if md_filename.endswith(".csv"):
                md_filename = md_filename[:-4] + ".md"
            elif not md_filename.endswith(".md"):
                md_filename = md_filename + ".md"

            markdown_path = Path("Documents") / key.subject / "markdown" / md_filename

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

        # Save state after processing
        self.state.save()

        return {
            "total_documents": len(grouped_issues),
            "total_batches": total_batches,
            "processed_batches": processed_batches,
            "skipped_batches": skipped_batches,
            "total_issues": total_issues,
        }

    def build_prompts(self, batch: Batch) -> list[str]:
        """Build prompts for the LLM.

        Args:
            batch: Batch of issues to process

        Returns:
            List of prompts (system prompt if applicable, then user prompts)
        """
        return build_prompts(batch)

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
        document_key = self._active_document_key
        if document_key is None:
            raise RuntimeError(
                "ProofreaderRunner.validate_response called without active document context"
            )

        self._ensure_issue_counter(document_key)

        validated_results: list[dict[str, Any]] = []
        failed_issue_ids: set[int] = {issue.issue_id for issue in issues}

        # Map of issue ids or 'batch_errors' to lists of messages
        error_messages: dict[object, list[str]] = {"batch_errors": []}
        for issue in issues:
            error_messages.setdefault(issue.issue_id, [])

        # Only accept a top-level JSON array of objects from the LLM.
        if not isinstance(response, list):
            msg = "Expected top-level JSON array of objects"
            print(f"    Error: {msg}")
            error_messages.setdefault("batch_errors", []).append(msg)
            return validated_results, failed_issue_ids, error_messages

        # Remember starting counter so we can roll back if validation fails
        starting_counter = self._next_issue_id[document_key]
        had_errors = False

        # Get filename from the active context or fallback to first issue
        fallback_filename = (
            document_key.filename
            if document_key is not None
            else (issues[0].filename if issues else "")
        )

        # Process the flat response list
        for index, issue_dict in enumerate(response):
            # Only accept dictionaries
            if not isinstance(issue_dict, dict):
                warn = "Entry in response array is not a JSON object"
                print(f"    Warning: {warn}")
                error_messages.setdefault("batch_errors", []).append(warn)
                had_errors = True
                continue

            original_issue = issues[index] if index < len(issues) else None

            try:
                merged = self._build_validated_issue_payload(
                    issue_dict,
                    original_issue,
                    fallback_filename,
                )

                validated = LanguageIssue(**merged)
                assigned_id = self._assign_issue_id(document_key)
                validated = validated.model_copy(update={"issue_id": assigned_id})
                validated_results.append(validated.model_dump())

            except ValidationError as e:
                had_errors = True
                target_key = (
                    original_issue.issue_id if original_issue else "batch_errors"
                )
                error_messages.setdefault(target_key, []).append(str(e))
                continue
            except Exception as e:
                had_errors = True
                target_key = (
                    original_issue.issue_id if original_issue else "batch_errors"
                )
                error_messages.setdefault(target_key, []).append(str(e))
                continue

        if had_errors:
            # Roll back counter so IDs remain contiguous on retry
            self._next_issue_id[document_key] = starting_counter
            validated_results = []
        else:
            failed_issue_ids.clear()

        return validated_results, failed_issue_ids, error_messages

    def _initialise_issue_counter(
        self, key: DocumentKey, *, reset: bool = False
    ) -> None:
        """Ensure the next issue-id counter is ready for a document."""
        if reset:
            self._next_issue_id[key] = 0
            return

        if key in self._next_issue_id:
            return

        existing_rows = self.persistence.load_document_results(key)
        next_index = 0
        if existing_rows:
            for row in existing_rows:
                raw_id = row.get("issue_id") if isinstance(row, dict) else None
                if raw_id is None or str(raw_id).strip() == "":
                    continue
                try:
                    next_index = max(next_index, int(raw_id) + 1)
                except ValueError:
                    continue

        self._next_issue_id[key] = next_index

    def _ensure_issue_counter(self, key: DocumentKey) -> None:
        if key not in self._next_issue_id:
            self._initialise_issue_counter(key)

    def _assign_issue_id(self, key: DocumentKey) -> int:
        self._ensure_issue_counter(key)
        next_id = self._next_issue_id[key]
        self._next_issue_id[key] = next_id + 1
        return next_id

    def _build_validated_issue_payload(
        self,
        llm_issue: dict[str, Any],
        original_issue: LanguageIssue | None,
        fallback_filename: str,
    ) -> dict[str, Any]:
        """Merge LLM fields with detection metadata for validation."""

        def _get_page_number() -> int | None:
            raw = llm_issue.get("page_number")
            if raw is None:
                return original_issue.page_number if original_issue else None
            try:
                return int(raw)
            except (TypeError, ValueError):
                raise ValueError("page_number must be an integer if provided")

        return {
            "filename": (
                original_issue.filename if original_issue else fallback_filename
            ),
            "rule_id": original_issue.rule_id if original_issue else "LLM_PROOFREADER",
            "message": (
                original_issue.message
                if original_issue
                else "Issue detected by LLM proofreader"
            ),
            "issue_type": (
                original_issue.issue_type if original_issue else "proofreading"
            ),
            "replacements": original_issue.replacements if original_issue else [],
            "context": llm_issue.get("highlighted_context")
            or (original_issue.context if original_issue else ""),
            "highlighted_context": llm_issue.get("highlighted_context")
            or (original_issue.highlighted_context if original_issue else ""),
            "issue": llm_issue.get("issue")
            or (original_issue.issue if original_issue else ""),
            "page_number": _get_page_number(),
            "issue_id": original_issue.issue_id if original_issue else -1,
            "pass_code": PassCode.LP,
            "error_category": llm_issue.get("error_category")
            or (original_issue.error_category if original_issue else None),
            "confidence_score": llm_issue.get("confidence_score")
            or (original_issue.confidence_score if original_issue else None),
            "reasoning": llm_issue.get("reasoning")
            or (original_issue.reasoning if original_issue else None),
        }

    def _process_batch(self, key: DocumentKey, batch: Batch) -> bool:
        """Set active document context before delegating to base implementation."""
        self._active_document_key = key
        self._ensure_issue_counter(key)
        try:
            return super()._process_batch(key, batch)
        finally:
            self._active_document_key = None

    def _call_llm(self, prompts: list[str], key, batch_index: int, attempt: int):
        """Override parent to add filter_json=True for proofreader."""
        from src.llm.provider import LLMQuotaError

        try:
            return self.llm_service.generate(prompts, filter_json=True)
        except Exception as e:
            if isinstance(e, LLMQuotaError) and not self.config.fail_on_quota:
                print(f"    Quota exhausted (skipping batch): {e}")
                return None
            print(f"    LLM error: {e}")
            if self.config.fail_on_quota:
                raise
            return None
