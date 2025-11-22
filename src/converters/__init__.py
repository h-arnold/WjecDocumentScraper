"""PDF to Markdown converters and LLM integration."""

from __future__ import annotations

from .base import ConversionResult, PdfToMarkdownConverter
from .converters import create_converter
from .docling_converter import DoclingConverter
from .marker_converter import MarkerConverter

# LLM providers live under `src.llm` now — import directly from there when needed.

__all__ = [
    "ConversionResult",
    "PdfToMarkdownConverter",
    # MarkItDown support removed; only MarkerConverter is exported from this module.
    # Other converters (e.g., DoclingConverter) exist in converters.py; export DoclingConverter here
    # so callers may import it directly from `src.converters`.
    "MarkerConverter",
    "DoclingConverter",
    "create_converter",
    # LLM specific exports were removed. Import via `src.llm` instead.
]
