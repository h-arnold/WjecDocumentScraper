from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from google import genai
from google.genai import types

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.converters.gemini_llm import GeminiLLM


class _DummyResponse:
    def __init__(self, text: Any) -> None:
        self.text = text


class _DummyModels:
    def __init__(self, response_text: Any = "mock-response") -> None:
        self.calls: list[dict[str, object]] = []
        self._response_text = response_text

    def generate_content(self, **kwargs: object) -> _DummyResponse:
        self.calls.append(kwargs)
        return _DummyResponse(text=self._response_text)


class _DummyClient:
    def __init__(self, response_text: Any = "mock-response") -> None:
        self.models = _DummyModels(response_text=response_text)


def test_generate_joins_prompts_and_sets_config(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_text = "## System\nFollow the rules."
    system_prompt_path.write_text(system_text, encoding="utf-8")
    client = _DummyClient()
    llm = GeminiLLM(system_prompt=system_prompt_path, client=cast(genai.Client, client))

    result = llm.generate(["Line one", "Line two"])

    assert isinstance(result, _DummyResponse)
    assert result.text == "mock-response"
    assert len(client.models.calls) == 1
    call = client.models.calls[0]
    assert call["model"] == llm.MODEL
    assert call["contents"] == "Line one\nLine two"
    config = call["config"]
    assert isinstance(config, types.GenerateContentConfig)
    assert config.system_instruction == system_text
    assert config.thinking_config is not None
    assert config.thinking_config.thinking_budget == llm.MAX_THINKING_BUDGET


def test_system_prompt_property_returns_file_contents(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("Obey orders.", encoding="utf-8")
    client = _DummyClient()

    llm = GeminiLLM(system_prompt=system_prompt_path, client=cast(genai.Client, client))

    assert llm.system_prompt == "Obey orders."


def test_loads_dotenv_when_path_provided(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("GEMINI_API_KEY=from-dotenv\n", encoding="utf-8")
    previous_value = os.environ.pop("GEMINI_API_KEY", None)
    client = _DummyClient()

    try:
        GeminiLLM(
            system_prompt=system_prompt_path,
            client=cast(genai.Client, client),
            dotenv_path=dotenv_path,
        )
        assert os.environ["GEMINI_API_KEY"] == "from-dotenv"
    finally:
        if previous_value is None:
            os.environ.pop("GEMINI_API_KEY", None)
        else:
            os.environ["GEMINI_API_KEY"] = previous_value


def test_generate_returns_repaired_json_when_filter_enabled(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    response_text = "Noise before {\"key\": \"value\",} and after"
    client = _DummyClient(response_text=response_text)
    llm = GeminiLLM(
        system_prompt=system_prompt_path,
        client=cast(genai.Client, client),
        filter_json=True,
    )

    result = llm.generate(["Prompt"])

    assert result == {"key": "value"}


def test_generate_raises_when_json_delimiters_missing(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient(response_text="No JSON here")
    llm = GeminiLLM(
        system_prompt=system_prompt_path,
        client=cast(genai.Client, client),
        filter_json=True,
    )

    with pytest.raises(ValueError):
        llm.generate(["Prompt"])


def test_generate_raises_when_response_has_no_text(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient(response_text=None)
    llm = GeminiLLM(
        system_prompt=system_prompt_path,
        client=cast(genai.Client, client),
        filter_json=True,
    )

    with pytest.raises(AttributeError):
        llm.generate(["Prompt"])
