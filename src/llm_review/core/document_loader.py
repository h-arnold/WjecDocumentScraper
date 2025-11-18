"""Generic document loader for LLM review passes.

This module provides reusable functionality to load and parse CSV reports into 
grouped LanguageIssue objects. It reads CSV reports, assigns issue IDs, validates 
that corresponding Markdown files exist, and groups issues by DocumentKey.

This is a generic component that can be used by any review pass.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Iterator

from src.language_check.language_issue import LanguageIssue
from src.models import PassCode
from src.models.document_key import DocumentKey


def load_issues(
    report_path: Path,
    *,
    subjects: set[str] | None = None,
    documents: set[str] | None = None,
) -> dict[DocumentKey, list[LanguageIssue]]:
    """Load issues from CSV report and group by DocumentKey.
    
    Args:
        report_path: Path to the language-check-report.csv file
        subjects: Optional set of subject names to filter (case-insensitive)
        documents: Optional set of document filenames to filter (case-insensitive)
        
    Returns:
        Dictionary mapping DocumentKey to list of LanguageIssue objects.
        Each issue within a document has an auto-incremented issue_id starting at 0.
        
    Raises:
        FileNotFoundError: If report_path doesn't exist
        ValueError: If CSV is malformed or required columns are missing
        
    Notes:
        - Issues are validated to ensure corresponding Markdown files exist
        - Missing Markdown files are logged and that document is skipped
        - Empty or malformed CSV rows are logged and skipped
    """
    if not report_path.exists():
        raise FileNotFoundError(f"Report file not found: {report_path}")
    
    # Read and parse CSV with subject info
    raw_issues_with_subjects = list(_parse_csv(report_path))
    
    # Prepare case-insensitive filters
    subjects_lower = {s.lower() for s in subjects} if subjects is not None else None
    documents_lower = {d.lower() for d in documents} if documents is not None else None
    
    # Group by DocumentKey
    grouped: dict[DocumentKey, list[LanguageIssue]] = {}
    
    for subject, issue in raw_issues_with_subjects:
        # Apply filters
        if subjects_lower is not None and subject.lower() not in subjects_lower:
            continue
        
        if documents_lower is not None and issue.filename.lower() not in documents_lower:
            continue
        
        # Create DocumentKey
        key = DocumentKey(subject=subject, filename=issue.filename)
        
        if key not in grouped:
            grouped[key] = []
        
        grouped[key].append(issue)
    
    # Assign issue IDs within each document
    for key, issues in grouped.items():
        for idx, issue in enumerate(issues):
            issue.issue_id = idx
    
    # Validate Markdown files exist
    validated = _validate_markdown_files(grouped)
    
    return validated


def _parse_csv(report_path: Path) -> Iterator[tuple[str, LanguageIssue]]:
    """Parse CSV and yield (subject, LanguageIssue) tuples."""
    with open(report_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        
        # Validate required columns
        required_columns = {
            "Subject", "Filename", "Page", "Rule ID", "Type", 
            "Issue", "Message", "Suggestions", "Highlighted Context"
        }
        
        if reader.fieldnames is None:
            raise ValueError("CSV file has no header row")
        
        missing = required_columns - set(reader.fieldnames)
        if missing:
            raise ValueError(f"CSV missing required columns: {missing}")
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
            try:
                # Parse suggestions (comma-separated)
                suggestions_str = row.get("Suggestions", "").strip()
                suggestions = [s.strip() for s in suggestions_str.split(",") if s.strip()] if suggestions_str else []
                
                # Parse page number (may be empty for single-page docs)
                page_str = row.get("Page", "").strip()
                page_number = int(page_str) if page_str else None
                
                subject = row["Subject"].strip()
                
                raw_pass_code = row.get("Pass Code", "").strip()
                pass_code: PassCode | None
                if not raw_pass_code:
                    # Default to LT for legacy CSVs or empty values
                    pass_code = PassCode.LT
                else:
                    try:
                        pass_code = PassCode(raw_pass_code)
                    except ValueError:
                        print(
                            f"Warning: Unknown pass code '{raw_pass_code}' on row {row_num}; defaulting to LT",
                            file=sys.stderr,
                        )
                        pass_code = PassCode.LT

                issue = LanguageIssue(
                    filename=row["Filename"].strip(),
                    rule_id=row["Rule ID"].strip(),
                    message=row["Message"].strip(),
                    issue_type=row["Type"].strip(),
                    replacements=suggestions,
                    context=row.get("Highlighted Context", "").strip(),  # For backward compat
                    highlighted_context=row.get("Highlighted Context", "").strip(),
                    issue=row.get("Issue", "").strip(),
                    page_number=page_number,
                    issue_id=-1,  # Will be assigned later
                    pass_code=pass_code,
                )
                
                yield subject, issue
                
            except (ValueError, KeyError) as e:
                print(f"Warning: Skipping malformed row {row_num}: {e}", file=sys.stderr)
                continue


def _validate_markdown_files(
    grouped: dict[DocumentKey, list[LanguageIssue]]
) -> dict[DocumentKey, list[LanguageIssue]]:
    """Validate that Markdown files exist for each document.
    
    Logs errors for missing files and removes those documents from the result.
    """
    validated: dict[DocumentKey, list[LanguageIssue]] = {}
    
    for key, issues in grouped.items():
        # Construct expected Markdown path
        markdown_path = Path("Documents") / key.subject / "markdown" / key.filename
        
        if not markdown_path.exists():
            print(f"Warning: Markdown file not found for {key}: {markdown_path}", file=sys.stderr)
            print(f"  Skipping {len(issues)} issue(s) for this document", file=sys.stderr)
            continue
        
        validated[key] = issues
    
    return validated
