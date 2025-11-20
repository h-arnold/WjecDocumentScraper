"""Generic state manager for LLM review passes.

This module provides reusable functionality to track completed batches for
resume support. It maintains a JSON state file to track which batches have been
successfully processed for each document, enabling workflows to resume after
interruptions.

This is a generic component that can be used by any review pass.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models.document_key import DocumentKey


class StateManager:
    """Manages state tracking for the categoriser workflow.

    The state file has this structure:
    {
        "version": "1.0",
        "subjects": {
            "Art-and-Design": {
                "file.md": {
                    "completed_batches": [0, 1, 2],
                    "total_issues": 45
                }
            }
        }
    }
    """

    VERSION = "1.0"

    def __init__(self, state_file: Path):
        """Initialize state manager.

        Args:
            state_file: Path to the JSON state file
        """
        self.state_file = state_file
        self._data: dict[str, Any] = {"version": self.VERSION, "subjects": {}}
        self._load()

    def _load(self) -> None:
        """Load state from file if it exists."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)

                # Validate version
                if loaded.get("version") == self.VERSION:
                    self._data = loaded
                else:
                    import sys

                    print(
                        "Warning: State file version mismatch, starting fresh",
                        file=sys.stderr,
                    )

            except (json.JSONDecodeError, OSError) as e:
                print(f"Warning: Could not load state file: {e}")

    def _save(self) -> None:
        """Save state to file atomically."""
        # Ensure parent directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file then rename (atomic on POSIX)
        temp_file = self.state_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)

            temp_file.replace(self.state_file)
        except OSError as e:
            print(f"Warning: Could not save state file: {e}")
            if temp_file.exists():
                temp_file.unlink()

    def save(self) -> None:
        """Persist the current state to disk."""
        self._save()

    def is_batch_completed(self, key: DocumentKey, batch_index: int) -> bool:
        """Check if a batch has been completed.

        Args:
            key: DocumentKey identifying the document
            batch_index: Zero-based batch index

        Returns:
            True if the batch is marked as completed
        """
        subjects = self._data.get("subjects", {})
        subject_data = subjects.get(key.subject, {})
        doc_data = subject_data.get(key.filename, {})
        completed = doc_data.get("completed_batches", [])

        return batch_index in completed

    def mark_batch_completed(
        self,
        key: DocumentKey,
        batch_index: int,
        total_issues: int | None = None,
    ) -> None:
        """Mark a batch as completed.

        Args:
            key: DocumentKey identifying the document
            batch_index: Zero-based batch index
            total_issues: Optional total issue count for the document
        """
        subjects = self._data.setdefault("subjects", {})
        subject_data = subjects.setdefault(key.subject, {})
        doc_data = subject_data.setdefault(
            key.filename, {"completed_batches": [], "total_issues": 0}
        )

        # Add batch index if not already present
        if batch_index not in doc_data["completed_batches"]:
            doc_data["completed_batches"].append(batch_index)
            doc_data["completed_batches"].sort()

        # Update total issues if provided
        if total_issues is not None:
            doc_data["total_issues"] = total_issues

        self._save()

    def remove_batch_completion(self, key: DocumentKey, batch_index: int) -> None:
        """Remove a batch from completed state (for refetching).

        Args:
            key: DocumentKey identifying the document
            batch_index: Zero-based batch index to remove
        """
        subjects = self._data.get("subjects", {})
        subject_data = subjects.get(key.subject, {})
        doc_data = subject_data.get(key.filename, {})

        if (
            "completed_batches" in doc_data
            and batch_index in doc_data["completed_batches"]
        ):
            doc_data["completed_batches"].remove(batch_index)
            self._save()

    def clear_document(self, key: DocumentKey) -> None:
        """Clear all state for a document.

        Args:
            key: DocumentKey identifying the document
        """
        subjects = self._data.get("subjects", {})
        if key.subject in subjects:
            subjects[key.subject].pop(key.filename, None)

            # Clean up empty subjects
            if not subjects[key.subject]:
                subjects.pop(key.subject)

        self._save()

    def clear_all(self) -> None:
        """Clear all state."""
        self._data = {"version": self.VERSION, "subjects": {}}
        self._save()

    def get_completed_count(self, key: DocumentKey) -> int:
        """Get the number of completed batches for a document.

        Args:
            key: DocumentKey identifying the document

        Returns:
            Number of completed batches
        """
        subjects = self._data.get("subjects", {})
        subject_data = subjects.get(key.subject, {})
        doc_data = subject_data.get(key.filename, {})
        return len(doc_data.get("completed_batches", []))
