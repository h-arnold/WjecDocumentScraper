"""Helper module for configuring Docling converter with common options.

This module provides utilities to easily create Docling configuration objects
for common use cases, matching the pattern from your example.

Example usage:
    from src.converters.docling_config import create_accurate_pipeline_options
    from src.converters.converters import create_converter
    
    pipeline_options = create_accurate_pipeline_options()
    converter = create_converter("docling", pipeline_options=pipeline_options)
"""

from typing import Any


def create_accurate_pipeline_options() -> Any:
    """Create PdfPipelineOptions configured for best accuracy.

    Returns:
        PdfPipelineOptions configured with:
        - OCR enabled for images (footers, etc.)
        - Table extraction with cell matching
        - Accurate table structure mode for multi-row headers
        - RapidOCR for best image text extraction
        - Hardware acceleration with 4 threads

    Requires: pip install docling rapidocr onnxruntime
    """
    from docling.datamodel.accelerator_options import (
        AcceleratorDevice,
        AcceleratorOptions,
    )
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        RapidOcrOptions,
        TableFormerMode,
    )

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True  # Enable OCR for images (e.g., footers)
    pipeline_options.do_table_structure = True  # Enable table extraction
    pipeline_options.table_structure_options.do_cell_matching = True
    pipeline_options.table_structure_options.mode = (
        TableFormerMode.ACCURATE  # Best for multi-row headers
    )

    # Use RapidOCR for best image text extraction
    pipeline_options.ocr_options = RapidOcrOptions(
        force_full_page_ocr=True, lang=["en"]
    )

    # Enable hardware acceleration if available
    pipeline_options.accelerator_options = AcceleratorOptions(
        num_threads=4, device=AcceleratorDevice.AUTO
    )

    return pipeline_options


def create_fast_pipeline_options() -> Any:
    """Create PdfPipelineOptions configured for speed over accuracy.

    Returns:
        PdfPipelineOptions configured with:
        - OCR disabled (faster processing)
        - Table extraction enabled without cell matching
        - Fast table structure mode
        - Hardware acceleration
    """
    from docling.datamodel.accelerator_options import (
        AcceleratorDevice,
        AcceleratorOptions,
    )
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False  # Disable OCR for speed
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options.do_cell_matching = False
    pipeline_options.table_structure_options.mode = TableFormerMode.FAST

    # Enable hardware acceleration
    pipeline_options.accelerator_options = AcceleratorOptions(
        num_threads=4, device=AcceleratorDevice.AUTO
    )

    return pipeline_options


def create_ocr_only_pipeline_options(lang: list[str] | None = None) -> Any:
    """Create PdfPipelineOptions for OCR-focused processing.

    Args:
        lang: List of language codes for OCR (default: ["en"]).
              Examples: ["en"], ["en", "fr"], ["zh", "ja"]

    Returns:
        PdfPipelineOptions configured with OCR enabled and table extraction disabled.
    """
    from docling.datamodel.accelerator_options import (
        AcceleratorDevice,
        AcceleratorOptions,
    )
    from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions

    if lang is None:
        lang = ["en"]

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = False
    pipeline_options.ocr_options = RapidOcrOptions(force_full_page_ocr=True, lang=lang)
    pipeline_options.accelerator_options = AcceleratorOptions(
        num_threads=4, device=AcceleratorDevice.AUTO
    )

    return pipeline_options
