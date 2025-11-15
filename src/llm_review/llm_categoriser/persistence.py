"""Persist categorised results as JSON files.

This module handles atomic writes of JSON output files and merging of batch results
when resuming work on partially-processed documents.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models.document_key import DocumentKey
from src.models.language_issue import LanguageIssue
from datetime import datetime
from typing import Iterable


def save_batch_results(
    key: DocumentKey,
    batch_results: dict[str, list[dict[str, Any]]],
    *,
    merge: bool = True,
    output_dir: Path = Path("Documents"),
) -> Path:
    """Save batch results to a JSON file.
    
    Args:
        key: DocumentKey identifying the document
        batch_results: Dictionary with page keys (e.g., "page_5") mapping to lists of issue dicts
        merge: If True and file exists, merge with existing content (deduplicating by rule_id+highlighted_context)
        output_dir: Base directory for output (default: "Documents")
        
    Returns:
        Path to the saved file
        
    Notes:
        - Results are saved to: Documents/<subject>/document_reports/<filename>.json
        - Writes are atomic (temp file + replace)
        - When merging, issues are deduplicated using (rule_id, highlighted_context) as key
        - Force mode (--force CLI flag) clears both state and results to prevent duplicates
    """
    # Construct output path
    report_dir = output_dir / key.subject / "document_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = report_dir / key.filename.replace(".md", ".json")
    
    # Load existing data if merging
    existing_data: dict[str, list[dict[str, Any]]] = {}
    if merge and output_file.exists():
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            import sys
            print(f"Warning: Could not load existing file {output_file}: {e}", file=sys.stderr)
    
    # Merge batch results with existing data, deduplicating by rule+context
    merged_data = existing_data.copy()
    for page_key, issues in batch_results.items():
        if page_key in merged_data:
            # Deduplicate: use (rule_id, highlighted_context) as unique key
            existing_keys = {
                (issue.get("rule_id"), issue.get("highlighted_context"))
                for issue in merged_data[page_key]
            }
            # Only add issues that don't already exist
            new_issues = [
                issue for issue in issues
                if (issue.get("rule_id"), issue.get("highlighted_context")) not in existing_keys
            ]
            merged_data[page_key].extend(new_issues)
        else:
            # New page
            merged_data[page_key] = issues
    
    # Write atomically
    temp_file = output_file.with_suffix(".tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(merged_data, f, indent=2)
        
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
) -> dict[str, list[dict[str, Any]]]:
    """Load existing results for a document.
    
    Args:
        key: DocumentKey identifying the document
        output_dir: Base directory for output (default: "Documents")
        
    Returns:
        Dictionary with page keys mapping to lists of issue dicts, or empty dict if not found
    """
    report_dir = output_dir / key.subject / "document_reports"
    output_file = report_dir / key.filename.replace(".md", ".json")
    
    if not output_file.exists():
        return {}
    
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Could not load {output_file}: {e}")
        return {}


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
    output_file = report_dir / key.filename.replace(".md", ".json")
    
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
        error_messages: Optional mapping of issue ids (or other keys) to lists of error messages.
        key: DocumentKey identifying the document
        batch_index: Integer index of the batch being processed
        failed_issues: Iterable of LanguageIssue objects that could not be validated
        output_dir: Base directory to write to (default: data)
        error_messages: Optional mapping of issue ids (or other keys) to lists of error messages.

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
