from __future__ import annotations

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
from src.llm.provider import LLMProviderError


class _DummyResponse:
    def __init__(self, text: Any) -> None:
        self.text = text


class _DummyBatchJob:
    def __init__(
        self,
        name: str,
        state: str = "JOB_STATE_SUCCEEDED",
        done: bool = True,
        error: Any | None = None,
        inlined_responses: list[Any] | None = None,
        inlined_requests: list[Any] | None = None,
    ) -> None:
        self.name = name
        self.state = state
        self.done = done
        self.error = error
        
        # Create destination with inlined responses
        self.dest = None
        if inlined_responses is not None:
            self.dest = type('Dest', (), {'inlined_responses': inlined_responses})()
        
        # Create source with inlined requests (for metadata)
        self.src = None
        if inlined_requests is not None:
            self.src = type('Src', (), {'inlined_requests': inlined_requests})()


class _DummyInlinedResponse:
    def __init__(self, response: Any | None = None, error: Any | None = None) -> None:
        self.response = response
        self.error = error


class _DummyBatches:
    def __init__(self) -> None:
        self.created_jobs: list[dict[str, Any]] = []
        self.jobs: dict[str, _DummyBatchJob] = {}

    def create(self, **kwargs: Any) -> _DummyBatchJob:
        self.created_jobs.append(kwargs)
        job_name = f"batch-job-{len(self.created_jobs)}"
        
        # Store the inlined requests for metadata access
        inlined_requests = kwargs.get('src', [])
        
        # Create successful responses for each request
        inlined_responses = []
        for req in inlined_requests:
            response = _DummyResponse(text="mock-batch-response")
            inlined_responses.append(_DummyInlinedResponse(response=response))
        
        job = _DummyBatchJob(
            name=job_name,
            inlined_responses=inlined_responses,
            inlined_requests=inlined_requests,
        )
        self.jobs[job_name] = job
        return job

    def get(self, *, name: str, **kwargs: Any) -> _DummyBatchJob:
        if name not in self.jobs:
            raise ValueError(f"Batch job {name} not found")
        return self.jobs[name]


class _DummyClient:
    def __init__(self) -> None:
        self.batches = _DummyBatches()


def test_create_batch_job_builds_inlined_requests(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_text = "System instructions"
    system_prompt_path.write_text(system_text, encoding="utf-8")
    client = _DummyClient()
    llm = GeminiLLM(system_prompt=system_prompt_path, client=cast(genai.Client, client))

    batch_payload = [
        ["First prompt", "Additional context"],
        ["Second prompt"],
    ]
    
    job_name = llm.create_batch_job(batch_payload)

    assert job_name == "batch-job-1"
    assert len(client.batches.created_jobs) == 1
    
    job_data = client.batches.created_jobs[0]
    assert job_data["model"] == llm.MODEL
    assert len(job_data["src"]) == 2
    
    # Check first request
    req1 = job_data["src"][0]
    assert isinstance(req1, types.InlinedRequest)
    assert req1.contents == "First prompt\nAdditional context"
    assert req1.config.system_instruction == system_text
    assert req1.config.temperature == 0.2
    assert req1.config.thinking_config.thinking_budget == llm.MAX_THINKING_BUDGET
    assert req1.metadata["filter_json"] == "false"
    
    # Check second request
    req2 = job_data["src"][1]
    assert isinstance(req2, types.InlinedRequest)
    assert req2.contents == "Second prompt"


def test_create_batch_job_stores_filter_json_in_metadata(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient()
    llm = GeminiLLM(system_prompt=system_prompt_path, client=cast(genai.Client, client))

    llm.create_batch_job([["Prompt"]], filter_json=True)

    job_data = client.batches.created_jobs[0]
    req = job_data["src"][0]
    assert req.metadata["filter_json"] == "true"


def test_create_batch_job_raises_on_empty_payload(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient()
    llm = GeminiLLM(system_prompt=system_prompt_path, client=cast(genai.Client, client))

    with pytest.raises(ValueError, match="batch_payload must not be empty"):
        llm.create_batch_job([])


def test_create_batch_job_raises_on_empty_prompts(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient()
    llm = GeminiLLM(system_prompt=system_prompt_path, client=cast(genai.Client, client))

    with pytest.raises(ValueError, match="prompt sequence.*must not be empty"):
        llm.create_batch_job([["First"], []])


def test_get_batch_job_returns_job_info(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient()
    llm = GeminiLLM(system_prompt=system_prompt_path, client=cast(genai.Client, client))

    job_name = llm.create_batch_job([["Prompt"]])
    job = llm.get_batch_job(job_name)

    assert job.name == job_name
    assert job.state == "JOB_STATE_SUCCEEDED"
    assert job.done is True


def test_fetch_batch_results_returns_responses(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient()
    llm = GeminiLLM(system_prompt=system_prompt_path, client=cast(genai.Client, client))

    job_name = llm.create_batch_job([["First"], ["Second"]])
    results = llm.fetch_batch_results(job_name)

    assert len(results) == 2
    assert all(isinstance(r, _DummyResponse) for r in results)
    assert all(r.text == "mock-batch-response" for r in results)


def test_fetch_batch_results_applies_json_filter_when_requested(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient()
    
    # Override the batch responses to return JSON text
    class _JsonBatchClient(_DummyClient):
        def __init__(self) -> None:
            super().__init__()
            self.batches = _JsonBatches()
    
    class _JsonBatches(_DummyBatches):
        def create(self, **kwargs: Any) -> _DummyBatchJob:
            job = super().create(**kwargs)
            # Update responses to have JSON content
            for inlined_resp in job.dest.inlined_responses:
                inlined_resp.response = _DummyResponse(text='{"key": "value",}')
            return job
    
    json_client = _JsonBatchClient()
    llm = GeminiLLM(system_prompt=system_prompt_path, client=cast(genai.Client, json_client))

    job_name = llm.create_batch_job([["Prompt"]], filter_json=True)
    results = llm.fetch_batch_results(job_name)

    assert len(results) == 1
    assert results[0] == {"key": "value"}


def test_fetch_batch_results_raises_when_not_completed(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient()
    llm = GeminiLLM(system_prompt=system_prompt_path, client=cast(genai.Client, client))

    job_name = llm.create_batch_job([["Prompt"]])
    # Modify job to be pending
    client.batches.jobs[job_name].done = False
    client.batches.jobs[job_name].state = "JOB_STATE_RUNNING"

    with pytest.raises(ValueError, match="not completed yet"):
        llm.fetch_batch_results(job_name)


def test_fetch_batch_results_raises_when_job_failed(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient()
    llm = GeminiLLM(system_prompt=system_prompt_path, client=cast(genai.Client, client))

    job_name = llm.create_batch_job([["Prompt"]])
    # Modify job to have error
    error = type('Error', (), {'message': 'Job failed'})()
    client.batches.jobs[job_name].error = error

    with pytest.raises(LLMProviderError, match="failed"):
        llm.fetch_batch_results(job_name)


def test_fetch_batch_results_raises_when_request_failed(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient()
    llm = GeminiLLM(system_prompt=system_prompt_path, client=cast(genai.Client, client))

    job_name = llm.create_batch_job([["First"], ["Second"]])
    # Modify second response to have error
    error = type('Error', (), {'message': 'Request failed'})()
    client.batches.jobs[job_name].dest.inlined_responses[1].error = error
    client.batches.jobs[job_name].dest.inlined_responses[1].response = None

    with pytest.raises(LLMProviderError, match="Request 1.*failed"):
        llm.fetch_batch_results(job_name)


def test_fetch_batch_results_raises_when_no_results(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient()
    llm = GeminiLLM(system_prompt=system_prompt_path, client=cast(genai.Client, client))

    job_name = llm.create_batch_job([["Prompt"]])
    # Remove results
    client.batches.jobs[job_name].dest = None

    with pytest.raises(ValueError, match="has no results"):
        llm.fetch_batch_results(job_name)


def test_batch_generate_raises_not_implemented(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System", encoding="utf-8")
    client = _DummyClient()
    llm = GeminiLLM(system_prompt=system_prompt_path, client=cast(genai.Client, client))

    with pytest.raises(NotImplementedError, match="asynchronous"):
        llm.batch_generate([["Prompt"]])
