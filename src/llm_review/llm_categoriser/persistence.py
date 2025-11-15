"""Persist categorised results as per-document CSV files.

This module handles atomic writes of CSV output files and merging of batch results
when resuming work on partially processed documents. Rows are deduplicated by
`issue_id`, so reruns simply overwrite the most recent categorisation for each issue.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from src.models.document_key import DocumentKey
from src.models.language_issue import LanguageIssue
from datetime import datetime
from typing import Iterable

CSV_HEADERS = [
    "issue_id",
    "page_number",
    "issue",
    "highlighted_context",
    "error_category",
    "confidence_score",
    "reasoning",
]


def save_batch_results(
    key: DocumentKey,
    batch_results: list[dict[str, Any]],
    *,
    merge: bool = True,
    output_dir: Path = Path("Documents"),
) -> Path:
    """Save batch results to a CSV file.
    
    Args:
        key: DocumentKey identifying the document
        batch_results: List of issue dictionaries (must include issue_id)
        merge: If True and file exists, merge with existing rows (deduplicating by issue_id)
        output_dir: Base directory for output (default: "Documents")
        
    Returns:
        Path to the saved file
        
    Notes:
        - Results are saved to: Documents/<subject>/document_reports/<filename>.csv
        - Writes are atomic (temp file + replace)
        - When merging, issues are deduplicated using `issue_id` as the primary key
        - Force mode (--force CLI flag) clears both state and results to prevent duplicates
    """
    # Construct output path
    report_dir = output_dir / key.subject / "document_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = report_dir / key.filename.replace(".md", ".csv")

    existing_rows: dict[int, dict[str, str]] = {}
    if merge and output_file.exists():
        existing_rows = _read_existing_rows(output_file)

    # Build new rows keyed by issue_id
    new_rows: dict[int, dict[str, str]] = {}
    for issue in batch_results:
        try:
            iid, row = _normalise_issue_row(issue)
        except ValueError as exc:
            print(f"    Warning: Skipping issue without valid issue_id: {exc}")
            continue
        new_rows[iid] = row

    if not new_rows and not existing_rows:
        return output_file

    merged_rows = existing_rows | new_rows

    # Write atomically
    temp_file = output_file.with_suffix(".tmp")
    try:
        with open(temp_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            for issue_id in sorted(merged_rows):
                writer.writerow(merged_rows[issue_id])

        temp_file.replace(output_file)

    except OSError as e:
        print(f"Error writing to {output_file}: {e}")
        if temp_file.exists():
            temp_file.unlink()
        raise
    
    return output_file


def load_document_results(
    key: DocumentKey,
    *,
    output_dir: Path = Path("Documents"),
) -> list[dict[str, str]]:
    """Load existing CSV results for a document.

    Returns a list of row dictionaries (strings) ordered by `issue_id`. If the
    file does not exist, an empty list is returned.
    """
    report_dir = output_dir / key.subject / "document_reports"
    output_file = report_dir / key.filename.replace(".md", ".csv")

    if not output_file.exists():
        return []

    rows = _read_existing_rows(output_file)
    return [rows[iid] for iid in sorted(rows)]


def clear_document_results(
    key: DocumentKey,
    *,
    output_dir: Path = Path("Documents"),
) -> None:
    """Delete results file for a document.
    
    Args:
        key: DocumentKey identifying the document
        output_dir: Base directory for output (default: "Documents")
    """
    report_dir = output_dir / key.subject / "document_reports"
    output_file = report_dir / key.filename.replace(".md", ".csv")
    
    if output_file.exists():
        try:
            output_file.unlink()
        except OSError as e:
            print(f"Warning: Could not delete {output_file}: {e}")


def save_failed_issues(
    key: DocumentKey,
    batch_index: int,
    failed_issues: Iterable[LanguageIssue],
    *,
    error_messages: dict | None = None,
    output_dir: Path = Path("data"),
) -> Path:
    """Save details about failed validation attempts to a JSON file.

    The file is written to: data/llm_categoriser_errors/<subject>/<filename>.batch-<index>.errors.json
    Args:
        key: DocumentKey identifying the document
        batch_index: Integer index of the batch being processed
        failed_issues: Iterable of LanguageIssue objects that could not be validated
        error_messages: Optional mapping of issue ids (or other keys) to lists of error messages.
        output_dir: Base directory to write to (default: data)

    Returns:
        Path to the saved file
    """
    report_dir = output_dir / "llm_categoriser_errors" / key.subject
    report_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = key.filename.replace("/", "-")
    output_file = report_dir / f"{safe_filename}.batch-{batch_index}.errors.json"

    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "subject": key.subject,
        "filename": key.filename,
        "batch_index": batch_index,
        "issues": [issue.model_dump() for issue in failed_issues],
    }

    temp_file = output_file.with_suffix(".tmp")
    # Attach any error messages to the payload before writing
    if error_messages:
        serialisable_errors = {str(k): v for k, v in error_messages.items()}
        payload["errors"] = serialisable_errors

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        temp_file.replace(output_file)
    except OSError as e:
        print(f"Error writing failed issues to {output_file}: {e}")
        if temp_file.exists():
            temp_file.unlink()
        raise

    return output_file


def _read_existing_rows(path: Path) -> dict[int, dict[str, str]]:
    """Read an existing CSV file into a mapping keyed by issue_id."""
    rows: dict[int, dict[str, str]] = {}
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_id = row.get("issue_id")
                if raw_id is None:
                    continue
                try:
                    iid = int(raw_id)
                except ValueError:
                    continue
                rows[iid] = row
    except OSError as e:
        print(f"Warning: Could not read existing CSV {path}: {e}")
    return rows


def _normalise_issue_row(issue: dict[str, Any]) -> tuple[int, dict[str, str]]:
    """Normalise a validated issue dict into a CSV row keyed by issue_id."""
    raw_id = issue.get("issue_id")
    if raw_id is None:
        raise ValueError("missing issue_id")
    try:
        issue_id = int(raw_id)
    except Exception as exc:
        raise ValueError(f"invalid issue_id {raw_id!r}") from exc

    def _clean(value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    row = {
        "issue_id": str(issue_id),
        "page_number": _clean(issue.get("page_number")),
        "issue": _clean(issue.get("issue") or issue.get("context") or issue.get("context_from_tool")),
        "highlighted_context": _clean(issue.get("highlighted_context") or issue.get("context_from_tool")),
        "error_category": _clean(issue.get("error_category")),
        "confidence_score": _clean(issue.get("confidence_score")),
        "reasoning": _clean(issue.get("reasoning")),
    }

    return issue_id, row
