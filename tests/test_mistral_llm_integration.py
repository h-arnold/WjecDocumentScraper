from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import pytest
from mistralai import Mistral

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.mistral_llm import MistralLLM
from src.llm.provider import LLMQuotaError, ProviderStatus
from src.llm.service import LLMService


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
    def __init__(
        self,
        response_content: Any = "mock-response",
        raise_error: Exception | None = None,
    ) -> None:
        self.calls: list[dict[str, object]] = []
        self._response_content = response_content
        self._raise_error = raise_error

    def start(self, **kwargs: object) -> _DummyResponse:
        self.calls.append(kwargs)
        if self._raise_error:
            raise self._raise_error
        return _DummyResponse(content=self._response_content)


class _DummyClient:
    def __init__(
        self,
        response_content: Any = "mock-response",
        raise_error: Exception | None = None,
    ) -> None:
        class _Beta:
            def __init__(
                self,
                response_content: Any = "mock-response",
                raise_error: Exception | None = None,
            ) -> None:
                self.conversations = _DummyChat(
                    response_content=response_content, raise_error=raise_error
                )

        self.beta = _Beta(response_content=response_content, raise_error=raise_error)


class _QuotaExceededError(Exception):
    """Mock quota exceeded error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.status_code = 429


def test_mistral_with_llm_service_fallback(tmp_path: Path) -> None:
    """Test that LLMService can fall back from a failing Mistral provider to another."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")

    # First provider fails with quota error
    failing_client = _DummyClient(raise_error=_QuotaExceededError("Rate limit"))
    mistral_failing = MistralLLM(
        system_prompt=system_prompt_path,
        client=cast(Mistral, failing_client),
    )

    # Second provider succeeds
    success_client = _DummyClient(response_content="Success response")
    mistral_success = MistralLLM(
        system_prompt=system_prompt_path,
        client=cast(Mistral, success_client),
    )

    service = LLMService([mistral_failing, mistral_success])

    result = service.generate(["Test prompt"])

    # Should get the successful response
    assert isinstance(result, _DummyResponse)
    assert result.choices[0].message.content == "Success response"


def test_mistral_with_llm_service_reporting(tmp_path: Path) -> None:
    """Test that LLMService correctly reports Mistral provider status."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")

    events: list[tuple[str, ProviderStatus, Exception | None]] = []

    def reporter(
        name: str, status: ProviderStatus, error: Exception | None = None
    ) -> None:
        events.append((name, status, error))

    # First provider fails with quota error
    failing_client = _DummyClient(raise_error=_QuotaExceededError("Rate limit"))
    mistral_failing = MistralLLM(
        system_prompt=system_prompt_path,
        client=cast(Mistral, failing_client),
    )

    # Second provider succeeds
    success_client = _DummyClient(response_content="Success response")
    mistral_success = MistralLLM(
        system_prompt=system_prompt_path,
        client=cast(Mistral, success_client),
    )

    service = LLMService([mistral_failing, mistral_success], reporter=reporter)

    service.generate(["Test prompt"])

    # Should have two events: QUOTA for first, SUCCESS for second
    assert len(events) == 2
    assert events[0][0] == "mistral"
    assert events[0][1] == ProviderStatus.QUOTA
    assert isinstance(events[0][2], LLMQuotaError)
    assert events[1][0] == "mistral"
    assert events[1][1] == ProviderStatus.SUCCESS


def test_mistral_batch_generate_reports_unsupported(tmp_path: Path) -> None:
    """Test that batch_generate correctly reports as unsupported for Mistral."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")

    events: list[tuple[str, ProviderStatus, Exception | None]] = []

    def reporter(
        name: str, status: ProviderStatus, error: Exception | None = None
    ) -> None:
        events.append((name, status, error))

    client = _DummyClient(response_content="Should not be used")
    mistral = MistralLLM(
        system_prompt=system_prompt_path,
        client=cast(Mistral, client),
    )

    service = LLMService([mistral], reporter=reporter)

    with pytest.raises(NotImplementedError) as exc_info:
        service.batch_generate([["prompt1"], ["prompt2"]])

    assert "No provider supports batch_generate" in str(exc_info.value)

    # Should have one event: UNSUPPORTED for Mistral
    assert len(events) == 1
    assert events[0][0] == "mistral"
    assert events[0][1] == ProviderStatus.UNSUPPORTED


def test_mistral_provider_order_in_service(tmp_path: Path) -> None:
    """Test that provider_order correctly reports Mistral."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")

    client = _DummyClient()
    mistral = MistralLLM(
        system_prompt=system_prompt_path,
        client=cast(Mistral, client),
    )

    service = LLMService([mistral])

    order = service.provider_order()

    assert order == ["mistral"]


def test_mistral_health_check_in_service(tmp_path: Path) -> None:
    """Test that health_check works through LLMService."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")

    client = _DummyClient()
    mistral = MistralLLM(
        system_prompt=system_prompt_path,
        client=cast(Mistral, client),
    )

    service = LLMService([mistral])

    health = service.health_check()

    assert health == [("mistral", True)]


def test_mistral_with_json_filtering_in_service(tmp_path: Path) -> None:
    """Test that JSON filtering works through LLMService."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")

    response_text = 'Here\'s the result: {"status": "ok", "value": 42} Done!'
    client = _DummyClient(response_content=response_text)
    mistral = MistralLLM(
        system_prompt=system_prompt_path,
        client=cast(Mistral, client),
    )

    service = LLMService([mistral])

    result = service.generate(["Test prompt"], filter_json=True)

    assert result == {"status": "ok", "value": 42}
