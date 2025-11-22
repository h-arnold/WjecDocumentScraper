"""Page-based runner for comprehensive document proofreading.

This runner processes entire documents page-by-page instead of only
processing pre-verified issues.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.llm.service import LLMService
from src.models import LanguageIssue, PassCode

from ..core.review_runner import ReviewRunner
from ..core.state_manager import StateManager
from .config import ProofreaderConfiguration
from .page_batcher import PageBatch, iter_page_batches
from .page_data_loader import load_page_based_documents
from .prompt_factory import build_page_prompts


class PageBasedProofreaderRunner(ReviewRunner):
    """Orchestrates page-by-page LLM proofreading workflow."""

    def __init__(
        self,
        llm_service: LLMService,
        state: StateManager,
        *,
        pages_per_batch: int = 3,
        max_retries: int = 2,
        log_raw_responses: bool | None = None,
        log_response_dir: Path | None = None,
        fail_on_quota: bool = True,
    ):
        """Initialize the page-based runner.

        Args:
            llm_service: LLM service for making API calls
            state: State manager for tracking progress
            pages_per_batch: Number of pages per batch (default 3)
            max_retries: Maximum retry attempts for failed validations
            log_raw_responses: Whether to log raw LLM responses
            log_response_dir: Directory for response logs
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

        # Create configuration with page-based output
        config = ProofreaderConfiguration(
            input_csv_path=Path("Documents/language-check-report.csv"),
            output_base_dir=Path("Documents"),
            output_subdir="llm_page_proofreader_reports",
            batch_size=pages_per_batch,
            max_retries=max_retries,
            state_file=Path("data/llm_page_proofreader_state.json"),
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
                "error_category",
                "confidence_score",
                "reasoning",
            ],
        )

        super().__init__(llm_service, state, config)
        self.pages_per_batch = pages_per_batch

        if self.config.log_raw_responses:
            print(f"Raw response logging enabled -> " f"{self.config.log_response_dir}")

    def run(
        self,
        *,
        force: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Run the page-based proofreading workflow.

        Args:
            force: If True, reprocess all batches (ignore state)
            dry_run: If True, only validate data loading (don't call LLM)

        Returns:
            Summary statistics dictionary
        """
        # Load documents with page-based structure
        print("Loading documents for page-based processing...")

        documents_root = Path("Documents")
        existing_report = self.config.input_csv_path

        document_metadata = load_page_based_documents(
            documents_root,
            existing_report if existing_report.exists() else None,
            subjects=self.config.subjects,
            documents=self.config.documents,
        )

        if not document_metadata:
            print("No documents found matching the filters")
            return {"total_documents": 0, "total_batches": 0, "total_pages": 0}

        print(f"Loaded {len(document_metadata)} document(s)")

        total_batches = 0
        total_pages = 0
        processed_batches = 0
        skipped_batches = 0

        for key, metadata in document_metadata.items():
            total_pages += metadata["total_pages"]
            print(
                f"\nProcessing {key.subject}/{key.filename} "
                f"({metadata['total_pages']} pages)..."
            )

            # Clear state if force mode
            if force:
                self.state.clear_document(key)
                self.persistence.clear_document_results(key)

            # Process page batches
            for batch in iter_page_batches(
                metadata,
                self.pages_per_batch,
                metadata["markdown_path"],
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
                success = self._process_page_batch(key, batch)
                if success:
                    processed_batches += 1
                    # Mark batch as complete with page count
                    self.state.mark_batch_completed(
                        key, batch.index, metadata["total_pages"]
                    )

        # Save state after processing
        self.state.save()

        return {
            "total_documents": len(document_metadata),
            "total_batches": total_batches,
            "processed_batches": processed_batches,
            "skipped_batches": skipped_batches,
            "total_pages": total_pages,
        }

    def _process_page_batch(self, key, batch: PageBatch) -> bool:
        """Process a single page batch with retries."""
        print(
            f"  Batch {batch.index}: Pages {batch.page_range[0]}-{batch.page_range[1]}"
        )

        for attempt in range(self.config.max_retries + 1):
            # Build prompts
            prompts = build_page_prompts(batch)

            # Call LLM
            response = self._call_llm(prompts, key, batch.index, attempt)
            if response is None:
                return False

            # Validate response
            validated_results, errors = self._validate_page_response(response, batch)

            if not errors:
                # Success - save results
                self.persistence.append_results(key, validated_results)
                print(f"    Success: {len(validated_results)} new findings")
                return True
            else:
                print(f"    Attempt {attempt + 1}: Validation errors")
                for error in errors[:3]:  # Show first 3 errors
                    print(f"      - {error}")

        print(f"    Failed after {self.config.max_retries + 1} attempts")
        return False

    def build_prompts(self, batch: PageBatch) -> list[str]:
        """Build prompts for a page batch."""
        return build_page_prompts(batch)

    def validate_response(
        self,
        response: Any,
        batch: PageBatch,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Validate LLM response for page-based review.

        Returns:
            Tuple of (validated_results, error_messages)
        """
        return self._validate_page_response(response, batch)

    def _validate_page_response(
        self,
        response: Any,
        batch: PageBatch,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Validate LLM response for a page batch.

        Returns:
            Tuple of (validated_results, error_messages)
        """
        validated_results = []
        errors = []

        # Expect a list of issue objects
        if not isinstance(response, list):
            errors.append("Expected top-level JSON array of objects")
            return validated_results, errors

        if not response:
            # No new issues found - this is valid
            return validated_results, []

        # Process each reported issue
        for item in response:
            if not isinstance(item, dict):
                errors.append("Entry in response array is not a JSON object")
                continue

            try:
                # Validate required fields
                if "page_number" not in item:
                    errors.append("Missing required field: page_number")
                    continue

                # Create a LanguageIssue for the new finding
                new_issue = LanguageIssue(
                    filename=batch.filename,
                    rule_id="LLM_PROOFREADER",
                    message="Issue detected by LLM proofreader",
                    issue_type="proofreading",
                    replacements=[],
                    context=item.get("highlighted_context", ""),
                    highlighted_context=item.get("highlighted_context", ""),
                    issue=item.get("issue", ""),
                    page_number=item.get("page_number"),
                    issue_id=-1,  # Auto-assigned later
                    pass_code=PassCode.LP,
                    error_category=item.get("error_category"),
                    confidence_score=item.get("confidence_score"),
                    reasoning=item.get("reasoning"),
                )

                validated_results.append(new_issue.model_dump())

            except ValidationError as e:
                errors.append(f"Validation error: {e}")
                continue
            except Exception as e:
                errors.append(f"Unexpected error: {e}")
                continue

        return validated_results, errors

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
