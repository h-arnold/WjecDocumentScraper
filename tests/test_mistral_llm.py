from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from mistralai import Mistral

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.mistral_llm import MistralLLM
from src.llm.provider import LLMQuotaError


class _DummyMessage:
    def __init__(self, content: Any) -> None:
        self.content = content


class _DummyChoice:
    def __init__(self, message: _DummyMessage) -> None:
        self.message = message
        self.finish_reason = "stop"


class _DummyResponse:
    def __init__(self, content: Any) -> None:
        self.choices = [_DummyChoice(_DummyMessage(content))]


class _DummyChat:
    def __init__(self, response_content: Any = "mock-response") -> None:
        self.calls: list[dict[str, object]] = []
        self._response_content = response_content

    def complete(self, **kwargs: object) -> _DummyResponse:
        self.calls.append(kwargs)
        return _DummyResponse(content=self._response_content)


class _DummyClient:
    def __init__(self, response_content: Any = "mock-response") -> None:
        self.chat = _DummyChat(response_content=response_content)


class _QuotaExceededError(Exception):
    """Mock quota exceeded error."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.status_code = 429


def test_generate_joins_prompts_and_sets_config(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_text = "## System\nFollow the rules."
    system_prompt_path.write_text(system_text, encoding="utf-8")
    client = _DummyClient()
    llm = MistralLLM(system_prompt=system_prompt_path, client=cast(Mistral, client))

    result = llm.generate(["Line one", "Line two"])

    assert isinstance(result, _DummyResponse)
    assert result.choices[0].message.content == "mock-response"
    assert len(client.chat.calls) == 1
    call = client.chat.calls[0]
    assert call["model"] == llm.MODEL
    
    # Check messages structure
    messages = call["messages"]
    assert len(messages) == 2
    assert messages[0].role == "system"
    assert messages[0].content == system_text
    assert messages[1].role == "user"
    assert messages[1].content == "Line one\nLine two"
    
    # Check thinking mode is enabled
    assert call["prompt_mode"] == "reasoning"
    assert call["temperature"] == 0.2


def test_system_prompt_property_returns_file_contents(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("Obey orders.", encoding="utf-8")
    client = _DummyClient()

    llm = MistralLLM(system_prompt=system_prompt_path, client=cast(Mistral, client))

    assert llm.system_prompt == "Obey orders."


def test_system_prompt_accepts_direct_string() -> None:
    system_text = "This is a direct system prompt.\nWith multiple lines."
    client = _DummyClient()

    llm = MistralLLM(system_prompt=system_text, client=cast(Mistral, client))

    assert llm.system_prompt == system_text


def test_loads_dotenv_when_path_provided(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("MISTRAL_API_KEY=from-dotenv\n", encoding="utf-8")
    previous_value = os.environ.pop("MISTRAL_API_KEY", None)
    client = _DummyClient()

    try:
        MistralLLM(
            system_prompt=system_prompt_path,
            client=cast(Mistral, client),
            dotenv_path=dotenv_path,
        )
        assert os.environ["MISTRAL_API_KEY"] == "from-dotenv"
    finally:
        if previous_value is None:
            os.environ.pop("MISTRAL_API_KEY", None)
        else:
            os.environ["MISTRAL_API_KEY"] = previous_value


def test_generate_returns_repaired_json_when_filter_enabled(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    response_text = "Noise before {\"key\": \"value\",} and after"
    client = _DummyClient(response_content=response_text)
    llm = MistralLLM(
        system_prompt=system_prompt_path,
        client=cast(Mistral, client),
        filter_json=True,
    )

    result = llm.generate(["Prompt"])

    assert result == {"key": "value"}


def test_generate_raises_when_json_delimiters_missing(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient(response_content="No JSON here")
    llm = MistralLLM(
        system_prompt=system_prompt_path,
        client=cast(Mistral, client),
        filter_json=True,
    )

    with pytest.raises(ValueError):
        llm.generate(["Prompt"])


def test_generate_raises_when_response_has_no_content(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient(response_content=None)
    llm = MistralLLM(
        system_prompt=system_prompt_path,
        client=cast(Mistral, client),
        filter_json=True,
    )

    with pytest.raises(AttributeError):
        llm.generate(["Prompt"])


def test_generate_raises_quota_error_on_429(tmp_path: Path) -> None:
    """Test that HTTP 429 status codes are converted to LLMQuotaError."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    
    class _QuotaChat:
        def complete(self, **kwargs: object) -> None:
            raise _QuotaExceededError("Rate limit exceeded")
    
    class _QuotaClient:
        def __init__(self) -> None:
            self.chat = _QuotaChat()
    
    client = _QuotaClient()
    llm = MistralLLM(system_prompt=system_prompt_path, client=cast(Mistral, client))

    with pytest.raises(LLMQuotaError) as exc_info:
        llm.generate(["Prompt"])
    
    assert "quota exhausted or rate limited" in str(exc_info.value)


def test_generate_raises_empty_prompts(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient()
    llm = MistralLLM(system_prompt=system_prompt_path, client=cast(Mistral, client))

    with pytest.raises(ValueError) as exc_info:
        llm.generate([])
    
    assert "must not be empty" in str(exc_info.value)


def test_batch_generate_raises_not_implemented(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient()
    llm = MistralLLM(system_prompt=system_prompt_path, client=cast(Mistral, client))

    with pytest.raises(NotImplementedError):
        llm.batch_generate([["prompt1"], ["prompt2"]])


def test_health_check_returns_true(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient()
    llm = MistralLLM(system_prompt=system_prompt_path, client=cast(Mistral, client))

    assert llm.health_check() is True


def test_name_property(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient()
    llm = MistralLLM(system_prompt=system_prompt_path, client=cast(Mistral, client))

    assert llm.name == "mistral"


def test_filter_json_can_be_overridden_per_call(tmp_path: Path) -> None:
    """Test that filter_json parameter can be overridden on a per-call basis."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    response_text = "Some text {\"key\": \"value\"} more text"
    client = _DummyClient(response_content=response_text)
    # Create with filter_json=False
    llm = MistralLLM(
        system_prompt=system_prompt_path,
        client=cast(Mistral, client),
        filter_json=False,
    )

    # Override to True for this call
    result = llm.generate(["Prompt"], filter_json=True)

    assert result == {"key": "value"}
