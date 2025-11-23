"""Docling PDF to Markdown converter implementation."""

from pathlib import Path
from typing import Any

from .base import ConversionResult, PdfToMarkdownConverter


class DoclingConverter(PdfToMarkdownConverter):
    """Converter using the docling library with accurate table and OCR support.

    By default, uses accurate pipeline options optimized for complex PDFs with
    many tables and awkward formatting. Supports optional configuration parameters.
    Common parameters include:
        - pipeline_options: PdfPipelineOptions for OCR, table extraction, etc.
        - format_options: Dict mapping InputFormat to format-specific options.
        - accelerator_options: AcceleratorOptions for hardware acceleration.
    """

    _PAGE_MARKER_DASHES = 48
    _PAGE_MARKER_PLACEHOLDER = "{DOCLING_PAGE}"

    def __init__(
        self,
        pipeline_options: Any | None = None,
        format_options: dict[str, Any] | None = None,
        **converter_kwargs: Any,
    ) -> None:
        """Initialize the DoclingConverter with optional pipeline and format options.

        By default, uses accurate pipeline options (OCR enabled, accurate table mode,
        RapidOCR) which are optimized for complex PDFs with tables and awkward formatting.

        Args:
            pipeline_options: Docling PdfPipelineOptions for configuring PDF processing.
                            If None, defaults to create_accurate_pipeline_options().
                            If provided, will be used to create a PdfFormatOption.
            format_options: Dict mapping InputFormat to format-specific options.
                          If pipeline_options is provided and format_options is None,
                          a default PdfFormatOption will be created using pipeline_options.
            **converter_kwargs: Additional keyword arguments to pass to DocumentConverter.
        """
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import DocumentConverter, PdfFormatOption

        from .docling_config import create_accurate_pipeline_options

        # Use accurate pipeline options as default if not provided
        if pipeline_options is None:
            pipeline_options = create_accurate_pipeline_options()

        # Create format_options from pipeline_options if not already specified
        if format_options is None:
            format_options = {
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }

        # Build converter kwargs
        converter_init_kwargs: dict[str, Any] = {"format_options": format_options}

        # Add any additional converter kwargs
        converter_init_kwargs.update(converter_kwargs)

        self._converter = DocumentConverter(**converter_init_kwargs)

    def convert(self, pdf_path: Path) -> ConversionResult:
        result = self._converter.convert(pdf_path)
        placeholder = self._PAGE_MARKER_PLACEHOLDER + "-" * self._PAGE_MARKER_DASHES
        markdown_text = result.document.export_to_markdown(
            page_break_placeholder=placeholder
        )
        markdown_text = self._add_page_numbers(markdown_text)
        return ConversionResult(markdown=markdown_text, metadata={})

    def _add_page_numbers(self, markdown: str) -> str:
        placeholder = self._PAGE_MARKER_PLACEHOLDER + "-" * self._PAGE_MARKER_DASHES
        pages = markdown.split(placeholder)
        result_chunks = []
        for i, page_content in enumerate(pages):
            page_marker = (
                "{" + str(i + 1) + "}" + "-" * self._PAGE_MARKER_DASHES
            )  # 1 index the page number with i + 1
            result_chunks.append(page_marker)
            if page_content.strip():
                result_chunks.append(page_content)
        return "\n\n".join(result_chunks)

    def close(self) -> None:
        pass
