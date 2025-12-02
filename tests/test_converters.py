"""Tests for PDF to Markdown converters."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.converters.converters import (
    ConversionResult,
    DoclingConverter,
    MarkerConverter,
    PdfToMarkdownConverter,
    _normalise_marker_markdown,
    create_converter,
)


def test_conversion_result_creation() -> None:
    """Test that ConversionResult can be created."""
    result = ConversionResult(markdown="# Test")
    assert result.markdown == "# Test"
    assert result.metadata is None


def test_conversion_result_with_metadata() -> None:
    """Test that ConversionResult can store metadata."""
    result = ConversionResult(markdown="# Test", metadata={"key": "value"})
    assert result.markdown == "# Test"
    assert result.metadata == {"key": "value"}


def test_create_converter_case_insensitive() -> None:
    """Test that converter type is case-insensitive for 'marker'."""
    converter1 = create_converter("marker")
    converter2 = create_converter("MARKER")

    assert isinstance(converter1, MarkerConverter)
    assert isinstance(converter2, MarkerConverter)

    converter1.close()
    converter2.close()


def test_create_converter_invalid_type() -> None:
    """Test that invalid converter type raises ValueError."""
    try:
        create_converter("invalid")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unknown converter type: invalid" in str(e)
        assert "marker" in str(e).lower()


def test_converter_close_is_safe() -> None:
    """Test that calling close multiple times is safe for MarkerConverter."""
    converter = MarkerConverter()
    converter.close()
    converter.close()  # Should not raise


def test_marker_converter_handles_markdown_output(monkeypatch, tmp_path: Path) -> None:
    """Marker should accept MarkdownOutput objects without a renderer."""

    class DummyMarkdownOutput:
        def __init__(self) -> None:
            self.markdown = "# Converted"
            self.images = {"image.png": object()}
            self.metadata = {"source": "test"}

    class DummyPdfConverter:
        def __init__(self, artifact_dict, config=None):
            assert artifact_dict == {"fake": True}
            # Config now includes Gemini settings in addition to paginate_output
            assert config.get("paginate_output") is True
            assert "use_llm" in config
            assert "gemini_api_key" in config
            assert "gemini_model_name" in config

        def __call__(self, path: str):
            return DummyMarkdownOutput()

    class FailingRenderer:
        def __init__(self, config=None):
            # Config now includes Gemini settings in addition to paginate_output
            assert config.get("paginate_output") is True

        def __call__(self, document):  # pragma: no cover - guard
            raise AssertionError("MarkdownRenderer should not be used")

    monkeypatch.setattr("marker.models.create_model_dict", lambda: {"fake": True})
    monkeypatch.setattr("marker.converters.pdf.PdfConverter", DummyPdfConverter)
    monkeypatch.setattr("marker.renderers.markdown.MarkdownRenderer", FailingRenderer)

    converter = MarkerConverter()
    try:
        fake_pdf = tmp_path / "dummy.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4\n")

        result = converter.convert(fake_pdf)

        assert isinstance(result, ConversionResult)
        assert result.markdown == "# Converted"
        assert result.metadata is not None
        assert result.metadata.get("metadata") == {"source": "test"}
        assert "images" in result.metadata
        assert isinstance(result.metadata["images"], dict)
    finally:
        converter.close()


def test_marker_converter_falls_back_to_renderer(monkeypatch, tmp_path: Path) -> None:
    """Marker should fall back to MarkdownRenderer when needed."""

    dummy_document = SimpleNamespace(name="doc")

    class DummyPdfConverter:
        def __init__(self, artifact_dict, config=None):
            assert artifact_dict == {"fake": True}
            # Config now includes Gemini settings in addition to paginate_output
            assert config.get("paginate_output") is True
            assert "use_llm" in config
            assert "gemini_api_key" in config
            assert "gemini_model_name" in config

        def __call__(self, path: str):
            return dummy_document

    class DummyMarkdownOutput:
        def __init__(self) -> None:
            self.markdown = "# Rendered"
            self.images = None
            self.metadata = {"renderer": "used"}

    class CapturingRenderer:
        def __init__(self, config=None):
            # Config now includes Gemini settings in addition to paginate_output
            assert config.get("paginate_output") is True

        def __call__(self, document):
            assert document is dummy_document
            return DummyMarkdownOutput()

    monkeypatch.setattr("marker.models.create_model_dict", lambda: {"fake": True})
    monkeypatch.setattr("marker.converters.pdf.PdfConverter", DummyPdfConverter)
    monkeypatch.setattr("marker.renderers.markdown.MarkdownRenderer", CapturingRenderer)

    converter = MarkerConverter()
    try:
        fake_pdf = tmp_path / "dummy.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4\n")

        result = converter.convert(fake_pdf)

        assert isinstance(result, ConversionResult)
        assert result.markdown == "# Rendered"
        assert result.metadata == {"metadata": {"renderer": "used"}}
    finally:
        converter.close()


def test_normalise_marker_markdown_preserves_tables_without_breaks() -> None:
    """Normalisation should leave tables without <br> untouched."""

    markdown = "| A | B |\n| - | - |\n| 1 | 2 |"
    assert _normalise_marker_markdown(markdown) == markdown


def test_normalise_marker_markdown_converts_breaks_to_lists() -> None:
    """Normalisation should replace marker <br> sequences while preserving structure."""

    raw = (
        "| Section | Amplification |"
        "\n"
        "| --- | --- |"
        "\n"
        "| 2.2.3a<br>Wave properties | Learners should understand:<br>•<br>use and draw graphical representations of waves from<br>given values of amplitude and wavelength<br>•<br>use the equation:<br>wave speed = frequency x<br>wavelength. |"
    )

    expected = (
        "| Section | Amplification |"
        "\n"
        "| --- | --- |"
        "\n"
        "| 2.2.3a Wave properties | Learners should understand: <ul><li>use and draw graphical representations of waves from given values of amplitude and wavelength</li><li>use the equation: wave speed = frequency x wavelength.</li></ul> |"
    )

    assert _normalise_marker_markdown(raw) == expected


def test_marker_converter_accepts_dotenv_path(monkeypatch, tmp_path: Path) -> None:
    """Test that MarkerConverter accepts and uses dotenv_path parameter."""
    # Create a test .env file with a custom API key
    env_file = tmp_path / "test.env"
    env_file.write_text("GEMINI_API_KEY=test_key_from_file\n", encoding="utf-8")

    # Clear any existing GEMINI_API_KEY from environment
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # Mock the marker components
    class DummyPdfConverter:
        def __init__(self, artifact_dict, config=None):
            # Store the config for verification
            self.config = config

        def __call__(self, path: str):
            return SimpleNamespace(markdown="# Test", images=None, metadata=None)

    monkeypatch.setattr("marker.models.create_model_dict", lambda: {"fake": True})
    monkeypatch.setattr("marker.converters.pdf.PdfConverter", DummyPdfConverter)

    # Create converter with dotenv_path
    converter = MarkerConverter(dotenv_path=env_file)

    # Verify that the environment variable was loaded
    assert os.environ.get("GEMINI_API_KEY") == "test_key_from_file"

    # Verify that the converter config has the API key
    assert converter._config["gemini_api_key"] == "test_key_from_file"

    converter.close()


def test_create_converter_passes_dotenv_path(monkeypatch, tmp_path: Path) -> None:
    """Test that create_converter factory passes dotenv_path to MarkerConverter."""
    # Create a test .env file
    env_file = tmp_path / "factory_test.env"
    env_file.write_text("GEMINI_API_KEY=factory_test_key\n", encoding="utf-8")

    # Clear any existing GEMINI_API_KEY from environment
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # Mock the marker components
    class DummyPdfConverter:
        def __init__(self, artifact_dict, config=None):
            self.config = config

        def __call__(self, path: str):
            return SimpleNamespace(markdown="# Test", images=None, metadata=None)

    monkeypatch.setattr("marker.models.create_model_dict", lambda: {"fake": True})
    monkeypatch.setattr("marker.converters.pdf.PdfConverter", DummyPdfConverter)

    # Create converter through factory with dotenv_path
    converter = create_converter("marker", dotenv_path=env_file)

    # Verify that the environment variable was loaded
    assert os.environ.get("GEMINI_API_KEY") == "factory_test_key"

    # Verify that the converter config has the API key
    assert converter._config["gemini_api_key"] == "factory_test_key"

    converter.close()


def test_docling_converter_adds_page_markers(monkeypatch, tmp_path: Path) -> None:
    """DoclingConverter should add page markers in the marker format."""

    class DummyDocumentConverter:
        def __init__(self):
            pass

        def convert(self, path: Path):
            # Mock document with export_to_markdown accepting page_break_placeholder
            def export_to_markdown(page_break_placeholder=None):
                if page_break_placeholder:
                    # Simulate docling inserting placeholders between pages
                    # For a 2-page PDF, there's 1 placeholder between the pages
                    return (
                        f"Page 0 content\n\n{page_break_placeholder}\n\n"
                        f"Page 1 content"
                    )
                return "Page 0 content\n\nPage 1 content"

            return SimpleNamespace(
                document=SimpleNamespace(export_to_markdown=export_to_markdown)
            )

    monkeypatch.setattr(
        "docling.document_converter.DocumentConverter", DummyDocumentConverter
    )

    from src.converters.converters import create_converter

    converter = create_converter("docling")
    try:
        fake_pdf = tmp_path / "docling.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4\n")

        result = converter.convert(fake_pdf)

        # Should have page markers in the marker format: {N}----...
        assert "{1}------------------------------------------------" in result.markdown
        assert "{2}------------------------------------------------" in result.markdown

        # Verify page markers are numbered sequentially
        # With 2 pages and 1 placeholder between them, we should have 2 markers: {1} and {2}
        import re

        pattern = re.compile(r"^\{(\d+)\}[-]+\s*$", re.MULTILINE)
        matches = list(pattern.finditer(result.markdown))
        assert len(matches) == 2, f"Expected 2 page markers, got {len(matches)}"
        assert matches[0].group(1) == "1"
        assert matches[1].group(1) == "2"

        # Verify each marker has exactly 48 dashes
        for match in matches:
            assert match.group(0).strip().count("-") == 48

        # Verify markers appear before content
        assert result.markdown.find("{1}") < result.markdown.find("Page 0 content")
        assert result.markdown.find("{2}") < result.markdown.find("Page 1 content")
    finally:
        converter.close()


def test_docling_converter_page_markers_work_with_page_utils(
    monkeypatch, tmp_path: Path
) -> None:
    """DoclingConverter page markers should be compatible with page_utils."""

    class DummyDocumentConverter:
        def __init__(self):
            pass

        def convert(self, path: Path):
            def export_to_markdown(page_break_placeholder=None):
                if page_break_placeholder:
                    # Simulate a 2-page PDF with 1 placeholder between pages
                    return f"First page\n\n{page_break_placeholder}\n\n" f"Second page"
                return "First page\n\nSecond page"

            return SimpleNamespace(
                document=SimpleNamespace(export_to_markdown=export_to_markdown)
            )

    monkeypatch.setattr(
        "docling.document_converter.DocumentConverter", DummyDocumentConverter
    )

    from src.converters.converters import create_converter
    from src.utils.page_utils import build_page_number_map, find_page_markers

    converter = create_converter("docling")
    try:
        fake_pdf = tmp_path / "docling.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4\n")

        result = converter.convert(fake_pdf)

        # Test with page_utils functions
        # With 2 pages, we should have 2 markers: {1} and {2}
        markers = find_page_markers(result.markdown)
        assert len(markers) == 2, f"Expected 2 page markers, got {len(markers)}"
        assert markers[0].page_number == 1
        assert markers[1].page_number == 2

        # Verify markers appear before content
        assert result.markdown.find("{1}") < result.markdown.find("First page")
        assert result.markdown.find("{2}") < result.markdown.find("Second page")

        # Test page number map
        page_map = build_page_number_map(result.markdown)
        assert len(page_map) > 0
    finally:
        converter.close()
