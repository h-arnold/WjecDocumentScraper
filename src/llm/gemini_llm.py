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
except (
    Exception
):  # pragma: no cover - only occurs in test environment without google libs
    google_exceptions = None
from src.llm.provider import LLMParseError, LLMQuotaError

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
        use_grounding_tool: bool | None = None,
    ) -> None:
        # Accept either a direct string or a path to a file containing the prompt
        if isinstance(system_prompt, (str, Path)):
            # Try to interpret as path first if it looks like a path
            if isinstance(system_prompt, Path) or (
                isinstance(system_prompt, str)
                and ("\n" not in system_prompt and len(system_prompt) < 500)
            ):
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
            raise TypeError(
                f"system_prompt must be str or Path, got {type(system_prompt)}"
            )

        if dotenv_path is not None:
            load_dotenv(dotenv_path=Path(dotenv_path))
        else:
            load_dotenv()
        self._client = client or genai.Client()
        self._filter_json = filter_json

        # Read rate limiting configuration from environment or parameters
        if min_request_interval is None:
            try:
                min_request_interval = float(
                    os.environ.get("GEMINI_MIN_REQUEST_INTERVAL", "0")
                )
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

        # Grounding/tooling configuration: allow opt-in via constructor or environment
        if use_grounding_tool is None:
            try:
                env_val = os.environ.get("GEMINI_ENABLE_GROUNDING_TOOL", "false")
                use_grounding_tool = str(env_val).strip().lower() in (
                    "1",
                    "true",
                    "yes",
                )
            except Exception:
                use_grounding_tool = False
        self._use_grounding_tool = bool(use_grounding_tool)

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
        # Build base config
        config_kwargs = dict(
            system_instruction=self._system_prompt,
            thinking_config=types.ThinkingConfig(
                thinking_budget=self.MAX_THINKING_BUDGET
            ),
            temperature=0.2,
        )

        # Optionally include the grounding tool
        if self._use_grounding_tool:
            try:
                grounding_tool = types.Tool(google_search=types.GoogleSearch())
                config_kwargs["tools"] = [grounding_tool]
            except Exception as e:  # pragma: no cover - defensive: library missing
                raise RuntimeError(
                    "Failed to configure Gemini grounding tool: %s" % e
                ) from e

        config = types.GenerateContentConfig(**config_kwargs)

        # Implement retry logic with exponential backoff for rate limit errors
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
                return self._parse_response_json(response, prompts=list(user_prompts))

            except Exception as exc:
                # Update last request time even on failure
                self._last_request_time = time.time()

                # Check if this is a retryable rate limit error (TooManyRequests/429)
                is_rate_limit = google_exceptions is not None and isinstance(
                    exc, getattr(google_exceptions, "TooManyRequests", object)
                )

                # Check if this is a permanent quota exhaustion (ResourceExhausted)
                is_quota_exhausted = google_exceptions is not None and isinstance(
                    exc, getattr(google_exceptions, "ResourceExhausted", object)
                )

                # Convert known quota/rate-limit exceptions to LLMQuotaError
                if is_quota_exhausted or is_rate_limit:

                    # ResourceExhausted is permanent, don't retry
                    if is_quota_exhausted:
                        raise LLMQuotaError("Gemini provider: quota exhausted") from exc

                    # TooManyRequests (429) is retryable
                    if is_rate_limit and attempt < self._max_retries:
                        # Calculate exponential backoff delay (as multiple of min_request_interval)
                        # Backoff: min_interval * 2^attempt
                        backoff_multiplier = 2**attempt
                        backoff_delay = self._min_request_interval * backoff_multiplier

                        # Add small base delay even if min_interval is 0
                        if self._min_request_interval == 0:
                            backoff_delay = 0.1 * backoff_multiplier

                        time.sleep(backoff_delay)
                        continue

                    # Exhausted retries
                    raise LLMQuotaError(
                        "Gemini provider: rate limited (exhausted retries)"
                    ) from exc

                # Non-quota exception, re-raise immediately
                raise

    def create_batch_job(
        self,
        batch_payload: Sequence[Sequence[str]],
        *,
        filter_json: bool | None = None,
    ) -> str:
        """Create a batch job with multiple prompts and return the job name.

        Args:
            batch_payload: Sequence of prompt sequences. Each inner sequence represents
                one generation request (prompts will be joined with newlines).
            filter_json: Whether to apply JSON filtering to responses (default: use instance setting).

        Returns:
            The batch job name that can be used to fetch results later.

        Raises:
            ValueError: If batch_payload is empty.
        """
        if not batch_payload:
            raise ValueError("batch_payload must not be empty.")

        apply_filter = self._filter_json if filter_json is None else filter_json

        # Build InlinedRequest objects for each prompt group
        inlined_requests = []
        for user_prompts in batch_payload:
            if not user_prompts:
                raise ValueError(
                    "Each prompt sequence in batch_payload must not be empty."
                )

            contents = "\n".join(user_prompts)
            config_kwargs = dict(
                system_instruction=self._system_prompt,
                thinking_config=types.ThinkingConfig(
                    thinking_budget=self.MAX_THINKING_BUDGET
                ),
                temperature=0.2,
            )

            if self._use_grounding_tool:
                try:
                    grounding_tool = types.Tool(google_search=types.GoogleSearch())
                    config_kwargs["tools"] = [grounding_tool]
                except Exception as e:  # pragma: no cover - defensive: library missing
                    raise RuntimeError(
                        "Failed to configure Gemini grounding tool: %s" % e
                    ) from e

            config = types.GenerateContentConfig(**config_kwargs)

            # Store filter setting in metadata for later retrieval
            metadata = {"filter_json": str(apply_filter).lower()}

            inlined_requests.append(
                types.InlinedRequest(
                    contents=contents,
                    config=config,
                    metadata=metadata,
                )
            )

        # Create the batch job
        batch_job = self._client.batches.create(
            model=self.MODEL,
            src=inlined_requests,
        )

        return batch_job.name

    def get_batch_job(self, batch_job_name: str) -> types.BatchJob:
        """Get the status and details of a batch job.

        Args:
            batch_job_name: The name of the batch job to retrieve.

        Returns:
            BatchJob object with status and results (if completed).
        """
        return self._client.batches.get(name=batch_job_name)

    def cancel_batch_job(self, batch_job_name: str) -> None:
        """Cancel a pending batch job.

        Args:
            batch_job_name: The name of the batch job to cancel.

        Raises:
            LLMProviderError: If cancellation fails.
        """
        from .provider import LLMProviderError

        try:
            self._client.batches.delete(name=batch_job_name)
        except Exception as e:
            raise LLMProviderError(
                f"Failed to cancel batch job {batch_job_name}: {e}"
            ) from e

    def fetch_batch_results(
        self,
        batch_job_name: str,
    ) -> Sequence[Any]:
        """Fetch and parse results from a completed batch job.

        Args:
            batch_job_name: The name of the batch job to fetch results from.

        Returns:
            Sequence of parsed responses in the same order as the original requests.
            Each response is formatted the same way as generate() output.

        Raises:
            ValueError: If the batch job is not completed or has no results.
            LLMProviderError: If individual requests failed.
        """
        from .provider import LLMProviderError

        batch_job = self.get_batch_job(batch_job_name)

        if not batch_job.done:
            raise ValueError(
                f"Batch job {batch_job_name} is not completed yet. "
                f"Current state: {batch_job.state}"
            )

        if batch_job.error:
            raise LLMProviderError(
                f"Batch job {batch_job_name} failed: {batch_job.error}"
            )

        if not batch_job.dest or not batch_job.dest.inlined_responses:
            raise ValueError(
                f"Batch job {batch_job_name} has no results. "
                f"This may indicate the job failed or was cancelled."
            )

        # Process each response
        results = []
        for idx, inlined_response in enumerate(batch_job.dest.inlined_responses):
            if inlined_response.error:
                raise LLMProviderError(
                    f"Request {idx} in batch job {batch_job_name} failed: "
                    f"{inlined_response.error}"
                )

            response = inlined_response.response
            if response is None:
                raise ValueError(
                    f"Request {idx} in batch job {batch_job_name} has no response."
                )

            # Check metadata to see if JSON filtering should be applied
            # Note: The Gemini API doesn't preserve batch_job.src, so we can't rely on metadata.
            # Instead, we'll try to parse as JSON if the response looks like it contains JSON.
            # This is a reasonable default since we typically use filter_json=True for batch jobs.
            apply_filter = False
            if (
                batch_job.src
                and batch_job.src.inlined_requests
                and idx < len(batch_job.src.inlined_requests)
            ):
                request_metadata = batch_job.src.inlined_requests[idx].metadata
                if request_metadata:
                    filter_value = request_metadata.get("filter_json", "false")
                    apply_filter = filter_value == "true"
            else:
                # No metadata available, try to detect if response contains JSON
                # Check if response has text that looks like JSON
                if hasattr(response, "text"):
                    text = response.text.strip()
                    # Check if it starts with JSON markers (possibly wrapped in code fences)
                    if (
                        text.startswith("{")
                        or text.startswith("[")
                        or "```json" in text
                    ):
                        apply_filter = True

            if apply_filter:
                try:
                    parsed_result = self._parse_response_json(response)
                    results.append(parsed_result)
                except LLMParseError as e:
                    # If JSON parsing fails, return the raw response
                    print(
                        f"Warning: Could not parse JSON from batch response {idx}: {e}"
                    )
                    results.append(response)
            else:
                results.append(response)

        return results

    def batch_generate(
        self,
        batch_payload: Sequence[Sequence[str]],
        *,
        filter_json: bool = False,
    ) -> Sequence[Any]:
        """Process multiple prompt groups in a single batch request.

        Note: This is a convenience wrapper that creates a batch job but does NOT wait
        for completion. For actual batch processing, use create_batch_job() and
        fetch_batch_results() separately.

        Args:
            batch_payload: Sequence of prompt sequences.
            filter_json: Whether to apply JSON filtering to responses.

        Raises:
            NotImplementedError: Always raised since batch jobs are asynchronous
                and require polling. Use create_batch_job() and fetch_batch_results() instead.
        """
        raise NotImplementedError(
            "Gemini batch generation is asynchronous. "
            "Use create_batch_job() to start a batch job, then poll its status "
            "and use fetch_batch_results() to retrieve completed results."
        )

    def health_check(self) -> bool:
        return True

    def _parse_response_json(
        self, response: Any, prompts: list[str] | None = None
    ) -> Any:
        """Extract and repair JSON content from a Gemini response.

        Args:
            response: The Gemini API response object
            prompts: Optional list of prompts used for the request (for error context)

        Returns:
            Parsed JSON data

        Raises:
            LLMParseError: If JSON parsing fails, with response text and prompts attached
        """
        text = getattr(response, "text", None)
        if not isinstance(text, str):
            raise LLMParseError(
                "Response object does not expose a text attribute for JSON parsing.",
                response_text=str(response),
                prompts=prompts,
            )

        try:
            return parse_json_response(text)
        except (ValueError, json.JSONDecodeError) as exc:
            raise LLMParseError(
                str(exc),
                response_text=text,
                prompts=prompts,
            ) from exc

    def _enforce_rate_limit(self) -> None:
        """Enforce minimum interval between API requests."""
        if self._min_request_interval <= 0:
            return

        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            sleep_time = self._min_request_interval - elapsed
            time.sleep(sleep_time)
