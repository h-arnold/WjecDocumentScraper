"""Tests for PDF to Markdown converters."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from converters import (
    ConversionResult,
    PdfToMarkdownConverter,
    MarkItDownConverter,
    create_converter,
)


def test_conversion_result_creation() -> None:
    """Test that ConversionResult can be created."""
    result = ConversionResult(markdown="# Test")
    assert result.markdown == "# Test"
    assert result.metadata is None


def test_conversion_result_with_metadata() -> None:
    """Test that ConversionResult can store metadata."""
    result = ConversionResult(
        markdown="# Test",
        metadata={"key": "value"}
    )
    assert result.markdown == "# Test"
    assert result.metadata == {"key": "value"}


def test_create_converter_markitdown() -> None:
    """Test creating a MarkItDown converter."""
    converter = create_converter("markitdown")
    assert isinstance(converter, MarkItDownConverter)
    assert isinstance(converter, PdfToMarkdownConverter)
    converter.close()


def test_create_converter_case_insensitive() -> None:
    """Test that converter type is case-insensitive."""
    converter1 = create_converter("markitdown")
    converter2 = create_converter("MARKITDOWN")
    converter3 = create_converter("MarkItDown")
    
    assert isinstance(converter1, MarkItDownConverter)
    assert isinstance(converter2, MarkItDownConverter)
    assert isinstance(converter3, MarkItDownConverter)
    
    converter1.close()
    converter2.close()
    converter3.close()


def test_create_converter_invalid_type() -> None:
    """Test that invalid converter type raises ValueError."""
    try:
        create_converter("invalid")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unknown converter type: invalid" in str(e)
        assert "markitdown" in str(e).lower()
        assert "marker" in str(e).lower()


def test_markitdown_converter_with_real_pdf(tmp_path: Path) -> None:
    """Test MarkItDown converter with a real PDF file."""
    # Find a PDF in the Documents directory
    project_root = Path(__file__).resolve().parents[1]
    pdf_path = project_root / "Documents" / "Digital-Media-and-Film" / "pdfs" / "wjec-gcse-digital-media-and-film-specification.pdf"
    
    if not pdf_path.exists():
        # Skip test if no PDF is available
        return
    
    converter = MarkItDownConverter()
    try:
        result = converter.convert(pdf_path)
        
        assert isinstance(result, ConversionResult)
        assert result.markdown is not None
        assert len(result.markdown) > 0
        assert isinstance(result.markdown, str)
        
        # Check that the markdown contains expected content
        assert "WJEC" in result.markdown or "Digital Media" in result.markdown
    finally:
        converter.close()


def test_converter_close_is_safe() -> None:
    """Test that calling close multiple times is safe."""
    converter = MarkItDownConverter()
    converter.close()
    converter.close()  # Should not raise
