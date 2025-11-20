"""Load verified categorised issues for proofreading.

This module parses the verified-llm-categorised-language-check-report.csv
and filters to only SPELLING_ERROR and ABSOLUTE_GRAMMATICAL_ERROR issues.

CSV columns:
    - subject
    - filename
    - issue_id
    - page_number
    - issue
    - highlighted_context
    - pass_code
    - error_category
    - confidence_score
    - reasoning
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Generator

from src.models import DocumentKey, ErrorCategory, LanguageIssue, PassCode


def load_proofreader_issues(
    report_path: Path,
    *,
    subjects: set[str] | None = None,
    documents: set[str] | None = None,
) -> dict[DocumentKey, list[LanguageIssue]]:
    """Load and group issues for proofreading from verified categorised report.

    Only includes issues with error_category in:
        - SPELLING_ERROR
        - ABSOLUTE_GRAMMATICAL_ERROR

    Args:
        report_path: Path to verified-llm-categorised-language-check-report.csv
        subjects: Optional set of subject filters (case-insensitive)
        documents: Optional set of document filters (case-insensitive)

    Returns:
        Dictionary mapping DocumentKey to list of LanguageIssue objects
    """
    raw_issues = list(_parse_verified_csv(report_path))

    # Apply filters
    if subjects:
        raw_issues = [
            (subj, fname, issue)
            for subj, fname, issue in raw_issues
            if any(s.lower() in subj.lower() for s in subjects)
        ]

    if documents:
        raw_issues = [
            (subj, fname, issue)
            for subj, fname, issue in raw_issues
            if any(d.lower() in fname.lower() for d in documents)
        ]

    # Group by DocumentKey
    grouped: dict[DocumentKey, list[LanguageIssue]] = {}
    for subject, filename, issue in raw_issues:
        key = DocumentKey(subject=subject, filename=filename)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(issue)

    return grouped


def _parse_verified_csv(
    report_path: Path,
) -> Generator[tuple[str, str, LanguageIssue], None, None]:
    """Parse the verified categorised CSV file.

    Only yields issues with SPELLING_ERROR or ABSOLUTE_GRAMMATICAL_ERROR.

    Yields:
        Tuples of (subject, filename, LanguageIssue)
    """
    if not report_path.exists():
        raise FileNotFoundError(f"Report not found: {report_path}")

    required_columns = {
        "subject",
        "filename",
        "issue_id",
        "page_number",
        "issue",
        "highlighted_context",
        "pass_code",
        "error_category",
        "confidence_score",
        "reasoning",
    }

    with open(report_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Validate headers
        if not reader.fieldnames:
            raise ValueError("CSV file has no headers")

        header_set = set(reader.fieldnames)
        missing = required_columns - header_set
        if missing:
            raise ValueError(f"CSV missing required columns: {missing}")

        for row in reader:
            try:
                subject = row["subject"].strip()
                filename = row["filename"].strip()

                # Parse error_category - handle "ErrorCategory.VALUE" format
                error_category_raw = row.get("error_category", "").strip()
                error_category: ErrorCategory | None = None
                if error_category_raw:
                    if error_category_raw.startswith("ErrorCategory."):
                        error_category_value = error_category_raw.split(".", 1)[1]
                    else:
                        error_category_value = error_category_raw
                    # Convert to enum
                    try:
                        error_category = ErrorCategory(error_category_value)
                    except ValueError:
                        print(f"Warning: Invalid error category '{error_category_raw}'")
                        continue  # Skip invalid categories

                # Filter: only SPELLING_ERROR and ABSOLUTE_GRAMMATICAL_ERROR
                if error_category not in (
                    ErrorCategory.SPELLING_ERROR,
                    ErrorCategory.ABSOLUTE_GRAMMATICAL_ERROR,
                ):
                    continue

                # Create a minimal LanguageIssue with available fields
                issue = LanguageIssue(
                    filename=filename,
                    rule_id="PROOFREADER_REVIEW",  # Placeholder
                    message="Review by LLM proofreader",  # Placeholder
                    issue_type="review",  # Placeholder
                    replacements=[],  # Not in verified CSV
                    context=row["highlighted_context"].strip(),
                    highlighted_context=row["highlighted_context"].strip(),
                    issue=row["issue"].strip(),
                    page_number=int(row["page_number"]) if row.get("page_number") else None,
                    issue_id=int(row["issue_id"]),
                    pass_code=PassCode.LP,  # Set to LP for proofreader
                    error_category=error_category,
                    confidence_score=(
                        int(row["confidence_score"])
                        if row.get("confidence_score")
                        else None
                    ),
                    reasoning=row.get("reasoning", "").strip() or None,
                )

                yield subject, filename, issue

            except (ValueError, KeyError) as e:
                print(f"Warning: Skipping invalid row: {e}")
                continue
