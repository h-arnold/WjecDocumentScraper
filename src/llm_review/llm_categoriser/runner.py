"""Orchestrate the LLM categorisation workflow with retries and validation.

This module coordinates the entire process: loading issues, batching, prompting the LLM,
validating responses, handling retries, and persisting results.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.language_check.language_issue import LanguageIssue
from src.llm.service import LLMService
from src.models.document_key import DocumentKey
from src.models.issue import LlmLanguageIssue

from .batcher import Batch, iter_batches
from .data_loader import load_issues
from .persistence import save_batch_results
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
        all_results: dict[str, list[dict[str, Any]]] = {}
        
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
            
            # Enforce rate limiting
            self._enforce_rate_limit()
            
            # Call LLM
            try:
                response = self.llm_service.generate(prompts, filter_json=True)
            except Exception as e:
                print(f"    Error calling LLM: {e}")
                return False
            
            # Validate and collect results
            validated, failed = self._validate_response(response, remaining_issues)
            
            # Add validated results to our collection
            for page_key, page_issues in validated.items():
                if page_key in all_results:
                    # Avoid adding duplicate issues by issue_id
                    existing_ids = {issue.issue_id for issue in all_results[page_key]}
                    new_issues = [issue for issue in page_issues if issue.issue_id not in existing_ids]
                    all_results[page_key].extend(new_issues)
                else:
                    all_results[page_key] = list(page_issues)
            
            # Update remaining issues for next retry
            remaining_issues = [issue for issue in remaining_issues if issue.issue_id in failed]
            
            if not remaining_issues:
                print(f"    All issues validated successfully")
                break
        
        # Log any issues that couldn't be validated
        if remaining_issues:
            print(f"    Warning: {len(remaining_issues)} issue(s) could not be validated after {self.max_retries} retries")
            for issue in remaining_issues:
                print(f"      - Issue #{issue.issue_id}: {issue.rule_id}")
        
        # Persist results
        if all_results:
            try:
                output_path = save_batch_results(key, all_results, merge=True)
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
    ) -> tuple[dict[str, list[dict[str, Any]]], set[int]]:
        """Validate LLM response and return validated results plus failed issue IDs.
        
        Args:
            response: Parsed JSON response from LLM
            issues: List of issues that were in the prompt
            
        Returns:
            Tuple of (validated_results, failed_issue_ids)
            validated_results: Dict mapping page keys to lists of valid issue dicts
            failed_issue_ids: Set of issue_id values that failed validation
        """
        validated_results: dict[str, list[dict[str, Any]]] = {}
        failed_issue_ids: set[int] = set(issue.issue_id for issue in issues)
        
        if not isinstance(response, dict):
            print(f"    Error: Response is not a dict (got {type(response)})")
            return validated_results, failed_issue_ids
        
        # Process each page in the response
        for page_key, page_issues in response.items():
            if not isinstance(page_issues, list):
                print(f"    Warning: Page '{page_key}' value is not a list")
                continue
            
            valid_issues = []
            for issue_dict in page_issues:
                try:
                    # Validate using Pydantic model
                    validated = LlmLanguageIssue(**issue_dict)
                    valid_issues.append(validated.model_dump())
                    
                    # Try to identify which input issue this corresponds to
                    # Match by rule_from_tool and context_from_tool
                    # Match by issue_id for 1:1 correspondence
                    if hasattr(validated, "issue_id"):
                        failed_issue_ids.discard(validated.issue_id)
                    else:
                        print(f"    Warning: LLM response issue missing 'issue_id' field.")
                    
                except ValidationError as e:
                    print(f"    Warning: Validation error for issue in '{page_key}': {e}")
                    continue
                except Exception as e:
                    print(f"    Warning: Unexpected error validating issue: {e}")
                    continue
            
            if valid_issues:
                validated_results[page_key] = valid_issues
        
        return validated_results, failed_issue_ids
    
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
