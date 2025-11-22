"""Docling PDF to Markdown converter implementation."""

from pathlib import Path

from .base import ConversionResult, PdfToMarkdownConverter


class DoclingConverter(PdfToMarkdownConverter):
    """Converter using the docling library."""

    _PAGE_MARKER_DASHES = 48
    _PAGE_MARKER_PLACEHOLDER = "{DOCLING_PAGE}"

    def __init__(self) -> None:
        from docling.document_converter import DocumentConverter

        self._converter = DocumentConverter()

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
