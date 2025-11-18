"""Generic batcher for LLM review passes.

This module provides reusable functionality to chunk issues per document into 
manageable batches, deduplicate page numbers, and fetch relevant page snippets 
from Markdown sources.

This is a generic component that can be used by any review pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.language_check.language_issue import LanguageIssue
from src.language_check.report_utils import build_issue_batch_table
from src.utils.page_utils import extract_pages_text, find_page_markers


@dataclass
class Batch:
    """Represents a single batch of issues for a document.
    
    Attributes:
        subject: Subject name (e.g., "Art-and-Design")
        filename: Document filename (e.g., "gcse-art-and-design.md")
        index: Zero-based batch index for this document
        issues: List of LanguageIssue objects in this batch
        page_context: Dict mapping page numbers to their Markdown content
        markdown_table: Simplified 4-column table for the LLM prompt
    """
    
    subject: str
    filename: str
    index: int
    issues: list[LanguageIssue]
    page_context: dict[int, str]
    markdown_table: str


def iter_batches(
    issues: list[LanguageIssue],
    batch_size: int,
    markdown_path: Path,
    *,
    subject: str,
    filename: str,
) -> Iterable[Batch]:
    """Generate batches of issues with page context.
    
    Args:
        issues: List of LanguageIssue objects for a single document
        batch_size: Maximum number of issues per batch
        markdown_path: Path to the Markdown file for this document
        subject: Subject name for the document
        filename: Filename for the document
        
    Yields:
        Batch objects containing chunked issues and their page context
        
    Notes:
        - If no page numbers are present (empty Page column), the entire document
          content is included as context for all batches
        - Page numbers are deduplicated within each batch
        - If page markers are malformed or missing, the batch is skipped with a warning
    """
    if not issues:
        return
    
    # Read the Markdown content once
    try:
        markdown_content = markdown_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        import sys
        print(f"Error reading Markdown file {markdown_path}: {e}", file=sys.stderr)
        return
    
    # Check if document has page markers
    page_markers = find_page_markers(markdown_content)
    has_page_markers = len(page_markers) > 0
    
    # Chunk issues into batches
    for batch_idx, start_idx in enumerate(range(0, len(issues), batch_size)):
        batch_issues = issues[start_idx : start_idx + batch_size]
        
        # Collect page context
        if not has_page_markers:
            # No page markers - use entire document as context
            page_context = {0: markdown_content}
        else:
            # Extract unique page numbers from this batch
            page_numbers = set()
            for issue in batch_issues:
                if issue.page_number is not None:
                    page_numbers.add(issue.page_number)
            
            # Fetch page content
            if page_numbers:
                page_context = extract_pages_text(markdown_content, page_numbers)
            else:
                # No page numbers specified but document has markers
                # This shouldn't happen, but handle gracefully
                print(f"Warning: Document has page markers but issues have no page numbers", file=sys.stderr)
                page_context = {0: markdown_content}
        
        # Build simplified Markdown table
        markdown_table = build_issue_batch_table(batch_issues)
        
        yield Batch(
            subject=subject,
            filename=filename,
            index=batch_idx,
            issues=batch_issues,
            page_context=page_context,
            markdown_table=markdown_table,
        )
