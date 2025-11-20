from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.models.document_key import DocumentKey

from ..core.config import ReviewConfiguration


@dataclass
class ProofreaderConfiguration(ReviewConfiguration):
    """Configuration for the LLM proofreader review pass."""

    def get_output_path(self, key: DocumentKey) -> Path:
        """Get output path for a specific document.

        Path: <output_base_dir>/<subject>/<output_subdir>/<filename>.csv
        """
        report_dir = self.output_base_dir / key.subject / self.output_subdir
        report_dir.mkdir(parents=True, exist_ok=True)

        # Ensure filename ends with .csv
        filename = key.filename
        if filename.endswith(".md"):
            filename = filename[:-3] + ".csv"
        elif not filename.endswith(".csv"):
            filename += ".csv"

        return report_dir / filename
