"""Tests for PDF to Markdown converters."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from types import SimpleNamespace

from src.converters.converters import (
    ConversionResult,
    MarkerConverter,
    MarkItDownConverter,
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
    pdf_path = (
        project_root
        / "Documents"
        / "Digital-Media-and-Film"
        / "pdfs"
        / "wjec-gcse-digital-media-and-film-specification.pdf"
    )

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
    import os
    
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
    import os
    
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
