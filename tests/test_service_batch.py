from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Sequence

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.provider import (
    LLMProvider,
    LLMProviderError,
    ProviderStatus,
)
from src.llm.service import LLMService


class _DummyBatchJob:
    def __init__(self, name: str, done: bool = True) -> None:
        self.name = name
        self.done = done
        self.state = "SUCCEEDED" if done else "RUNNING"


class _BatchProvider(LLMProvider):
    name = "batch"

    def __init__(
        self,
        *,
        create_result: str | None = None,
        fetch_result: list[Any] | None = None,
        create_error: Exception | None = None,
        fetch_error: Exception | None = None,
    ) -> None:
        self._create_result = create_result or "batch-123"
        self._fetch_result = fetch_result or ["result1", "result2"]
        self._create_error = create_error
        self._fetch_error = fetch_error
        self._jobs: dict[str, _DummyBatchJob] = {}

    def generate(
        self,
        user_prompts: Sequence[str],
        *,
        filter_json: bool = False,
    ) -> Any:
        return "sync-result"

    def batch_generate(
        self,
        batch_payload: Sequence[Sequence[str]],
        *,
        filter_json: bool = False,
    ) -> Sequence[Any]:
        raise NotImplementedError()

    def create_batch_job(
        self,
        batch_payload: Sequence[Sequence[str]],
        *,
        filter_json: bool = False,
    ) -> str:
        if self._create_error:
            raise self._create_error
        # Store job for later retrieval
        self._jobs[self._create_result] = _DummyBatchJob(self._create_result, done=False)
        return self._create_result

    def get_batch_job(self, batch_job_name: str) -> _DummyBatchJob:
        return self._jobs.get(batch_job_name, _DummyBatchJob(batch_job_name, done=True))

    def fetch_batch_results(self, batch_job_name: str) -> Sequence[Any]:
        if self._fetch_error:
            raise self._fetch_error
        return self._fetch_result

    def health_check(self) -> bool:
        return True


class _UnsupportedProvider(LLMProvider):
    name = "unsupported"

    def generate(
        self,
        user_prompts: Sequence[str],
        *,
        filter_json: bool = False,
    ) -> Any:
        return "result"

    def batch_generate(
        self,
        batch_payload: Sequence[Sequence[str]],
        *,
        filter_json: bool = False,
    ) -> Sequence[Any]:
        raise NotImplementedError()

    def health_check(self) -> bool:
        return True


def test_create_batch_job_uses_first_supporting_provider() -> None:
    service = LLMService([
        _UnsupportedProvider(),
        _BatchProvider(create_result="batch-456"),
    ])

    provider_name, job_name = service.create_batch_job([["prompt"]])

    assert provider_name == "batch"
    assert job_name == "batch-456"


def test_create_batch_job_raises_when_no_provider_supports_it() -> None:
    service = LLMService([
        _UnsupportedProvider(),
        _UnsupportedProvider(),
    ])

    with pytest.raises(NotImplementedError, match="No provider supports"):
        service.create_batch_job([["prompt"]])


def test_create_batch_job_raises_on_provider_error() -> None:
    service = LLMService([
        _BatchProvider(create_error=LLMProviderError("failed")),
    ])

    with pytest.raises(LLMProviderError, match="failed"):
        service.create_batch_job([["prompt"]])


def test_fetch_batch_results_retrieves_from_correct_provider() -> None:
    service = LLMService([
        _BatchProvider(fetch_result=["a", "b", "c"]),
        _UnsupportedProvider(),
    ])

    provider_name, job_name = service.create_batch_job([["prompt"]])
    results = service.fetch_batch_results(provider_name, job_name)

    assert results == ["a", "b", "c"]


def test_fetch_batch_results_raises_when_provider_not_found() -> None:
    service = LLMService([
        _BatchProvider(),
    ])

    with pytest.raises(ValueError, match="not found"):
        service.fetch_batch_results("nonexistent", "batch-123")


def test_fetch_batch_results_raises_when_provider_unsupported() -> None:
    service = LLMService([
        _UnsupportedProvider(),
    ])

    with pytest.raises(NotImplementedError, match="does not support"):
        service.fetch_batch_results("unsupported", "batch-123")


def test_fetch_batch_results_raises_on_provider_error() -> None:
    service = LLMService([
        _BatchProvider(fetch_error=LLMProviderError("fetch failed")),
    ])

    provider_name, job_name = service.create_batch_job([["prompt"]])

    with pytest.raises(LLMProviderError, match="fetch failed"):
        service.fetch_batch_results(provider_name, job_name)


def test_get_batch_job_status_returns_status() -> None:
    service = LLMService([
        _BatchProvider(),
    ])

    provider_name, job_name = service.create_batch_job([["prompt"]])
    status = service.get_batch_job_status(provider_name, job_name)

    assert status.name == job_name
    assert status.done is False


def test_get_batch_job_status_raises_when_provider_not_found() -> None:
    service = LLMService([
        _BatchProvider(),
    ])

    with pytest.raises(ValueError, match="not found"):
        service.get_batch_job_status("nonexistent", "batch-123")


def test_reporting_hook_records_batch_operations() -> None:
    events: list[tuple[str, ProviderStatus, Exception | None]] = []

    def reporter(name: str, status: ProviderStatus, error: Exception | None = None) -> None:
        events.append((name, status, error))

    service = LLMService([
        _UnsupportedProvider(),
        _BatchProvider(),
    ], reporter=reporter)

    provider_name, job_name = service.create_batch_job([["prompt"]])
    service.fetch_batch_results(provider_name, job_name)

    # Should have: unsupported (create), success (create), success (fetch)
    assert len(events) == 3
    assert events[0][1] == ProviderStatus.UNSUPPORTED
    assert events[1][1] == ProviderStatus.SUCCESS
    assert events[2][1] == ProviderStatus.SUCCESS
