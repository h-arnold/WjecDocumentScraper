"""Orchestrate the LLM categorisation workflow with retries and validation.

This module coordinates the entire process: loading issues, batching, prompting the LLM,
validating responses, handling retries, and persisting results.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
import os
import json
from datetime import datetime, timezone

from pydantic import ValidationError

from src.models import LanguageIssue, DocumentKey
from src.llm.service import LLMService

from .batcher import Batch, iter_batches
from .data_loader import load_issues
from .persistence import save_batch_results, save_failed_issues
from .prompt_factory import build_prompts
from .state import CategoriserState


class CategoriserRunner:
    """Orchestrates the LLM categorisation workflow."""
    
    def __init__(
        self,
        llm_service: LLMService,
        state: CategoriserState,
        *,
        batch_size: int = 10,
        max_retries: int = 2,
        min_request_interval: float = 0.0,
        log_raw_responses: bool | None = None,
        log_response_dir: Path | None = None,
    ):
        """Initialize the runner.
        
        Args:
            llm_service: LLM service for making API calls
            state: State manager for tracking progress
            batch_size: Number of issues per batch
            max_retries: Maximum retry attempts for failed validations
            min_request_interval: Minimum seconds between API requests
        """
        self.llm_service = llm_service
        self.state = state
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.min_request_interval = min_request_interval
        if log_raw_responses is None:
            env_flag = os.environ.get("LLM_CATEGORISER_LOG_RESPONSES", "")
            log_raw_responses = env_flag.strip().lower() in {"1", "true", "yes", "on"}
        self.log_raw_responses = log_raw_responses
        if log_response_dir is None:
            log_response_dir = Path(os.environ.get("LLM_CATEGORISER_LOG_DIR", "data/llm_categoriser_responses"))
        self.log_response_dir = Path(log_response_dir)
        if self.log_raw_responses:
            print(
                "Raw response logging enabled -> "
                f"{self.log_response_dir} (subject folders will be created automatically)"
            )
        # Initialize to 0.0 so that the first API call is not rate-limited.
        # This ensures the first request does not sleep; subsequent requests will enforce the interval.
        self._last_request_time = 0.0
    
    def run(
        self,
        report_path: Path,
        *,
        subjects: set[str] | None = None,
        documents: set[str] | None = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Run the categorisation workflow.
        
        Args:
            report_path: Path to language-check-report.csv
            subjects: Optional subject filter
            documents: Optional document filter
            force: If True, reprocess all batches (ignore state)
            dry_run: If True, only validate data loading (don't call LLM)
            
        Returns:
            Summary statistics dictionary
        """
        print(f"Loading issues from {report_path}...")
        grouped_issues = load_issues(report_path, subjects=subjects, documents=documents)
        
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
            
            # Get Markdown path
            markdown_path = Path("Documents") / key.subject / "markdown" / key.filename
            
            # Clear state if force mode
            if force:
                self.state.clear_document(key)
                from .persistence import clear_document_results
                clear_document_results(key)
            
            # Process batches for this document
            for batch in iter_batches(
                issues,
                self.batch_size,
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
        print(f"Summary:")
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
        """Process a single batch with retries.
        
        Returns:
            True if batch was successfully processed and persisted
        """
        print(f"  Batch {batch.index}: Processing {len(batch.issues)} issue(s)...")
        
        remaining_issues = batch.issues.copy()
        all_results: dict[int, dict[str, Any]] = {}

        agg_failed_errors: dict[object, list[str]] = {}

        for attempt in range(self.max_retries + 1):
            if not remaining_issues:
                break
            
            if attempt > 0:
                print(f"    Retry {attempt}/{self.max_retries} for {len(remaining_issues)} issue(s)")
            
            # Build prompts for remaining issues
            retry_batch = Batch(
                subject=batch.subject,
                filename=batch.filename,
                index=batch.index,
                issues=remaining_issues,
                page_context=batch.page_context,
                markdown_table=self._build_table_for_issues(remaining_issues),
            )
            
            prompts = build_prompts(retry_batch)
            # build_prompts returns [system_prompt, user_prompt] when available.
            # The system prompt is provided to the provider chain during creation,
            # so we must only send user (content) prompts to the provider.
            if len(prompts) > 1:
                user_prompts = prompts[1:]
            else:
                user_prompts = prompts
            
            # Enforce rate limiting
            self._enforce_rate_limit()
            
            # Call LLM
            try:
                response = self.llm_service.generate(user_prompts, filter_json=True)
            except Exception as e:
                print(f"    Error calling LLM: {e}")
                return False

            self._maybe_log_response(key, batch.index, attempt, response, remaining_issues)
            
            # Validate and collect results
            validated, failed, errors = self._validate_response(response, remaining_issues)

            # Add validated results to our collection, deduplicating by issue_id
            for issue_dict in validated:
                issue_id = issue_dict.get("issue_id") if isinstance(issue_dict, dict) else None
                if issue_id is None:
                    continue
                try:
                    iid_int = int(issue_id)
                except Exception:
                    continue
                all_results[iid_int] = issue_dict
            
            # Update remaining issues for next retry
            remaining_issues = [issue for issue in remaining_issues if issue.issue_id in failed]

            # Aggregate errors for later use
            # errors is a mapping of issue_id or 'batch_errors' -> list[str]
            for k, msgs in errors.items():
                if msgs:
                    agg_failed_errors.setdefault(k, []).extend(msgs)
            
            if not remaining_issues:
                print(f"    All issues validated successfully")
                break
        
        # Log any issues that couldn't be validated
        if remaining_issues:
            print(f"    Warning: {len(remaining_issues)} issue(s) could not be validated after {self.max_retries} retries")
            for issue in remaining_issues:
                print(f"      - Issue #{issue.issue_id}: {issue.rule_id}")
            # Save details to data directory for debugging
            try:
                err_path = save_failed_issues(key, batch.index, remaining_issues, error_messages=agg_failed_errors)
                # Print a short summary of the errors saved
                total_errors = sum(len(msgs) for msgs in agg_failed_errors.values())
                print(f"      Saved failed-issues details to {err_path} ({total_errors} messages)")
            except Exception as e:
                print(f"      Could not save failed issues: {e}")
        
        # Persist results
        if all_results:
            try:
                output_path = save_batch_results(key, list(all_results.values()), merge=True)
                print(f"    Saved results to {output_path}")
                return True
            except Exception as e:
                print(f"    Error saving results: {e}")
                return False
        else:
            print(f"    No valid results to save")
            return False
    
    def _validate_response(
        self,
        response: Any,
        issues: list[LanguageIssue],
    ) -> tuple[list[dict[str, Any]], set[int], dict[object, list[str]]]:
        """Validate LLM response and return validated results, failed ids and error messages.

        Returns:
            (validated_results, failed_issue_ids, error_messages)
        """
        validated_results: list[dict[str, Any]] = []
        failed_issue_ids: set[int] = set(issue.issue_id for issue in issues)

        # Map of issue ids or 'batch_errors' to lists of messages
        error_messages: dict[object, list[str]] = {issue.issue_id: [] for issue in issues}
        error_messages.setdefault("batch_errors", [])

        # Only accept a top-level JSON array of objects from the LLM.
        # Minimal validation: ensure top-level is a list, each entry is a JSON
        # object, then try to create a LanguageIssue for each entry. Any
        # ValidationError raised by Pydantic will be reported and the issue
        # will remain in the failed set.
        if not isinstance(response, list):
            msg = "Expected top-level JSON array of objects"
            print(f"    Error: {msg}")
            error_messages.setdefault("batch_errors", []).append(msg)
            return validated_results, failed_issue_ids, error_messages

        # Get filename from first issue (all issues in a batch are from same document)
        filename = issues[0].filename if issues else ""

        if not response:
            msg = "Response is empty; no issues to validate"
            print(f"    Warning: {msg}")
            error_messages.setdefault("batch_errors", []).append(msg)
            return validated_results, failed_issue_ids, error_messages

        # Build a map of original issues indexed by issue_id for merging LLM
        # categorisation with the existing detection fields.
        issue_map = {issue.issue_id: issue for issue in issues}

        # Process the flat response list
        for issue_dict in response:
            # Only accept dictionaries
            if not isinstance(issue_dict, dict):
                warn = "Entry in response array is not a JSON object"
                print(f"    Warning: {warn}")
                error_messages.setdefault("batch_errors", []).append(warn)
                continue

            # Try to construct a LanguageIssue from the LLM response. When the
            # LLM returns only categorisation fields (no tool fields), we
            # merge those fields into the original LanguageIssue for the
            # final stored result. This ensures the resulting object has the
            # detection fields present.
            try:
                iid = issue_dict.get("issue_id") if isinstance(issue_dict, dict) else None

                if iid is not None and iid in issue_map:
                    # Merge categoriser results into the original detection
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
                        # LLM fields
                        "error_category": issue_dict.get("error_category"),
                        "confidence_score": issue_dict.get("confidence_score"),
                        "reasoning": issue_dict.get("reasoning"),
                    }
                    validated = LanguageIssue(**merged)
                else:
                    # Fall back to creating from full LLM response mapping
                    validated = LanguageIssue.from_llm_response(issue_dict, filename=filename)
                validated_results.append(validated.model_dump())

                # If the LLM supplied an explicit issue_id, mark it as validated.
                if validated.issue_id >= 0:
                    failed_issue_ids.discard(validated.issue_id)

            except ValidationError as e:
                # Validation errors are expected when required detection fields
                # are missing — attach the message to the specific issue id if
                # present, otherwise add to batch-level errors.
                iid = issue_dict.get("issue_id") if isinstance(issue_dict, dict) else None
                if iid is not None:
                    error_messages.setdefault(iid, []).append(str(e))
                else:
                    error_messages.setdefault("batch_errors", []).append(str(e))
                continue
            except Exception as e:
                iid = issue_dict.get("issue_id") if isinstance(issue_dict, dict) else None
                if iid is not None:
                    error_messages.setdefault(iid, []).append(str(e))
                else:
                    error_messages.setdefault("batch_errors", []).append(str(e))
                continue
        if not validated_results:
            msg = "Response contained no valid issue objects"
            error_messages.setdefault("batch_errors", []).append(msg)

        return validated_results, failed_issue_ids, error_messages

    @staticmethod
    def _is_page_grouped_response(response: dict[Any, Any]) -> bool:
        """Return True if the dict looks like the legacy page-keyed format."""
        if not response:
            return False
        return all(isinstance(value, list) for value in response.values())

    @staticmethod
    def _looks_like_issue_payload(response: Any) -> bool:
        """Return True if the object appears to be a single-issue payload."""
        if not isinstance(response, dict):
            return False
        required_keys = {"issue_id", "error_category", "confidence_score", "reasoning"}
        return any(key in response for key in required_keys)

    def _maybe_log_response(
        self,
        key: DocumentKey,
        batch_index: int,
        attempt: int,
        response: Any,
        issues: list[LanguageIssue],
    ) -> None:
        if not self.log_raw_responses:
            return
        try:
            self._log_raw_response(key, batch_index, attempt, response, issues)
        except Exception as exc:
            print(f"    Warning: Could not log raw response: {exc}")

    def _log_raw_response(
        self,
        key: DocumentKey,
        batch_index: int,
        attempt: int,
        response: Any,
        issues: list[LanguageIssue],
    ) -> None:
        subject_dir = self.log_response_dir / key.subject
        subject_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = key.filename.replace("/", "-")
        current_time = datetime.now(timezone.utc)
        timestamp = current_time.strftime("%Y%m%dT%H%M%S%fZ")
        output_file = subject_dir / f"{safe_filename}.batch-{batch_index}.attempt-{attempt}.{timestamp}.json"

        payload = {
            "timestamp": current_time.isoformat().replace("+00:00", "Z"),
            "subject": key.subject,
            "filename": key.filename,
            "batch_index": batch_index,
            "attempt": attempt,
            "issue_ids": [issue.issue_id for issue in issues],
            "response": response,
        }

        with open(output_file, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, default=self._fallback_json_serializer)

    @staticmethod
    def _fallback_json_serializer(obj: Any) -> str:
        return str(obj)
    
    def _enforce_rate_limit(self) -> None:
        """Enforce minimum interval between API requests."""
        if self.min_request_interval <= 0:
            return
        
        elapsed = time.time() - self._last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    def _build_table_for_issues(self, issues: list[LanguageIssue]) -> str:
        """Build a Markdown table for a subset of issues."""
        from src.language_check.report_utils import build_issue_batch_table
        return build_issue_batch_table(issues)
