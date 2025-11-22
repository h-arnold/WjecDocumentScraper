"""Marker PDF to Markdown converter implementation."""

import os
from pathlib import Path
from typing import Any

from .base import ConversionResult, PdfToMarkdownConverter


class MarkerConverter(PdfToMarkdownConverter):
    """Converter using the marker library."""

    def __init__(self, *, dotenv_path: str | Path | None = None) -> None:
        from dotenv import load_dotenv
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict

        # Load environment variables from .env file before accessing GEMINI_API_KEY
        if dotenv_path is not None:
            load_dotenv(dotenv_path=Path(dotenv_path))
        else:
            load_dotenv()

        self._model_dict = create_model_dict()
        self._config: dict[str, Any] = {
            "paginate_output": True,
            "use_llm": True,
            "gemini_api_key": os.environ.get("GEMINI_API_KEY"),
            "gemini_model_name": "gemini-2.5-flash-lite",
        }
        self._converter = PdfConverter(
            artifact_dict=self._model_dict,
            config=self._config,
        )

    def convert(self, pdf_path: Path) -> ConversionResult:
        """Convert a PDF using marker."""
        rendered = self._converter(str(pdf_path))

        if hasattr(rendered, "markdown"):
            markdown_output = rendered
        else:
            from marker.renderers.markdown import MarkdownRenderer

            renderer = MarkdownRenderer(config=self._config)
            markdown_output = renderer(rendered)

        markdown_text = getattr(markdown_output, "markdown", None)
        if markdown_text is None:
            raise ValueError("Marker conversion did not return markdown output")

        metadata: dict[str, Any] | None = None
        images = getattr(markdown_output, "images", None)
        details = getattr(markdown_output, "metadata", None)

        if images is not None or details is not None:
            metadata = {}
            if images is not None:
                metadata["images"] = images
            if details is not None:
                metadata["metadata"] = details

        # cleaned_markdown = _normalise_marker_markdown(markdown_text)
        return ConversionResult(markdown=markdown_text, metadata=metadata)

    def close(self) -> None:
        pass
