"""PDF to Markdown converter factory."""

from pathlib import Path
from typing import Any

from .base import PdfToMarkdownConverter
from .docling_converter import DoclingConverter
from .marker_converter import MarkerConverter


def create_converter(
    converter_type: str,
    *,
    dotenv_path: str | Path | None = None,
    pipeline_options: Any | None = None,
    format_options: dict[str, Any] | None = None,
    **converter_kwargs: Any,
) -> PdfToMarkdownConverter:
    """Factory function to create a converter of the specified type.

    Args:
        converter_type: Type of converter to create ('marker' or 'docling').
        dotenv_path: Optional path to .env file for loading environment variables.
                     Only used by converters that need API keys (e.g., marker with Gemini).
        pipeline_options: (Docling only) Docling PdfPipelineOptions for configuring PDF processing.
        format_options: (Docling only) Dict mapping InputFormat to format-specific options.
        **converter_kwargs: Additional keyword arguments passed to the converter.
                          For docling, these are passed to DocumentConverter.

    Returns:
        A PdfToMarkdownConverter instance.

    Raises:
        ValueError: If the converter type is not recognized.
    """
    converter_type = converter_type.lower()

    if converter_type == "marker":
        return MarkerConverter(dotenv_path=dotenv_path)
    elif converter_type == "docling":
        return DoclingConverter(
            pipeline_options=pipeline_options,
            format_options=format_options,
            **converter_kwargs,
        )
    else:
        raise ValueError(
            f"Unknown converter type: {converter_type}. "
            f"Valid options are: 'marker', 'docling'"
        )
