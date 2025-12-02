"""PDF to Markdown converter helpers and exports."""

from pathlib import Path

from .base import ConversionResult, PdfToMarkdownConverter, _normalise_marker_markdown
from .docling_converter import DoclingConverter
from .marker_converter import MarkerConverter

__all__ = [
    "ConversionResult",
    "PdfToMarkdownConverter",
    "MarkerConverter",
    "DoclingConverter",
    "create_converter",
    "_normalise_marker_markdown",
]


def create_converter(
    converter_type: str, *, dotenv_path: str | Path | None = None
) -> PdfToMarkdownConverter:
    """Factory function to create a converter of the specified type.

    Args:
        converter_type: Type of converter to create ('marker' or 'docling').
        dotenv_path: Optional path to .env file for loading environment variables.
                     Only used by converters that need API keys (e.g., marker with Gemini).

    Returns:
        A PdfToMarkdownConverter instance.

    Raises:
        ValueError: If the converter type is not recognized.
    """
    converter_type = converter_type.lower()

    if converter_type == "marker":
        return MarkerConverter(dotenv_path=dotenv_path)
    elif converter_type == "docling":
        return DoclingConverter()
    else:
        raise ValueError(
            f"Unknown converter type: {converter_type}. "
            f"Valid options are: 'marker', 'docling'"
        )
