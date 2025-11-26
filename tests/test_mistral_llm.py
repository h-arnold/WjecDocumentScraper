from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from mistralai import Mistral

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.mistral_llm import MistralLLM
from src.llm.provider import LLMParseError, LLMProviderError, LLMQuotaError


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
        # Newer Mistral SDK includes a `beta.conversations.start` API.
        # Provide a `beta.conversations.start` compatible test client instead
        # of `chat.complete` to match production usage.
        class _Conversations:
            def __init__(self, response_content: Any = "mock-response") -> None:
                self.calls: list[dict[str, object]] = []
                self._response_content = response_content

            def start(self, **kwargs: object) -> _DummyResponse:
                self.calls.append(kwargs)
                return _DummyResponse(content=self._response_content)

        class _Beta:
            def __init__(self, response_content: Any = "mock-response") -> None:
                self.conversations = _Conversations(response_content=response_content)

        self.beta = _Beta(response_content=response_content)


class _QuotaExceededError(Exception):
    """Mock quota exceeded error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.status_code = 429


class _StaticResponse:
    def __init__(self, text: str) -> None:
        self.text = text
        self.closed = False

    def read(self) -> bytes:
        return self.text.encode("utf-8")

    def close(self) -> None:
        self.closed = True


class _DummyFiles:
    def __init__(
        self, output_lines: list[dict[str, Any]], error_text: str | None = None
    ) -> None:
        self.upload_payloads: list[str] = []
        self.output_text = "\n".join(json.dumps(line) for line in output_lines)
        self.error_text = error_text or ""

    def upload(self, *, file: Any, purpose: str) -> SimpleNamespace:
        assert purpose == "batch"
        payload_bytes = file.content.read()
        file.content.seek(0)
        self.upload_payloads.append(payload_bytes.decode("utf-8"))
        return SimpleNamespace(id="file-upload")

    def download(self, *, file_id: str) -> _StaticResponse:
        if file_id == "output-file":
            return _StaticResponse(self.output_text)
        if file_id == "error-file":
            return _StaticResponse(self.error_text)
        raise AssertionError(f"Unexpected file_id: {file_id}")


class _DummyBatchJobs:
    def __init__(
        self,
        status_sequence: list[str],
        *,
        output_file: str = "output-file",
        error_file: str | None = None,
        errors: list[Any] | None = None,
    ) -> None:
        self.status_sequence = status_sequence
        self.create_kwargs: dict[str, Any] | None = None
        self.calls = 0
        self.job = SimpleNamespace(
            id="job-1",
            status=status_sequence[0],
            output_file=output_file,
            error_file=error_file,
            errors=errors or [],
        )

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.create_kwargs = kwargs
        return self.job

    def get(self, *, job_id: str) -> SimpleNamespace:
        assert job_id == self.job.id
        self.calls += 1
        index = min(self.calls, len(self.status_sequence) - 1)
        self.job.status = self.status_sequence[index]
        return self.job


class _DummyBatch:
    def __init__(self, jobs: _DummyBatchJobs) -> None:
        self.jobs = jobs


class _BatchEnabledClient:
    def __init__(self, files: _DummyFiles, jobs: _DummyBatchJobs) -> None:
        self.files = files
        self.batch = _DummyBatch(jobs)


def test_generate_joins_prompts_and_sets_config(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_text = "## System\nFollow the rules."
    system_prompt_path.write_text(system_text, encoding="utf-8")
    client = _DummyClient()
    llm = MistralLLM(system_prompt=system_prompt_path, client=cast(Mistral, client))

    result = llm.generate(["Line one", "Line two"])

    assert isinstance(result, _DummyResponse)
    assert result.choices[0].message.content == "mock-response"
    # Check the new beta.conversations.start call was made
    assert len(client.beta.conversations.calls) == 1
    call = client.beta.conversations.calls[0]
    assert call["model"] == llm.MODEL

    # Check messages structure
    inputs = call["inputs"]
    assert isinstance(inputs, list)
    # we match the SDK example: system instructions are sent via the
    # `instructions` parameter and the inputs list contains user messages.
    assert call["instructions"] == system_text
    first_input = inputs[0]
    if isinstance(first_input, dict):
        assert first_input["role"] == "user"
        assert first_input["content"] == "Line one\nLine two"
    else:
        assert getattr(first_input, "role") == "user"
        assert getattr(first_input, "content") == "Line one\nLine two"

    # Check completion args contain the low temperature
    completion_args = call.get("completion_args", {})
    assert completion_args.get("temperature") == 0.2


def test_mistral_api_key_is_passed_to_sdk_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure that MistralLLM reads MISTRAL_API_KEY and passes it to the Mistral SDK."""
    # Arrange: set the env var that MistralLLM should pick up
    monkeypatch.setenv("MISTRAL_API_KEY", "env-test-key-123")

    # Capture arguments passed to the SDK constructor
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, api_key: str | None = None, **kwargs: object) -> None:
            captured["api_key"] = api_key

    # Replace the Mistral constructor in the module under test
    monkeypatch.setattr("src.llm.mistral_llm.Mistral", FakeClient)

    # Act: instantiate MistralLLM (without providing a client)
    MistralLLM(system_prompt="test")
    MistralLLM(system_prompt="test")
    # Assert: the FakeClient received the API key from the environment
    assert captured.get("api_key") == "env-test-key-123"


def test_mistral_raises_when_api_key_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify MistralLLM raises a helpful error when MISTRAL_API_KEY is not set."""
    # Arrange: ensure env var is unset
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    # Prevent the module from re-loading the real .env file (which would set the key again)
    monkeypatch.setattr("src.llm.mistral_llm.load_dotenv", lambda *args, **kwargs: None)

    # Replace Mistral constructor to ensure if code tries to call it without API key,
    # we can detect it. However, the code should raise before calling the constructor.
    called = {"constructed": False}

    class FakeClientNoop:
        def __init__(self, api_key: str | None = None, **kwargs: object) -> None:
            called["constructed"] = True

    monkeypatch.setattr("src.llm.mistral_llm.Mistral", FakeClientNoop)

    # Act & Assert: Instantiation should raise a ValueError due to missing API key
    with pytest.raises(
        ValueError, match="MISTRAL_API_KEY environment variable is required"
    ):
        MistralLLM(system_prompt="test")
    # The constructor should not have been called
    assert called["constructed"] is False


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
    response_text = 'Noise before {"key": "value",} and after'
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

    with pytest.raises(LLMParseError) as exc_info:
        llm.generate(["Prompt"])
    
    # Verify the error contains the response and prompts for debugging
    assert exc_info.value.response_text == "No JSON here"
    assert exc_info.value.prompts == ["Prompt"]


def test_generate_raises_when_response_has_no_content(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient(response_content=None)
    llm = MistralLLM(
        system_prompt=system_prompt_path,
        client=cast(Mistral, client),
        filter_json=True,
    )

    with pytest.raises(LLMParseError) as exc_info:
        llm.generate(["Prompt"])
    
    # Verify the error contains the prompts for debugging
    assert exc_info.value.prompts == ["Prompt"]


def test_generate_parses_outputs_shape_with_code_fence(tmp_path: Path) -> None:
    """When the Mistral beta API returns an `outputs` list containing a
    fenced codeblock with JSON, we should extract and repair it correctly.
    """
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")

    # Create a response object whose `outputs` property contains an item
    # with a `content` string including a fenced JSON codeblock.
    class _OutItem:
        def __init__(self, content: Any) -> None:
            self.content = content

    class _OutResponse:
        def __init__(self, outputs: list) -> None:
            self.outputs = outputs

    class _OutputsClient:
        def __init__(self, response: _OutResponse) -> None:
            class _Conversations:
                def __init__(self, response: _OutResponse) -> None:
                    self._response = response

                def start(self, **kwargs: object) -> _OutResponse:
                    return self._response

            class _Beta:
                def __init__(self, response: _OutResponse) -> None:
                    self.conversations = _Conversations(response)

            self.beta = _Beta(response)

    # Fenced JSON content (with trailing comma and code fences)
    fenced_json = (
        '```json\n[ {\n  "issue_id": 10,\n  "reasoning": "Missing hyphen"\n} ]\n```'
    )
    outputs_response = _OutResponse(outputs=[_OutItem(fenced_json)])
    client = _OutputsClient(response=outputs_response)

    llm = MistralLLM(
        system_prompt=system_prompt_path,
        client=cast(Mistral, client),
        filter_json=True,
    )

    result = llm.generate(["Prompt"])

    assert isinstance(result, list)
    assert result[0]["issue_id"] == 10


def test_generate_raises_quota_error_on_429(tmp_path: Path) -> None:
    """Test that HTTP 429 status codes are converted to LLMQuotaError."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")

    class _QuotaChat:
        def start(self, **kwargs: object) -> None:
            raise _QuotaExceededError("Rate limit exceeded")

    class _QuotaClient:
        def __init__(self) -> None:
            class _Beta:
                def __init__(self) -> None:
                    self.conversations = _QuotaChat()

            self.beta = _Beta()

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


def _build_output_line(index: int, content: str) -> dict[str, Any]:
    return {
        "custom_id": f"req-{index:05d}",
        "response": {
            "status_code": 200,
            "body": {
                "conversation_id": f"conv-{index}",
                "outputs": [{"content": content}],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
        },
    }


def test_batch_generate_returns_conversation_objects(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")

    files = _DummyFiles(
        [
            _build_output_line(0, '{"value": 1}'),
            _build_output_line(1, '{"value": 2}'),
        ]
    )
    jobs = _DummyBatchJobs(["RUNNING", "SUCCESS"])
    client = _BatchEnabledClient(files, jobs)

    llm = MistralLLM(system_prompt=system_prompt_path, client=cast(Mistral, client))

    results = llm.batch_generate([["Prompt A"], ["Prompt B"]])

    assert len(results) == 2
    assert all(hasattr(item, "conversation_id") for item in results)

    assert jobs.create_kwargs is not None
    assert jobs.create_kwargs["endpoint"] == "/v1/conversations"

    assert files.upload_payloads
    first_line = files.upload_payloads[0].splitlines()[0]
    payload = json.loads(first_line)
    assert payload["body"]["instructions"] == "System prompt"
    assert payload["body"]["completion_args"]["temperature"] == 0.2


def test_batch_generate_with_filter_returns_json(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")

    files = _DummyFiles(
        [
            _build_output_line(0, '{"foo": 1}'),
        ]
    )
    jobs = _DummyBatchJobs(["SUCCESS"])
    client = _BatchEnabledClient(files, jobs)

    llm = MistralLLM(system_prompt=system_prompt_path, client=cast(Mistral, client))

    results = llm.batch_generate([["Prompt"]], filter_json=True)

    assert results == [{"foo": 1}]


def test_batch_generate_raises_on_job_failure(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")

    files = _DummyFiles(
        [
            _build_output_line(0, '{"foo": 1}'),
        ],
        error_text="job failure",
    )
    jobs = _DummyBatchJobs(
        ["RUNNING", "FAILED"], error_file="error-file", errors=[{"message": "failed"}]
    )
    client = _BatchEnabledClient(files, jobs)

    llm = MistralLLM(system_prompt=system_prompt_path, client=cast(Mistral, client))

    with pytest.raises(LLMProviderError):
        llm.batch_generate([["Prompt"]])


def test_batch_generate_raises_quota_from_upload(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")

    class _QuotaFiles(_DummyFiles):
        def __init__(self) -> None:
            super().__init__([])

        def upload(self, *, file: Any, purpose: str) -> SimpleNamespace:  # type: ignore[override]
            raise _QuotaExceededError("Quota hit")

    files = _QuotaFiles()
    jobs = _DummyBatchJobs(["SUCCESS"])
    client = _BatchEnabledClient(files, jobs)

    llm = MistralLLM(system_prompt=system_prompt_path, client=cast(Mistral, client))

    with pytest.raises(LLMQuotaError):
        llm.batch_generate([["Prompt"]])


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
    response_text = 'Some text {"key": "value"} more text'
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
