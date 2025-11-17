"""Tests for GeminiLLM rate limiting and retry logic."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest
from google import genai

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.gemini_llm import GeminiLLM
from src.llm.provider import LLMQuotaError

# Create mock exceptions that can be used for isinstance checks
class _MockResourceExhausted(Exception):
    """Mock ResourceExhausted exception."""
    pass

class _MockTooManyRequests(Exception):
    """Mock TooManyRequests exception."""
    pass


class _DummyResponse:
    def __init__(self, text: Any) -> None:
        self.text = text


class _TimingModels:
    """Mock models that tracks call times and can simulate rate limit errors."""
    
    def __init__(
        self,
        response_text: Any = "mock-response",
        *,
        fail_count: int = 0,
        error_type: str = "rate_limit",
    ) -> None:
        self.calls: list[dict[str, object]] = []
        self.call_times: list[float] = []
        self._response_text = response_text
        self._fail_count = fail_count
        self._call_count = 0
        self._error_type = error_type
    
    def generate_content(self, **kwargs: object) -> _DummyResponse:
        self.call_times.append(time.time())
        self.calls.append(kwargs)
        self._call_count += 1
        # Simulate failures for first N calls
        if self._call_count <= self._fail_count:
            if self._error_type == "rate_limit":
                raise _MockTooManyRequests("429 Rate limit exceeded")
            elif self._error_type == "quota":
                raise _MockResourceExhausted("Quota exceeded")
        
        return _DummyResponse(text=self._response_text)


class _TimingClient:
    def __init__(
        self,
        response_text: Any = "mock-response",
        *,
        fail_count: int = 0,
        error_type: str = "rate_limit",
    ) -> None:
        self.models = _TimingModels(
            response_text=response_text,
            fail_count=fail_count,
            error_type=error_type,
        )


def test_gemini_respects_min_request_interval(tmp_path: Path) -> None:
    """Test that GeminiLLM enforces minimum request interval between calls."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")
    
    client = _TimingClient()
    llm = GeminiLLM(
        system_prompt=system_prompt_path,
        client=cast(genai.Client, client),
        min_request_interval=0.5,  # 500ms minimum
    )
    
    # Make multiple requests
    llm.generate(["First request"])
    llm.generate(["Second request"])
    llm.generate(["Third request"])
    
    # Check that at least min_request_interval elapsed between calls
    call_times = client.models.call_times
    assert len(call_times) == 3
    
    # Check intervals between consecutive calls
    for i in range(1, len(call_times)):
        interval = call_times[i] - call_times[i-1]
        # Allow some tolerance for execution overhead
        assert interval >= 0.45, f"Interval {interval} is less than minimum 0.5s"


def test_gemini_no_delay_when_interval_zero(tmp_path: Path) -> None:
    """Test that no delay is added when min_request_interval is 0."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")
    
    client = _TimingClient()
    llm = GeminiLLM(
        system_prompt=system_prompt_path,
        client=cast(genai.Client, client),
        min_request_interval=0.0,  # No delay
    )
    
    start = time.time()
    llm.generate(["First"])
    llm.generate(["Second"])
    elapsed = time.time() - start
    
    # Should complete very quickly without artificial delay
    assert elapsed < 0.1, f"Took {elapsed}s, expected < 0.1s"


def test_gemini_reads_min_interval_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that GeminiLLM reads GEMINI_MIN_REQUEST_INTERVAL from environment."""
    monkeypatch.setenv("GEMINI_MIN_REQUEST_INTERVAL", "0.3")
    
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")
    
    client = _TimingClient()
    llm = GeminiLLM(
        system_prompt=system_prompt_path,
        client=cast(genai.Client, client),
    )
    
    # Make two requests
    llm.generate(["First"])
    llm.generate(["Second"])
    
    call_times = client.models.call_times
    interval = call_times[1] - call_times[0]
    assert interval >= 0.25, f"Interval {interval} is less than env-configured 0.3s"


def test_gemini_retries_on_rate_limit_error(tmp_path: Path) -> None:
    """Test that GeminiLLM retries on 429 rate limit errors."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")
    
    # Configure client to fail twice, then succeed
    client = _TimingClient(
        response_text="success",
        fail_count=2,
        error_type="rate_limit",
    )
    
    # Mock google_exceptions to recognize our mock exception
    with patch("src.llm.gemini_llm.google_exceptions") as mock_exceptions:
        mock_exceptions.TooManyRequests = _MockTooManyRequests
        mock_exceptions.ResourceExhausted = _MockResourceExhausted
        
        llm = GeminiLLM(
            system_prompt=system_prompt_path,
            client=cast(genai.Client, client),
            max_retries=3,
            min_request_interval=0.1,
        )
        
        result = llm.generate(["Test"])
        
        # Should eventually succeed after retries
        assert result.text == "success"
        # Should have made 3 attempts (2 failures + 1 success)
        assert len(client.models.calls) == 3


def test_gemini_exponential_backoff_on_retries(tmp_path: Path) -> None:
    """Test that retry delays follow exponential backoff pattern."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")
    
    # Configure to fail 3 times
    client = _TimingClient(
        response_text="success",
        fail_count=3,
        error_type="rate_limit",
    )
    
    with patch("src.llm.gemini_llm.google_exceptions") as mock_exceptions:
        mock_exceptions.TooManyRequests = _MockTooManyRequests
        mock_exceptions.ResourceExhausted = _MockResourceExhausted
        
        min_interval = 0.1
        llm = GeminiLLM(
            system_prompt=system_prompt_path,
            client=cast(genai.Client, client),
            max_retries=4,
            min_request_interval=min_interval,
        )
        
        result = llm.generate(["Test"])
        
        assert result.text == "success"
        call_times = client.models.call_times
        assert len(call_times) == 4  # 3 failures + 1 success
        
        # Check that delays increase exponentially (as multiples of min_interval)
        # Expected pattern: initial request (attempt 1, no wait), then before retry 1 wait min_interval * 2^0, before retry 2 wait min_interval * 2^1, etc.
        intervals = [call_times[i] - call_times[i-1] for i in range(1, len(call_times))]
        
        # First retry should wait ~min_interval (2^0)
        assert intervals[0] >= min_interval * 0.9
        # Second retry should wait ~2*min_interval (2^1)
        assert intervals[1] >= min_interval * 2 * 0.9
        # Third retry should wait ~4*min_interval (2^2)
        assert intervals[2] >= min_interval * 4 * 0.9


def test_gemini_raises_quota_error_after_max_retries(tmp_path: Path) -> None:
    """Test that LLMQuotaError is raised after exhausting retries."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")
    
    # Configure to always fail
    client = _TimingClient(
        fail_count=10,  # More failures than retries
        error_type="rate_limit",
    )
    
    with patch("src.llm.gemini_llm.google_exceptions") as mock_exceptions:
        mock_exceptions.TooManyRequests = _MockTooManyRequests
        mock_exceptions.ResourceExhausted = _MockResourceExhausted
        
        llm = GeminiLLM(
            system_prompt=system_prompt_path,
            client=cast(genai.Client, client),
            max_retries=2,
            min_request_interval=0.05,  # Small interval for fast test
        )
        
        with pytest.raises(LLMQuotaError, match="rate limit|quota"):
            llm.generate(["Test"])
        
        # Should have made initial attempt + max_retries
        assert len(client.models.calls) == 3  # 1 initial + 2 retries


def test_gemini_raises_quota_error_immediately_on_resource_exhausted(tmp_path: Path) -> None:
    """Test that ResourceExhausted errors are not retried (permanent quota exhaustion)."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")
    
    client = _TimingClient(
        fail_count=1,
        error_type="quota",  # Permanent quota exhaustion
    )
    
    with patch("src.llm.gemini_llm.google_exceptions") as mock_exceptions:
        mock_exceptions.TooManyRequests = _MockTooManyRequests
        mock_exceptions.ResourceExhausted = _MockResourceExhausted
        
        llm = GeminiLLM(
            system_prompt=system_prompt_path,
            client=cast(genai.Client, client),
            max_retries=3,
            min_request_interval=0.05,
        )
        
        with pytest.raises(LLMQuotaError, match="quota|Rate limit"):
            llm.generate(["Test"])
        
        # Should only make one attempt (no retries for ResourceExhausted)
        assert len(client.models.calls) == 1


def test_gemini_default_no_retries(tmp_path: Path) -> None:
    """Test that by default (max_retries=0), no retries are performed."""
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")
    
    client = _TimingClient(
        fail_count=1,
        error_type="rate_limit",
    )
    
    with patch("src.llm.gemini_llm.google_exceptions") as mock_exceptions:
        mock_exceptions.TooManyRequests = _MockTooManyRequests
        mock_exceptions.ResourceExhausted = _MockResourceExhausted
        
        # Default behavior (no retries configured)
        llm = GeminiLLM(
            system_prompt=system_prompt_path,
            client=cast(genai.Client, client),
        )
        
        with pytest.raises(LLMQuotaError):
            llm.generate(["Test"])
        
        # Should only make one attempt
        assert len(client.models.calls) == 1


def test_gemini_reads_max_retries_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that GeminiLLM reads GEMINI_MAX_RETRIES from environment."""
    monkeypatch.setenv("GEMINI_MAX_RETRIES", "2")
    
    system_prompt_path = tmp_path / "system.md"
    system_prompt_path.write_text("System prompt", encoding="utf-8")
    
    client = _TimingClient(
        response_text="success",
        fail_count=1,
        error_type="rate_limit",
    )
    
    with patch("src.llm.gemini_llm.google_exceptions") as mock_exceptions:
        mock_exceptions.TooManyRequests = _MockTooManyRequests
        mock_exceptions.ResourceExhausted = _MockResourceExhausted
        
        llm = GeminiLLM(
            system_prompt=system_prompt_path,
            client=cast(genai.Client, client),
        )
        
        result = llm.generate(["Test"])
        assert result.text == "success"
        # Should have retried once (1 failure + 1 success)
        assert len(client.models.calls) == 2
