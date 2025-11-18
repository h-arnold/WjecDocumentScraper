from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from src.models.document_key import DocumentKey


@dataclass
class ReviewConfiguration(ABC):
    """Base configuration for any review pass."""

    # Input/Output
    input_csv_path: Path
    output_base_dir: Path
    output_subdir: str  # e.g., "document_reports" or "fact_check_reports"

    # Batch settings
    batch_size: int
    max_retries: int

    # State management
    state_file: Path

    # Filtering
    subjects: set[str] | None
    documents: set[str] | None

    # LLM settings
    llm_provider: str | None
    fail_on_quota: bool

    # Logging
    log_raw_responses: bool
    log_response_dir: Path

    # CSV output columns (configurable per review pass)
    output_csv_columns: list[str]

    @abstractmethod
    def get_output_path(self, key: DocumentKey) -> Path:
        """Get output path for a specific document."""
        pass
