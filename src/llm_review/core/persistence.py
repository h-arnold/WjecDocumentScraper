from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.models.document_key import DocumentKey
from src.models.language_issue import LanguageIssue

from .config import ReviewConfiguration


class PersistenceManager:
    """Generic persistence with configurable paths and columns."""

    def __init__(self, config: ReviewConfiguration):
        self.config = config

    def save_batch_results(
        self,
        key: DocumentKey,
        batch_results: list[dict[str, Any]],
        *,
        merge: bool = True,
    ) -> Path:
        """Save batch results to a CSV file.

        Args:
            key: DocumentKey identifying the document
            batch_results: List of issue dictionaries (must include issue_id)
            merge: If True and file exists, merge with existing rows
                   (deduplicating by issue_id)

        Returns:
            Path to the saved file
        """
        output_file = self.config.get_output_path(key)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        existing_rows: dict[int, dict[str, str]] = {}
        if merge and output_file.exists():
            existing_rows = self._read_existing_rows(output_file)

        # Build new rows keyed by issue_id
        new_rows: dict[int, dict[str, str]] = {}
        for issue in batch_results:
            try:
                iid, row = self._normalise_issue_row(issue)
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
                writer = csv.DictWriter(f, fieldnames=self.config.output_csv_columns)
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

    def save_failed_issues(
        self,
        key: DocumentKey,
        batch_index: int,
        failed_issues: Iterable[LanguageIssue],
        *,
        error_messages: dict | None = None,
    ) -> Path:
        """Save details about failed validation attempts to a JSON file.

        The file is written to:
        <output_base_dir>/<output_subdir>_errors/<subject>/<filename>.batch-<index>.errors.json
        """
        # Construct error output path based on config
        # e.g. data/llm_categoriser_errors/Subject/file.json
        # We'll use output_base_dir (e.g. Documents or data) and append _errors to subdir

        # Note: The original implementation used "data/llm_categoriser_errors"
        # We should probably make this configurable or derive it.
        # For now, let's assume we want to store errors in a parallel structure.

        # If output_base_dir is "Documents", maybe we don't want errors there.
        # The spec didn't explicitly define error path config.
        # I'll use a convention: data/<subdir>_errors/

        error_dir_name = f"{self.config.output_subdir}_errors"
        report_dir = Path("data") / error_dir_name / key.subject
        report_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = key.filename.replace("/", "-")
        output_file = report_dir / f"{safe_filename}.batch-{batch_index}.errors.json"

        current_time = datetime.now(timezone.utc)
        payload = {
            "timestamp": current_time.isoformat().replace("+00:00", "Z"),
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

    def load_document_results(self, key: DocumentKey) -> list[dict[str, str]]:
        """Load existing CSV results for a document.

        Returns a list of row dictionaries (strings) ordered by `issue_id`. If the
        file does not exist, an empty list is returned.
        """
        output_file = self.config.get_output_path(key)

        if not output_file.exists():
            return []

        rows = self._read_existing_rows(output_file)
        return [rows[iid] for iid in sorted(rows)]

    def clear_document_results(self, key: DocumentKey) -> None:
        """Delete results file for a document."""
        output_file = self.config.get_output_path(key)

        if output_file.exists():
            try:
                output_file.unlink()
            except OSError as e:
                print(f"Warning: Could not delete {output_file}: {e}")

    def _read_existing_rows(self, path: Path) -> dict[int, dict[str, str]]:
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

                    # Normalise the row to ensure all configured columns are present.
                    normalised_row = {
                        header: row.get(header, "")
                        for header in self.config.output_csv_columns
                    }
                    rows[iid] = normalised_row
        except OSError as e:
            print(f"Warning: Could not read existing CSV {path}: {e}")
        return rows

    def _normalise_issue_row(self, issue: dict[str, Any]) -> tuple[int, dict[str, str]]:
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

        # We only populate columns that exist in the issue dict and are in the config
        row = {}
        for header in self.config.output_csv_columns:
            # Special handling for issue_id which we know exists
            if header == "issue_id":
                row[header] = str(issue_id)
            else:
                # Try to find the value in the issue dict
                val = issue.get(header)
                if val is None:
                    # Fallbacks for common fields if not found directly
                    if header == "issue":
                        val = issue.get("context") or issue.get("context_from_tool")
                    elif header == "highlighted_context":
                        val = issue.get("context_from_tool")

                row[header] = _clean(val)

        return issue_id, row
