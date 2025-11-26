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

from src.llm.gemini_llm import GeminiLLM
from src.llm.provider import LLMParseError


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
    # By default the grounding tool is not enabled
    assert not getattr(config, "tools", None)


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
    response_text = 'Noise before {"key": "value",} and after'
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

    with pytest.raises(LLMParseError) as exc_info:
        llm.generate(["Prompt"])
    
    # Verify the error contains the response and prompts for debugging
    assert exc_info.value.response_text == "No JSON here"
    assert exc_info.value.prompts == ["Prompt"]


def test_generate_raises_when_response_has_no_text(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient(response_text=None)
    llm = GeminiLLM(
        system_prompt=system_prompt_path,
        client=cast(genai.Client, client),
        filter_json=True,
    )

    with pytest.raises(LLMParseError) as exc_info:
        llm.generate(["Prompt"])
    
    # Verify the error contains the prompts for debugging
    assert exc_info.value.prompts == ["Prompt"]


def test_generate_excludes_grounding_tool_by_default(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_text = "## System\nFollow the rules."
    system_prompt_path.write_text(system_text, encoding="utf-8")
    client = _DummyClient()
    llm = GeminiLLM(system_prompt=system_prompt_path, client=cast(genai.Client, client))

    _ = llm.generate(["Line one"])
    call = client.models.calls[0]
    config = call["config"]
    assert isinstance(config, types.GenerateContentConfig)
    assert not getattr(config, "tools", None)


def test_generate_includes_grounding_tool_when_enabled(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_text = "## System\nFollow the rules."
    system_prompt_path.write_text(system_text, encoding="utf-8")
    client = _DummyClient()
    llm = GeminiLLM(
        system_prompt=system_prompt_path,
        client=cast(genai.Client, client),
        use_grounding_tool=True,
    )

    _ = llm.generate(["Line one"])
    call = client.models.calls[0]
    config = call["config"]
    # The config.tools should include a Tool with google_search
    tools = getattr(config, "tools", []) or []
    assert isinstance(tools, list)
    assert len(tools) >= 1
    # Ensure the Tool includes google_search property
    found_google_search = any(
        getattr(t, "google_search", None) is not None for t in tools
    )
    assert found_google_search
