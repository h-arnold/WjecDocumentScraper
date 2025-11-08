from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import cast

from google import genai
from google.genai import types

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gemini_llm import GeminiLLM


class _DummyResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _DummyModels:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> _DummyResponse:
        self.calls.append(kwargs)
        return _DummyResponse(text="mock-response")


class _DummyClient:
    def __init__(self) -> None:
        self.models = _DummyModels()


def test_generate_joins_prompts_and_sets_config(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_text = "## System\nFollow the rules."
    system_prompt_path.write_text(system_text, encoding="utf-8")
    client = _DummyClient()
    llm = GeminiLLM(system_prompt_path=system_prompt_path, client=cast(genai.Client, client))

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

    llm = GeminiLLM(system_prompt_path=system_prompt_path, client=cast(genai.Client, client))

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
            system_prompt_path=system_prompt_path,
            client=cast(genai.Client, client),
            dotenv_path=dotenv_path,
        )
        assert os.environ["GEMINI_API_KEY"] == "from-dotenv"
    finally:
        if previous_value is None:
            os.environ.pop("GEMINI_API_KEY", None)
        else:
            os.environ["GEMINI_API_KEY"] = previous_value
