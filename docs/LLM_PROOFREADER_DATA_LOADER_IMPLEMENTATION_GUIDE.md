# LLM Proofreader Data Loader Implementation Guide

## Overview

This guide provides detailed step-by-step instructions for modifying the `llm_proofreader` data loader to process **every page from every document** instead of only processing pre-verified issues. The new system will:

1. **Load all document pages**: Process entire documents page-by-page regardless of whether issues have been detected
2. **Include pre-existing issues as context**: Display previously detected issues in the prompt to avoid duplicate reporting

## Current System Architecture

### Current Data Flow (Before Modifications)

```
verified-llm-categorised-language-check-report.csv
    ↓
load_proofreader_issues() 
    ↓ (filters by error_category)
Grouped by DocumentKey
    ↓
iter_batches() - groups issues into batches
    ↓
build_prompts() - creates prompts with issue table + page context
    ↓
LLM Review
```

### Current Limitations

1. **Issue-driven**: Only processes pages that have detected issues
2. **No coverage for clean pages**: Pages without issues are never reviewed
3. **Filtering constraint**: Only SPELLING_ERROR and ABSOLUTE_GRAMMATICAL_ERROR categories are processed
4. **Incomplete review**: Misses contextual errors on pages that passed initial checks

## New System Architecture

### New Data Flow (After Modifications)

```
Documents/<subject>/markdown/*.md files
    ↓
load_all_document_pages()
    ↓ (reads page markers, loads pre-existing issues)
Grouped by DocumentKey with full page coverage
    ↓
iter_page_batches() - creates batches by page ranges
    ↓
build_prompts() - creates prompts with:
    - Full page content
    - Pre-existing issues as "already flagged" context
    ↓
LLM Review
```

### Key Design Decisions

1. **Page-centric batching**: Instead of batching by issues, batch by page ranges (e.g., 5-10 pages per batch)
2. **Pre-existing issues as context**: Load issues from existing reports and display them as "Ignore - already flagged" sections
3. **Full document coverage**: Every page is reviewed, even if no issues were previously detected
4. **Maintain backward compatibility**: Keep the existing `load_proofreader_issues()` for potential future use

## Implementation Steps

### Step 1: Create New Data Loader Module

**File**: `src/llm_review/llm_proofreader/page_data_loader.py`

This new module will handle page-based loading instead of issue-based loading.

```python
"""Load documents page-by-page for comprehensive proofreading.

This module provides an alternative to the issue-based loader that processes
every page from every document, including pre-existing issues as context.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Generator

from src.models import DocumentKey, LanguageIssue, PassCode
from src.utils.page_utils import find_page_markers


def load_page_based_documents(
    documents_root: Path,
    existing_report_path: Path | None = None,
    *,
    subjects: set[str] | None = None,
    documents: set[str] | None = None,
) -> dict[DocumentKey, dict]:
    """Load all documents with page-by-page structure and pre-existing issues.
    
    This loader processes entire documents page-by-page, regardless of whether
    issues have been detected. Pre-existing issues are loaded from the language
    check report and provided as context for each page.
    
    Args:
        documents_root: Path to Documents/ directory containing subject folders
        existing_report_path: Path to language-check-report.csv (optional)
        subjects: Optional set of subject filters (case-insensitive)
        documents: Optional set of document filters (case-insensitive)
    
    Returns:
        Dictionary mapping DocumentKey to dict with:
            - markdown_path: Path to the markdown file
            - total_pages: Total number of pages in document
            - page_numbers: List of page numbers
            - pre_existing_issues: Dict mapping page_number -> list[LanguageIssue]
    """
    # Step 1: Find all markdown documents
    all_documents = _discover_markdown_documents(
        documents_root,
        subjects=subjects,
        documents=documents,
    )
    
    # Step 2: Load pre-existing issues if available
    existing_issues = {}
    if existing_report_path and existing_report_path.exists():
        existing_issues = _load_existing_issues(existing_report_path)
    
    # Step 3: Build document metadata with page information
    result = {}
    for subject, markdown_path in all_documents:
        key = DocumentKey(subject=subject, filename=markdown_path.name)
        
        # Read markdown content and extract page information
        try:
            content = markdown_path.read_text(encoding="utf-8")
            page_markers = find_page_markers(content)
            
            # Get page numbers (or use 0 for documents without markers)
            if page_markers:
                page_numbers = sorted([marker.page_number for marker in page_markers])
            else:
                page_numbers = [0]  # Whole document as page 0
            
            # Filter pre-existing issues for this document
            doc_issues = existing_issues.get(key, [])
            issues_by_page = _group_issues_by_page(doc_issues)
            
            result[key] = {
                "markdown_path": markdown_path,
                "total_pages": len(page_numbers),
                "page_numbers": page_numbers,
                "pre_existing_issues": issues_by_page,
            }
            
        except (OSError, UnicodeDecodeError) as e:
            print(f"Warning: Failed to read {markdown_path}: {e}")
            continue
    
    return result


def _discover_markdown_documents(
    documents_root: Path,
    *,
    subjects: set[str] | None = None,
    documents: set[str] | None = None,
) -> list[tuple[str, Path]]:
    """Discover all markdown documents in the Documents directory.
    
    Returns:
        List of (subject, markdown_path) tuples
    """
    results = []
    
    if not documents_root.exists():
        return results
    
    # Iterate through subject directories
    for subject_dir in sorted(documents_root.iterdir()):
        if not subject_dir.is_dir():
            continue
        
        subject = subject_dir.name
        
        # Apply subject filter
        if subjects and not any(s.lower() in subject.lower() for s in subjects):
            continue
        
        # Look for markdown directory
        markdown_dir = subject_dir / "markdown"
        if not markdown_dir.is_dir():
            continue
        
        # Find all .md files
        for md_path in sorted(markdown_dir.glob("*.md")):
            # Apply document filter
            if documents and not any(d.lower() in md_path.name.lower() for d in documents):
                continue
            
            results.append((subject, md_path))
    
    return results


def _load_existing_issues(
    report_path: Path,
) -> dict[DocumentKey, list[LanguageIssue]]:
    """Load existing issues from language-check-report.csv.
    
    Returns:
        Dictionary mapping DocumentKey to list of LanguageIssue objects
    """
    issues_by_doc = {}
    
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    subject = row.get("Subject", "").strip()
                    filename = row.get("Filename", "").strip()
                    
                    if not subject or not filename:
                        continue
                    
                    # Create minimal LanguageIssue
                    issue = LanguageIssue(
                        filename=filename,
                        rule_id=row.get("Rule ID", "").strip(),
                        message=row.get("Message", "").strip(),
                        issue_type=row.get("Type", "").strip(),
                        replacements=row.get("Suggestions", "").split(", ") if row.get("Suggestions") else [],
                        context=row.get("Highlighted Context", "").strip(),
                        highlighted_context=row.get("Highlighted Context", "").strip(),
                        issue=row.get("Issue", "").strip(),
                        page_number=int(row["Page"]) if row.get("Page") else None,
                        issue_id=-1,  # Not relevant for pre-existing issues
                        pass_code=PassCode.LT,  # Original detection source
                    )
                    
                    key = DocumentKey(subject=subject, filename=filename)
                    issues_by_doc.setdefault(key, []).append(issue)
                    
                except (ValueError, KeyError) as e:
                    print(f"Warning: Skipping invalid row in existing report: {e}")
                    continue
    
    except (OSError, UnicodeDecodeError) as e:
        print(f"Warning: Failed to read existing report {report_path}: {e}")
    
    return issues_by_doc


def _group_issues_by_page(
    issues: list[LanguageIssue],
) -> dict[int, list[LanguageIssue]]:
    """Group issues by page number.
    
    Returns:
        Dictionary mapping page_number -> list of issues on that page
    """
    by_page = {}
    for issue in issues:
        page = issue.page_number if issue.page_number is not None else 0
        by_page.setdefault(page, []).append(issue)
    
    return by_page
```

### Step 2: Create Page-Based Batcher

**File**: `src/llm_review/llm_proofreader/page_batcher.py`

This module creates batches based on page ranges rather than issue counts.

```python
"""Page-based batching for comprehensive document review.

Instead of batching by issues, this module batches by page ranges to ensure
complete coverage of all document pages.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.models import LanguageIssue
from src.utils.page_utils import extract_pages_text, find_page_markers


@dataclass
class PageBatch:
    """Represents a batch of pages for review.
    
    Attributes:
        subject: Subject name
        filename: Document filename
        index: Zero-based batch index
        page_range: Tuple of (start_page, end_page) inclusive
        page_context: Dict mapping page numbers to their content
        pre_existing_issues: Dict mapping page numbers to list of known issues
    """
    subject: str
    filename: str
    index: int
    page_range: tuple[int, int]
    page_context: dict[int, str]
    pre_existing_issues: dict[int, list[LanguageIssue]]


def iter_page_batches(
    document_metadata: dict,
    pages_per_batch: int,
    markdown_path: Path,
    *,
    subject: str,
    filename: str,
) -> Iterable[PageBatch]:
    """Generate batches of pages for a document.
    
    Args:
        document_metadata: Metadata dict from load_page_based_documents()
        pages_per_batch: Number of pages per batch
        markdown_path: Path to the markdown file
        subject: Subject name
        filename: Filename for the document
    
    Yields:
        PageBatch objects containing page ranges and context
    """
    page_numbers = document_metadata["page_numbers"]
    pre_existing_issues = document_metadata["pre_existing_issues"]
    
    if not page_numbers:
        return
    
    # Read markdown content once
    try:
        markdown_content = markdown_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"Error reading {markdown_path}: {e}")
        return
    
    # Check for page markers
    page_markers = find_page_markers(markdown_content)
    has_page_markers = len(page_markers) > 0
    
    # Create batches by page ranges
    for batch_idx, start_idx in enumerate(range(0, len(page_numbers), pages_per_batch)):
        batch_page_nums = page_numbers[start_idx : start_idx + pages_per_batch]
        
        if not batch_page_nums:
            continue
        
        # Extract page content
        if has_page_markers:
            page_context = extract_pages_text(markdown_content, set(batch_page_nums))
        else:
            # Whole document - use page 0
            page_context = {0: markdown_content}
        
        # Filter pre-existing issues for this batch
        batch_issues = {
            page: pre_existing_issues.get(page, [])
            for page in batch_page_nums
        }
        
        page_range = (batch_page_nums[0], batch_page_nums[-1])
        
        yield PageBatch(
            subject=subject,
            filename=filename,
            index=batch_idx,
            page_range=page_range,
            page_context=page_context,
            pre_existing_issues=batch_issues,
        )
```

### Step 3: Update Prompt Factory

**File Modification**: `src/llm_review/llm_proofreader/prompt_factory.py`

Add a new function to build prompts for page-based batches:

```python
def build_page_prompts(batch: PageBatch) -> list[str]:
    """Build system and user prompts for a page-based batch.
    
    Args:
        batch: A PageBatch object containing page ranges and context
    
    Returns:
        A list with two strings: [system_prompt, user_prompt]
    """
    # Build structured page data with pre-existing issues
    page_data = []
    for page_num in sorted(batch.page_context.keys()):
        page_issues = batch.pre_existing_issues.get(page_num, [])
        
        # Format issues for display
        issue_rows = []
        for issue in page_issues:
            issue_rows.append({
                "issue_id": str(issue.issue_id) if issue.issue_id >= 0 else "—",
                "issue": issue.issue.replace("|", "\\|") if issue.issue else "—",
                "highlighted_context": (issue.highlighted_context or "").replace("|", "\\|"),
            })
        
        page_label = str(page_num) if page_num != 0 else "—"
        
        page_data.append({
            "page_number": page_label,
            "page_content": batch.page_context.get(page_num, ""),
            "has_existing_issues": len(issue_rows) > 0,
            "issues": issue_rows,
            "issue_count": len(issue_rows),
        })
    
    # Build context for template
    context = {
        "subject": batch.subject,
        "filename": batch.filename,
        "page_range_start": batch.page_range[0],
        "page_range_end": batch.page_range[1],
        "issue_pages": page_data,
    }
    
    # Render prompts using existing templates
    # The user_llm_proofreader.md template already handles issue_pages correctly
    system_prompt, user_prompt = render_prompts(
        "llm_proofreader.md",
        "user_llm_proofreader.md",
        context,
    )
    
    return [system_prompt, user_prompt]
```

### Step 4: Create New Runner for Page-Based Processing

**File**: `src/llm_review/llm_proofreader/page_runner.py`

This is a new runner that processes documents page-by-page:

```python
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
        pages_per_batch: int = 5,
        max_retries: int = 2,
        log_raw_responses: bool | None = None,
        log_response_dir: Path | None = None,
        fail_on_quota: bool = True,
    ):
        """Initialize the page-based runner.

        Args:
            llm_service: LLM service for making API calls
            state: State manager for tracking progress
            pages_per_batch: Number of pages per batch (default 5)
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
            print(
                f"Raw response logging enabled -> "
                f"{self.config.log_response_dir}"
            )

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
        print(f"  Batch {batch.index}: Pages {batch.page_range[0]}-{batch.page_range[1]}")

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
```

### Step 5: Add CLI Integration

**File Modification**: `src/llm_review/llm_proofreader/cli.py`

Add a new CLI option to use page-based processing:

```python
# Add to argument parser
parser.add_argument(
    "--page-based",
    action="store_true",
    help="Use page-based processing instead of issue-based processing",
)

parser.add_argument(
    "--pages-per-batch",
    type=int,
    default=5,
    help="Number of pages per batch (for page-based mode)",
)

# In main() function, add conditional logic:
def main():
    args = parser.parse_args()
    
    # ... existing code for LLM service setup ...
    
    if args.page_based:
        # Use page-based runner
        from .page_runner import PageBasedProofreaderRunner
        
        runner = PageBasedProofreaderRunner(
            llm_service,
            state,
            pages_per_batch=args.pages_per_batch,
            max_retries=args.max_retries,
            fail_on_quota=not args.continue_on_quota,
        )
    else:
        # Use existing issue-based runner
        runner = ProofreaderRunner(
            llm_service,
            state,
            batch_size=args.batch_size,
            max_retries=args.max_retries,
            fail_on_quota=not args.continue_on_quota,
        )
    
    # Run the workflow
    stats = runner.run(force=args.force, dry_run=args.dry_run)
    
    # Print summary
    print(f"\nCompleted: {stats}")
```

## Testing Strategy

### Unit Tests

Create test file: `tests/test_page_data_loader.py`

```python
"""Tests for page-based data loader."""

import pytest
from pathlib import Path
from src.llm_review.llm_proofreader.page_data_loader import (
    load_page_based_documents,
    _discover_markdown_documents,
    _group_issues_by_page,
)


def test_discover_markdown_documents(tmp_path):
    """Test document discovery."""
    # Create test structure
    subject_dir = tmp_path / "Test-Subject" / "markdown"
    subject_dir.mkdir(parents=True)
    (subject_dir / "doc1.md").write_text("# Doc 1")
    (subject_dir / "doc2.md").write_text("# Doc 2")
    
    docs = _discover_markdown_documents(tmp_path)
    assert len(docs) == 2
    assert all(doc[0] == "Test-Subject" for doc in docs)


def test_group_issues_by_page():
    """Test issue grouping by page."""
    from src.models import LanguageIssue, PassCode
    
    issues = [
        LanguageIssue(
            filename="test.md",
            rule_id="TEST",
            message="Test",
            issue_type="test",
            replacements=[],
            context="",
            highlighted_context="",
            issue="",
            page_number=1,
            pass_code=PassCode.LT,
        ),
        LanguageIssue(
            filename="test.md",
            rule_id="TEST",
            message="Test",
            issue_type="test",
            replacements=[],
            context="",
            highlighted_context="",
            issue="",
            page_number=1,
            pass_code=PassCode.LT,
        ),
        LanguageIssue(
            filename="test.md",
            rule_id="TEST",
            message="Test",
            issue_type="test",
            replacements=[],
            context="",
            highlighted_context="",
            issue="",
            page_number=2,
            pass_code=PassCode.LT,
        ),
    ]
    
    grouped = _group_issues_by_page(issues)
    assert len(grouped) == 2
    assert len(grouped[1]) == 2
    assert len(grouped[2]) == 1


def test_load_page_based_documents_filters(tmp_path):
    """Test subject and document filtering."""
    # Create multiple subjects
    for subject in ["Math", "Science", "History"]:
        md_dir = tmp_path / subject / "markdown"
        md_dir.mkdir(parents=True)
        (md_dir / f"{subject.lower()}-doc.md").write_text(f"# {subject}")
    
    # Test subject filter
    docs = load_page_based_documents(
        tmp_path,
        None,
        subjects={"Math", "Science"},
    )
    assert len(docs) == 2
    
    # Test document filter
    docs = load_page_based_documents(
        tmp_path,
        None,
        documents={"math-doc"},
    )
    assert len(docs) == 1
```

### Integration Tests

Create test file: `tests/test_page_based_runner_integration.py`

```python
"""Integration tests for page-based runner."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock


def test_page_based_runner_full_workflow(tmp_path):
    """Test complete page-based workflow."""
    from src.llm_review.llm_proofreader.page_runner import PageBasedProofreaderRunner
    from src.llm.service import LLMService
    from src.llm_review.core.state_manager import StateManager
    
    # Setup test environment
    subject_dir = tmp_path / "Test" / "markdown"
    subject_dir.mkdir(parents=True)
    
    # Create test document with page markers
    content = """# Document Title

{1}------------------------------------------------

Content on page 1

{2}------------------------------------------------

Content on page 2
"""
    (subject_dir / "test-doc.md").write_text(content)
    
    # Mock LLM service
    mock_llm = Mock(spec=LLMService)
    mock_llm.generate.return_value = []  # No new issues
    
    # Create state manager
    state = StateManager(tmp_path / "state.json")
    
    # Create runner
    runner = PageBasedProofreaderRunner(
        mock_llm,
        state,
        pages_per_batch=2,
    )
    
    # Run with mocked environment
    # This would need proper setup of Documents directory
    # stats = runner.run(dry_run=True)
    # assert stats["total_documents"] >= 0
```

## Migration Strategy

### Phase 1: Development and Testing (Week 1-2)

1. Implement new modules (page_data_loader, page_batcher, page_runner)
2. Write unit tests for each module
3. Test with small sample documents
4. Validate prompt rendering with pre-existing issues

### Phase 2: Parallel Operation (Week 3)

1. Keep existing issue-based system operational
2. Add `--page-based` flag to CLI
3. Run both systems on same documents and compare results
4. Fine-tune pages_per_batch parameter based on token limits

### Phase 3: Production Deployment (Week 4)

1. Make page-based mode the default
2. Update documentation
3. Create migration guide for users
4. Monitor performance and accuracy

## Configuration and Tuning

### Recommended Parameters

```bash
# Small documents (< 20 pages)
--pages-per-batch 10

# Medium documents (20-50 pages)
--pages-per-batch 5

# Large documents (> 50 pages)
--pages-per-batch 3

# Very detailed review
--pages-per-batch 1
```

### Environment Variables

```bash
# Enable detailed logging
export LLM_PROOFREADER_LOG_RESPONSES=1
export LLM_PROOFREADER_LOG_DIR=data/llm_proofreader_responses

# Continue on quota errors
export LLM_PROOFREADER_CONTINUE_ON_QUOTA=1
```

## Best Practices

### 1. Token Management

- Monitor prompt sizes for large documents
- Adjust `pages_per_batch` if hitting token limits
- Consider truncating very long pages (add max_page_length parameter)

### 2. Error Handling

- Always log failed batches for manual review
- Implement retry logic with exponential backoff
- Save partial results after each successful batch

### 3. Performance Optimization

- Use async batch API for large document sets
- Implement parallel processing for multiple documents
- Cache markdown content to avoid repeated file reads

### 4. Quality Assurance

- Regularly review LLM outputs for false positives
- Compare page-based results with issue-based results
- Monitor consistency across different page batch sizes

## Troubleshooting

### Issue: Token Limit Exceeded

**Solution**: Reduce `pages_per_batch` or implement page content truncation

### Issue: Duplicate Issue Reporting

**Solution**: Ensure pre-existing issues are clearly marked in prompt template

### Issue: Missing Pages

**Solution**: Verify page marker parsing in `find_page_markers()` function

### Issue: Slow Processing

**Solution**: Use batch API, increase parallelism, or reduce pages_per_batch

## References

- **Language Check Module**: `src/language_check/language_check.py` - Reference for document processing patterns
- **Existing Batcher**: `src/llm_review/core/batcher.py` - Reference for batch structure
- **Prompt Templates**: `src/prompt/promptFiles/` - Reference for template format
- **LLM Review Guide**: `docs/LLM_REVIEW_MODULE_GUIDE.md` - General patterns

## Conclusion

This guide provides a complete blueprint for implementing page-based document processing in the LLM proofreader. The key benefits are:

1. **Complete Coverage**: Every page is reviewed, not just pages with detected issues
2. **Context Awareness**: Pre-existing issues provide context to avoid duplicates
3. **Flexibility**: Adjustable batch sizes for different document types
4. **Backward Compatibility**: Existing issue-based system remains available

Follow the steps sequentially, test thoroughly at each stage, and refer to the existing `language_check` module for proven patterns.
