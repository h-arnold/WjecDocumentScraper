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
            page: pre_existing_issues.get(page, []) for page in batch_page_nums
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
