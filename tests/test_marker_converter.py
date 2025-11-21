from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.converters.converters import MarkerConverter


@pytest.fixture()
def sample_pdf_path() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "sample-short.pdf"


def test_marker_converter_enables_paginated_output(
    monkeypatch: pytest.MonkeyPatch, sample_pdf_path: Path
) -> None:
    captured: dict[str, object] = {}

    class DummyPdfConverter:
        def __init__(
            self,
            *,
            artifact_dict: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> None:
            captured["artifact_dict"] = artifact_dict
            captured["config"] = config

        def __call__(self, pdf_path: str) -> types.SimpleNamespace:
            captured["pdf_path"] = Path(pdf_path)
            return types.SimpleNamespace(
                markdown="page 1 content",
                images={"img-1": b""},
                metadata={"page_count": 1},
            )

        def close(self) -> None:  # pragma: no cover - defensive guard
            captured["closed"] = True

    monkeypatch.setattr("marker.models.create_model_dict", lambda: {"model": object()})
    monkeypatch.setattr("marker.converters.pdf.PdfConverter", DummyPdfConverter)

    converter = MarkerConverter()

    result = converter.convert(sample_pdf_path)

    # Config now includes Gemini settings in addition to paginate_output
    assert captured["config"]["paginate_output"] is True
    assert captured["config"]["use_llm"] is True
    assert "gemini_api_key" in captured["config"]
    assert "gemini_model_name" in captured["config"]
    assert captured["pdf_path"] == sample_pdf_path
    assert result.markdown == "page 1 content"
    assert result.metadata == {
        "images": {"img-1": b""},
        "metadata": {"page_count": 1},
    }


def test_marker_converter_injects_page_markers(
    monkeypatch: pytest.MonkeyPatch, sample_pdf_path: Path
) -> None:
    captured: dict[str, object] = {}

    class DummyPdfConverter:
        def __init__(
            self,
            *,
            artifact_dict: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> None:
            captured["artifact_dict"] = artifact_dict
            captured["converter_config"] = config

        def __call__(self, pdf_path: str) -> object:
            captured["pdf_path"] = Path(pdf_path)
            return object()

        def close(self) -> None:  # pragma: no cover - defensive guard
            captured["closed"] = True

    class DummyMarkdownRenderer:
        def __init__(self, config: dict[str, object] | None = None) -> None:
            captured["renderer_config"] = config
            self.paginate_output = config.get("paginate_output") if config else None

        def __call__(self, document: object) -> types.SimpleNamespace:
            captured["renderer_document"] = document
            hyphen_line = "-" * 48
            markdown = f"\n\n{{1}}{hyphen_line}\n\nPage body\n\n"
            return types.SimpleNamespace(
                markdown=markdown, images={}, metadata={"page_count": 1}
            )

    monkeypatch.setattr("marker.models.create_model_dict", lambda: {"model": object()})
    monkeypatch.setattr("marker.converters.pdf.PdfConverter", DummyPdfConverter)
    monkeypatch.setattr(
        "marker.renderers.markdown.MarkdownRenderer", DummyMarkdownRenderer
    )

    converter = MarkerConverter()
    try:
        result = converter.convert(sample_pdf_path)
    finally:
        converter.close()

    # Config now includes Gemini settings in addition to paginate_output
    assert captured["converter_config"]["paginate_output"] is True
    assert captured["converter_config"]["use_llm"] is True
    assert "gemini_api_key" in captured["converter_config"]
    assert "gemini_model_name" in captured["converter_config"]
    
    # Renderer still gets the same config
    assert captured["renderer_config"]["paginate_output"] is True
    assert captured["renderer_config"]["use_llm"] is True
    assert captured["pdf_path"] == sample_pdf_path
    assert captured["renderer_document"] is not None

    assert result.markdown.startswith("\n\n{1}")
    assert "Page body" in result.markdown
    assert result.metadata == {"metadata": {"page_count": 1}, "images": {}}
