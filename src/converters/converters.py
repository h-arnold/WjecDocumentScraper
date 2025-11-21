"""PDF to Markdown converters with pluggable backends."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _is_table_separator_row(row: str) -> bool:
    """Return True if the row is a Markdown table separator row."""
    stripped = row.strip()
    if not stripped.startswith("|"):
        return False
    inner = stripped.strip("|")
    parts = [part.strip() for part in inner.split("|")]
    if not parts:
        return False
    for part in parts:
        if not part:
            return False
        if set(part) - {"-", ":"}:
            return False
    return True


def _split_table_row(row: str) -> list[str]:
    """Split a Markdown table row into individual cell values."""
    inner = row.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [cell.strip() for cell in inner.split("|")]


def _rebuild_table_row(cells: list[str]) -> str:
    """Rebuild a Markdown table row from cleaned cell values."""
    return "| " + " | ".join(cell.strip() for cell in cells) + " |"


def _clean_marker_table_cell(cell: str) -> str:
    """Normalise `<br>` usage inside a single table cell."""
    if "<br" not in cell:
        return cell.strip()

    normalised = cell.replace("<br />", "<br>").replace("<br/>", "<br>")
    parts = [fragment.strip() for fragment in normalised.split("<br>")]
    parts = [fragment for fragment in parts if fragment]

    if not parts:
        return ""

    prefix: list[str] = []
    bullets: list[str] = []
    current_bullet: list[str] | None = None

    for fragment in parts:
        if fragment.startswith("•"):
            # Close any in-flight bullet before starting a new one.
            if current_bullet is not None:
                combined = " ".join(current_bullet).strip()
                if combined:
                    bullets.append(combined)

            entry = fragment.lstrip("•").strip()
            current_bullet = [entry] if entry else []
            continue

        if current_bullet is None:
            prefix.append(fragment)
        else:
            current_bullet.append(fragment)

    if current_bullet is not None:
        combined = " ".join(current_bullet).strip()
        if combined:
            bullets.append(combined)

    if bullets:
        bullet_markup = "".join(f"<li>{item}</li>" for item in bullets)
        prefix_text = " ".join(prefix).strip()
        if prefix_text:
            return f"{prefix_text} <ul>{bullet_markup}</ul>"
        return f"<ul>{bullet_markup}</ul>"

    return " ".join(parts).strip()


def _normalise_marker_markdown(markdown: str) -> str:
    """Normalise marker output so table cells avoid raw `<br>` tags."""
    lines = markdown.splitlines()
    cleaned: list[str] = []
    idx = 0

    while idx < len(lines):
        line = lines[idx]
        stripped = line.lstrip()
        if stripped.startswith("|") and "|" in stripped:
            table_block: list[str] = []
            while idx < len(lines):
                candidate = lines[idx]
                if not candidate.lstrip().startswith("|"):
                    break
                table_block.append(candidate)
                idx += 1

            cleaned.extend(_clean_marker_table_block(table_block))
            continue

        cleaned.append(line)
        idx += 1

    return "\n".join(cleaned)


def _clean_marker_table_block(rows: list[str]) -> list[str]:
    """Clean a block of Markdown table rows produced by marker."""
    cleaned_rows: list[str] = []

    for row in rows:
        stripped = row.strip()
        if not stripped.startswith("|"):
            cleaned_rows.append(row)
            continue

        if _is_table_separator_row(row):
            cleaned_rows.append(row)
            continue

        cells = _split_table_row(row)
        if not any("<br" in cell for cell in cells):
            cleaned_rows.append(row)
            continue

        cleaned_cells = [_clean_marker_table_cell(cell) for cell in cells]
        cleaned_rows.append(_rebuild_table_row(cleaned_cells))

    return cleaned_rows


@dataclass
class ConversionResult:
    """Result of a PDF to Markdown conversion."""

    markdown: str
    """The converted markdown text."""

    metadata: dict[str, Any] | None = None
    """Optional metadata about the conversion."""


class PdfToMarkdownConverter(ABC):
    """Abstract base class for PDF to Markdown converters."""

    @abstractmethod
    def convert(self, pdf_path: Path) -> ConversionResult:
        """Convert a PDF file to Markdown.

        Args:
            pdf_path: Path to the PDF file to convert.

        Returns:
            ConversionResult containing the markdown text and optional metadata.

        Raises:
            Exception: If the conversion fails.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Clean up any resources held by the converter."""
        pass


class MarkItDownConverter(PdfToMarkdownConverter):
    """Converter using the MarkItDown library."""

    def __init__(self) -> None:
        from markitdown import MarkItDown

        self._converter = MarkItDown()

    def convert(self, pdf_path: Path) -> ConversionResult:
        """Convert a PDF using MarkItDown."""
        result = self._converter.convert(pdf_path)
        return ConversionResult(markdown=result.markdown)

    def close(self) -> None:
        """MarkItDown doesn't require cleanup."""
        pass


class MarkerConverter(PdfToMarkdownConverter):
    """Converter using the marker library."""

    def __init__(self, *, dotenv_path: str | Path | None = None) -> None:
        from dotenv import load_dotenv
        from marker.converters.pdf import PdfConverter
        from marker.converters.ocr import OCRConverter
        from marker.models import create_model_dict

        # Load environment variables from .env file before accessing GEMINI_API_KEY
        if dotenv_path is not None:
            load_dotenv(dotenv_path=Path(dotenv_path))
        else:
            load_dotenv()

        self._model_dict = create_model_dict()
        # Enable page markers so output matches marker CLI --paginate flag.
        # Default marker config: enable page markers and LLM mode with Gemini.
        # Use GEMINI_API_KEY environment variable by default; if not present,
        # Marker will still attempt to read credentials from the environment
        # but verify_config_keys will raise if the service is configured without
        # the required values at runtime.
        self._config: dict[str, Any] = {
            "paginate_output": True,
            "use_llm": True,
            "gemini_api_key": os.environ.get("GEMINI_API_KEY"),
            "gemini_model_name": "gemini-2.5-flash-lite",
        }
        self._converter = PdfConverter(
            artifact_dict=self._model_dict,
            config=self._config,
        )

    def convert(self, pdf_path: Path) -> ConversionResult:
        """Convert a PDF using marker."""
        # PdfConverter can return either a full Document (old API) or a MarkdownOutput
        rendered = self._converter(str(pdf_path))

        if hasattr(rendered, "markdown"):
            markdown_output = rendered
        else:
            # Fallback for older versions that require an explicit renderer
            from marker.renderers.markdown import MarkdownRenderer

            renderer = MarkdownRenderer(config=self._config)
            markdown_output = renderer(rendered)

        markdown_text = getattr(markdown_output, "markdown", None)
        if markdown_text is None:  # pragma: no cover - defensive guard
            raise ValueError("Marker conversion did not return markdown output")

        metadata: dict[str, Any] | None = None
        images = getattr(markdown_output, "images", None)
        details = getattr(markdown_output, "metadata", None)

        if images is not None or details is not None:
            metadata = {}
            if images is not None:
                metadata["images"] = images
            if details is not None:
                metadata["metadata"] = details

        # LLM-enhanced OCR should produce cleaner output; skip normalization for now.
        # cleaned_markdown = _normalise_marker_markdown(markdown_text)

        return ConversionResult(markdown=markdown_text, metadata=metadata)

    def close(self) -> None:
        """Clean up marker resources if needed."""
        # Marker may hold GPU resources; clean up if needed
        pass


def create_converter(
    converter_type: str, *, dotenv_path: str | Path | None = None
) -> PdfToMarkdownConverter:
    """Factory function to create a converter of the specified type.

    Args:
        converter_type: Type of converter to create ('markitdown' or 'marker').
        dotenv_path: Optional path to .env file for loading environment variables.
                     Only used by converters that need API keys (e.g., marker with Gemini).

    Returns:
        A PdfToMarkdownConverter instance.

    Raises:
        ValueError: If the converter type is not recognized.
    """
    converter_type = converter_type.lower()

    if converter_type == "markitdown":
        return MarkItDownConverter()
    elif converter_type == "marker":
        return MarkerConverter(dotenv_path=dotenv_path)
    else:
        raise ValueError(
            f"Unknown converter type: {converter_type}. "
            f"Valid options are: 'markitdown', 'marker'"
        )
