"""Load documents page-by-page for comprehensive proofreading.

This module provides an alternative to the issue-based loader that processes
every page from every document, including pre-existing issues as context.
"""

from __future__ import annotations

import csv
from pathlib import Path

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
            if documents and not any(
                d.lower() in md_path.name.lower() for d in documents
            ):
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
                        replacements=(
                            row.get("Suggestions", "").split(", ")
                            if row.get("Suggestions")
                            else []
                        ),
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
