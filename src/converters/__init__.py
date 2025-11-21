"""PDF to Markdown converters and LLM integration."""

from __future__ import annotations

from .converters import (
    ConversionResult,
    MarkerConverter,
    PdfToMarkdownConverter,
    create_converter,
)

# LLM providers live under `src.llm` now — import directly from there when needed.

__all__ = [
    "ConversionResult",
    "PdfToMarkdownConverter",
    # MarkItDown support removed; only MarkerConverter is exported.
    "MarkerConverter",
    "create_converter",
    # LLM specific exports were removed. Import via `src.llm` instead.
]
