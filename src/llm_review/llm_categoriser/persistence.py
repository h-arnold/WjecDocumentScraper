"""Persist categorised results as JSON files.

This module handles atomic writes of JSON output files and merging of batch results
when resuming work on partially-processed documents.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models.document_key import DocumentKey


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
        merge: If True and file exists, merge with existing content
        output_dir: Base directory for output (default: "Documents")
        
    Returns:
        Path to the saved file
        
    Notes:
        - Results are saved to: Documents/<subject>/document_reports/<filename>.json
        - Writes are atomic (temp file + replace)
        - Existing files are merged by default unless merge=False
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
            print(f"Warning: Could not load existing file {output_file}: {e}")
    
    # Merge batch results with existing data
    merged_data = existing_data.copy()
    for page_key, issues in batch_results.items():
        if page_key in merged_data:
            # Append to existing page
            merged_data[page_key].extend(issues)
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
