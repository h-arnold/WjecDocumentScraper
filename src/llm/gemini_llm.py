from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Sequence

from dotenv import load_dotenv
from google import genai
from google.genai import types
try:
    from google.api_core import exceptions as google_exceptions
except Exception:  # pragma: no cover - only occurs in test environment without google libs
    google_exceptions = None
from src.llm.provider import LLMQuotaError

from .json_utils import parse_json_response


class GeminiLLM:
    """Wrapper around the Gemini SDK with system instructions.
    
    The system prompt can be provided either as a string directly or as a Path to a file.
    """

    name = "gemini"
    MODEL = "gemini-2.5-flash"
    MAX_THINKING_BUDGET = 24576

    def __init__(
        self,
        system_prompt: str | Path,
        *,
        client: genai.Client | None = None,
        dotenv_path: str | Path | None = None,
        filter_json: bool = False,
        min_request_interval: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        # Accept either a direct string or a path to a file containing the prompt
        if isinstance(system_prompt, (str, Path)):
            # Try to interpret as path first if it looks like a path
            if isinstance(system_prompt, Path) or (isinstance(system_prompt, str) and ("\n" not in system_prompt and len(system_prompt) < 500)):
                try:
                    prompt_path = Path(system_prompt)
                    if prompt_path.exists() and prompt_path.is_file():
                        self._system_prompt = prompt_path.read_text(encoding="utf-8")
                    else:
                        # Treat as direct string prompt
                        self._system_prompt = str(system_prompt)
                except (OSError, ValueError):
                    # If path operations fail, treat as direct string
                    self._system_prompt = str(system_prompt)
            else:
                # Multi-line or long string - treat as direct prompt
                self._system_prompt = system_prompt
        else:
            raise TypeError(f"system_prompt must be str or Path, got {type(system_prompt)}")
            
        if dotenv_path is not None:
            load_dotenv(dotenv_path=Path(dotenv_path))
        else:
            load_dotenv()
        self._client = client or genai.Client()
        self._filter_json = filter_json
        
        # Read rate limiting configuration from environment or parameters
        if min_request_interval is None:
            try:
                min_request_interval = float(os.environ.get("GEMINI_MIN_REQUEST_INTERVAL", "0"))
            except ValueError:
                min_request_interval = 0.0
        self._min_request_interval = max(0.0, min_request_interval)
        
        # Read retry configuration from environment or parameters
        if max_retries is None:
            try:
                max_retries = int(os.environ.get("GEMINI_MAX_RETRIES", "0"))
            except ValueError:
                max_retries = 0
        self._max_retries = max(0, max_retries)
        
        # Track last request time for rate limiting
        # Initialize to 0 so first request is not rate limited
        self._last_request_time = 0.0

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    def generate(
        self,
        user_prompts: Sequence[str],
        *,
        filter_json: bool | None = None,
    ) -> Any:
        if not user_prompts:
            raise ValueError("user_prompts must not be empty.")

        apply_filter = self._filter_json if filter_json is None else filter_json

        contents = "\n".join(user_prompts)
        config = types.GenerateContentConfig(
            system_instruction=self._system_prompt,
            thinking_config=types.ThinkingConfig(thinking_budget=self.MAX_THINKING_BUDGET),
            temperature=0.2,
        )
        
        # Implement retry logic with exponential backoff for rate limit errors
        last_exception: Exception | None = None
        for attempt in range(self._max_retries + 1):
            # Enforce rate limiting before making the request
            self._enforce_rate_limit()
            
            try:
                response = self._client.models.generate_content(
                    model=self.MODEL,
                    contents=contents,
                    config=config,
                )
                
                # Success - reset last request time and return response
                self._last_request_time = time.time()
                
                if not apply_filter:
                    return response
                return self._parse_response_json(response)
                
            except Exception as exc:
                # Update last request time even on failure
                self._last_request_time = time.time()
                
                # Check if this is a retryable rate limit error (TooManyRequests/429)
                is_rate_limit = (
                    google_exceptions is not None
                    and isinstance(exc, getattr(google_exceptions, "TooManyRequests", object))
                )
                
                # Check if this is a permanent quota exhaustion (ResourceExhausted)
                is_quota_exhausted = (
                    google_exceptions is not None
                    and isinstance(exc, getattr(google_exceptions, "ResourceExhausted", object))
                )
                
                # Convert known quota/rate-limit exceptions to LLMQuotaError
                if is_quota_exhausted or is_rate_limit:
                    last_exception = exc
                    
                    # ResourceExhausted is permanent, don't retry
                    if is_quota_exhausted:
                        raise LLMQuotaError("Gemini provider: quota exhausted") from exc
                    
                    # TooManyRequests (429) is retryable
                    if is_rate_limit and attempt < self._max_retries:
                        # Calculate exponential backoff delay (as multiple of min_request_interval)
                        # Backoff: min_interval * 2^attempt
                        backoff_multiplier = 2 ** attempt
                        backoff_delay = self._min_request_interval * backoff_multiplier
                        
                        # Add small base delay even if min_interval is 0
                        if self._min_request_interval == 0:
                            backoff_delay = 0.1 * backoff_multiplier
                        
                        time.sleep(backoff_delay)
                        continue
                    
                    # Exhausted retries
                    raise LLMQuotaError("Gemini provider: rate limited (exhausted retries)") from exc
                
                # Non-quota exception, re-raise immediately
                raise
        

    def batch_generate(
        self,
        batch_payload: Sequence[Sequence[str]],
        *,
        filter_json: bool = False,
    ) -> Sequence[Any]:
        raise NotImplementedError("Gemini batch generation is not implemented yet.")

    def health_check(self) -> bool:
        return True

    def _parse_response_json(self, response: Any) -> Any:
        """Extract and repair JSON content from a Gemini response."""
        text = getattr(response, "text", None)
        if not isinstance(text, str):
            raise AttributeError("Response object does not expose a text attribute for JSON parsing.")
        
        return parse_json_response(text)
    
    def _enforce_rate_limit(self) -> None:
        """Enforce minimum interval between API requests."""
        if self._min_request_interval <= 0:
            return
        
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            sleep_time = self._min_request_interval - elapsed
            time.sleep(sleep_time)
