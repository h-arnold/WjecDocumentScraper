"""PDF to Markdown converters with pluggable backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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

    def __init__(self) -> None:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict

        self._model_dict = create_model_dict()
        self._converter = PdfConverter(artifact_dict=self._model_dict)

    def convert(self, pdf_path: Path) -> ConversionResult:
        """Convert a PDF using marker."""
        from marker.renderers.markdown import MarkdownRenderer
        
        # The converter returns a Document object
        document = self._converter(str(pdf_path))
        
        # Use the MarkdownRenderer to convert the document to markdown
        renderer = MarkdownRenderer()
        result = renderer(document)

        # MarkdownOutput has markdown, images, and metadata fields
        return ConversionResult(
            markdown=result.markdown,
            metadata={"images": result.images, "metadata": result.metadata}
        )

    def close(self) -> None:
        """Clean up marker resources if needed."""
        # Marker may hold GPU resources; clean up if needed
        pass


def create_converter(converter_type: str) -> PdfToMarkdownConverter:
    """Factory function to create a converter of the specified type.

    Args:
        converter_type: Type of converter to create ('markitdown' or 'marker').

    Returns:
        A PdfToMarkdownConverter instance.

    Raises:
        ValueError: If the converter type is not recognized.
    """
    converter_type = converter_type.lower()
    
    if converter_type == "markitdown":
        return MarkItDownConverter()
    elif converter_type == "marker":
        return MarkerConverter()
    else:
        raise ValueError(
            f"Unknown converter type: {converter_type}. "
            f"Valid options are: 'markitdown', 'marker'"
        )
