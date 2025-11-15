"""Document key dataclass for identifying documents across the codebase.

This provides a consistent way to reference documents by subject and filename,
particularly useful for the LLM categoriser and other document-processing workflows.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentKey:
    """Immutable key identifying a document by subject and filename.
    
    Attributes:
        subject: The subject name (e.g., "Art-and-Design")
        filename: The document filename (e.g., "gcse-art-and-design---delivery-guide.md")
    """
    
    subject: str
    filename: str
    
    def __str__(self) -> str:
        """Return a human-readable string representation."""
        return f"{self.subject}/{self.filename}"
