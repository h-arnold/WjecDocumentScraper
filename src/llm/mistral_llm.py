from __future__ import annotations

import contextlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence, cast

from dotenv import load_dotenv
from mistralai import Mistral, models

# NOTE: We intentionally avoid marshalled SDK message classes and instead
# use the `inputs`/`instructions` shape via `beta.conversations.start`.
from .json_utils import parse_json_response
from .provider import LLMParseError, LLMProvider, LLMProviderError, LLMQuotaError


class MistralLLM(LLMProvider):
    """Wrapper around the Mistral SDK with system instructions.

    The system prompt can be provided either as a string directly or as a Path to a file.
    Implements thinking mode using prompt_mode="reasoning".
    """

    name = "mistral"
    MODEL = "magistral-medium-latest"
    # Endpoint used by the batch request lines; kept stable for testing and
    # for compatibility with the SDK batch upload/execute workflow.
    _BATCH_ENDPOINT = "/v1/conversations"

    def __init__(
        self,
        system_prompt: str | Path,
        *,
        client: Mistral | None = None,
        dotenv_path: str | Path | None = None,
        filter_json: bool = False,
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
            # Load the provided dotenv file but do not override existing
            # environment variables; tests and explicit environment values
            # should take precedence.
            load_dotenv(dotenv_path=Path(dotenv_path))
        else:
            load_dotenv()

        # Mistral SDK does not automatically read MISTRAL_API_KEY from environment
        # We need to read it and pass it explicitly
        if client is None:
            api_key = os.environ.get("MISTRAL_API_KEY")
            if not api_key:
                raise ValueError(
                    "MISTRAL_API_KEY environment variable is required but not set. "
                    "Please set it in your .env file or environment."
                )
            self._client = Mistral(api_key=api_key)
        else:
            self._client = client

        self._filter_json = filter_json
        self._batch_poll_interval = self._read_float_env(
            "MISTRAL_BATCH_POLL_INTERVAL", default=2.0
        )
        self._batch_timeout = self._read_float_env(
            "MISTRAL_BATCH_TIMEOUT", default=900.0
        )

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

        # Build messages array with system message and user content
        # Build inputs (role/content) structure and instructions string to match
        # the `beta.conversations.start` shape used by the Mistral SDK examples.
        inputs = cast(
            models.ConversationInputs,
            [
                models.MessageInputEntry(
                    role="user",
                    content="\n".join(user_prompts),
                )
            ],
        )
        instructions = self._system_prompt

        try:
            # Use the new `beta.conversations.start` API shape where possible.
            # We pass `completion_args` for temperature so the call mirrors the
            # old behaviour and keeps the temperature low by default.
            # NOTE: The SDK may not supply `beta` on older versions; for those
            # cases the tests inject a dummy client implementing this shape.
            response = self._client.beta.conversations.start(
                inputs=inputs,
                instructions=instructions,
                model=self.MODEL,
                completion_args={"temperature": 0.2},
                tools=[],
            )
        except Exception as exc:
            # Translate Mistral SDK quota/rate-limit exceptions into the
            # project's LLMQuotaError so higher-level logic can handle provider
            # fallbacks or fail fast depending on configuration.
            status_code = getattr(exc, "status_code", None)
            if status_code == 429:
                raise LLMQuotaError(
                    "Mistral provider: quota exhausted or rate limited"
                ) from exc
            raise

        if not apply_filter:
            return response

        return self._parse_response_json(response, prompts=list(user_prompts))

    def batch_generate(
        self,
        batch_payload: Sequence[Sequence[str]],
        *,
        filter_json: bool | None = None,
    ) -> Sequence[Any]:
        if not batch_payload:
            return []

        apply_filter = self._filter_json if filter_json is None else filter_json

        if not hasattr(self._client, "batch") or not getattr(
            self._client.batch, "jobs", None
        ):
            raise NotImplementedError(
                "Mistral batch interface is unavailable in this SDK version."
            )

        request_lines, id_map = self._build_batch_requests(batch_payload)

        temp_path: Path | None = None
        try:
            temp_path = self._write_batch_file(request_lines)
            file_id = self._upload_batch_file(temp_path)
            job = self._submit_batch_job(file_id)
            final_job = self._wait_for_batch_job(job.id)
            if final_job.status != "SUCCESS":
                error_message = self._describe_batch_failure(final_job)
                raise LLMProviderError(error_message)

            output_file = getattr(final_job, "output_file", None)
            if not output_file:
                raise LLMProviderError(
                    "Mistral batch job completed without an output file."
                )

            line_data = self._read_batch_output(output_file)
            results: list[Any] = [None] * len(batch_payload)
            encountered_errors: list[str] = []

            for raw_line in line_data:
                if not raw_line:
                    continue
                try:
                    record = json.loads(raw_line)
                except json.JSONDecodeError as decode_error:
                    encountered_errors.append(f"Invalid JSON line: {decode_error}")
                    continue
                custom_id = record.get("custom_id")
                if custom_id not in id_map:
                    continue
                target_index = id_map[custom_id]

                error_entry = record.get("error")
                if error_entry:
                    encountered_errors.append(f"{custom_id}: {error_entry}")
                    continue

                response_block = record.get("response") or {}
                status_code = response_block.get("status_code")
                if status_code and status_code != 200:
                    encountered_errors.append(
                        f"{custom_id}: response status {status_code}"
                    )
                    continue

                body = response_block.get("body")
                if not isinstance(body, dict):
                    encountered_errors.append(f"{custom_id}: missing response body")
                    continue

                try:
                    conversation = models.ConversationResponse.model_validate(body)
                except Exception as validation_error:  # pragma: no cover - defensive
                    encountered_errors.append(
                        f"{custom_id}: invalid conversation payload ({validation_error})"
                    )
                    continue

                if apply_filter:
                    results[target_index] = self._parse_response_json(conversation)
                else:
                    results[target_index] = conversation

            missing = [idx for idx, value in enumerate(results) if value is None]
            if missing or encountered_errors:
                details = []
                if encountered_errors:
                    details.append("; ".join(encountered_errors))
                if missing:
                    details.append(
                        "Missing responses for indices: "
                        + ", ".join(str(i) for i in missing)
                    )
                raise LLMProviderError(
                    "Mistral batch job returned incomplete results: "
                    + "; ".join(details)
                )

            return results
        except Exception as exc:  # noqa: BLE001
            if self._is_quota_error(exc):
                raise LLMQuotaError(
                    "Mistral provider: quota exhausted or rate limited"
                ) from exc
            raise
        finally:
            if temp_path is not None:
                with contextlib.suppress(FileNotFoundError):
                    temp_path.unlink()

                    def _parse_batch_results(
                        self,
                        line_data: Sequence[str],
                        id_map: dict[str, int],
                        apply_filter: bool,
                    ) -> list[Any]:
                        """Parse JSONL lines from a Mistral batch job output.

                        Returns a list of parsed responses in the original batch order. Raises
                        LLMProviderError if any lines are invalid or the job returned incomplete results.
                        """
                        # Determine expected result list length based on highest index in id_map
                        expected_length = max(id_map.values()) + 1 if id_map else 0
                        results: list[Any] = [None] * expected_length
                        encountered_errors: list[str] = []

                        for raw_line in line_data:
                            if not raw_line:
                                continue
                            try:
                                record = json.loads(raw_line)
                            except json.JSONDecodeError as decode_error:
                                encountered_errors.append(
                                    f"Invalid JSON line: {decode_error}"
                                )
                                continue

                            custom_id = record.get("custom_id")
                            if custom_id not in id_map:
                                # Unknown line (perhaps from a different job); ignore
                                continue
                            target_index = id_map[custom_id]

                            error_entry = record.get("error")
                            if error_entry:
                                encountered_errors.append(f"{custom_id}: {error_entry}")
                                continue

                            response_block = record.get("response") or {}
                            status_code = response_block.get("status_code")
                            if status_code and status_code != 200:
                                encountered_errors.append(
                                    f"{custom_id}: response status {status_code}"
                                )
                                continue

                            body = response_block.get("body")
                            if not isinstance(body, dict):
                                encountered_errors.append(
                                    f"{custom_id}: missing response body"
                                )
                                continue

                            try:
                                conversation = (
                                    models.ConversationResponse.model_validate(body)
                                )
                            except (
                                Exception
                            ) as validation_error:  # pragma: no cover - defensive
                                encountered_errors.append(
                                    f"{custom_id}: invalid conversation payload ({validation_error})"
                                )
                                continue

                            if apply_filter:
                                try:
                                    results[target_index] = self._parse_response_json(
                                        conversation
                                    )
                                except Exception as parse_error:
                                    encountered_errors.append(
                                        f"{custom_id}: JSON parsing error ({parse_error})"
                                    )
                            else:
                                results[target_index] = conversation

                        missing = [
                            idx for idx, value in enumerate(results) if value is None
                        ]
                        if missing or encountered_errors:
                            details: list[str] = []
                            if encountered_errors:
                                details.append("; ".join(encountered_errors))
                            if missing:
                                details.append(
                                    "Missing responses for indices: "
                                    + ", ".join(str(i) for i in missing)
                                )
                            raise LLMProviderError(
                                "Mistral batch job returned incomplete results: "
                                + "; ".join(details)
                            )

                        return results

    def health_check(self) -> bool:
        return True

    def _parse_response_json(
        self, response: Any, prompts: list[str] | None = None
    ) -> Any:
        """Extract and repair JSON content from a Mistral response.

        Args:
            response: The Mistral API response object
            prompts: Optional list of prompts used for the request (for error context)

        Returns:
            Parsed JSON data

        Raises:
            LLMParseError: If JSON parsing fails, with response text and prompts attached
        """
        # The Mistral SDK returns structured response objects. We support the
        # two canonical shapes we expect from recent SDKs and older OpenAI-style
        # SDK shapes (in PRECEDENCE order):
        # 1. response.outputs -> list of MessageOutputEntry items with a
        #    `content` attribute which is a string (often a fenced JSON block)
        # 2. response.choices[0].message.content -> older style; keep this for
        #    backward compatibility with the code in tests.
        # Do not attempt speculative fallbacks for other properties.
        text: str | None = None

        # Preferred: new 'outputs' shape used by beta.conversations.start
        if hasattr(response, "outputs") and isinstance(
            getattr(response, "outputs"), list
        ):
            for entry in getattr(response, "outputs"):
                # Entry could be an object with a `.content` attribute or a dict
                content_val = None
                if isinstance(entry, dict):
                    content_val = entry.get("content")
                else:
                    content_val = getattr(entry, "content", None)

                if isinstance(content_val, str) and content_val.strip():
                    text = content_val
                    break

        # Backwards-compatible: OpenAI-style `choices` property
        if text is None and hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            message = getattr(choice, "message", None)
            if message is not None:
                maybe = getattr(message, "content", None)
                if isinstance(maybe, str):
                    text = maybe

        if not isinstance(text, str):
            raise LLMParseError(
                "Response message content is not a string for JSON parsing; expected `outputs` or `choices` shapes.",
                response_text=str(response),
                prompts=prompts,
            )

        # parse_json_response does extraction and repair of common JSON issues
        try:
            return parse_json_response(text)
        except (ValueError, json.JSONDecodeError) as exc:
            raise LLMParseError(
                str(exc),
                response_text=text,
                prompts=prompts,
            ) from exc

    def _build_batch_requests(
        self,
        batch_payload: Sequence[Sequence[str]],
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        request_lines: list[dict[str, Any]] = []
        id_map: dict[str, int] = {}

        for index, prompts in enumerate(batch_payload):
            if not prompts:
                raise ValueError(
                    "Batch payload entries must contain at least one prompt."
                )

            custom_id = f"req-{index:05d}"
            id_map[custom_id] = index

            body: dict[str, Any] = {
                "inputs": [
                    {
                        "type": "message.input",
                        "role": "user",
                        "content": "\n".join(prompts),
                    }
                ],
                "completion_args": {"temperature": 0.2},
                "tools": [],
            }

            if self._system_prompt:
                body["instructions"] = self._system_prompt

            request_lines.append(
                {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": self._BATCH_ENDPOINT,
                    "body": body,
                }
            )

        return request_lines, id_map

    def _write_batch_file(self, request_lines: Sequence[dict[str, Any]]) -> Path:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".jsonl", delete=False
        ) as handle:
            for line in request_lines:
                handle.write(json.dumps(line))
                handle.write("\n")
        return Path(handle.name)

    def _upload_batch_file(self, file_path: Path) -> str:
        with file_path.open("rb") as input_stream:
            upload = self._client.files.upload(
                file=models.File(file_name=file_path.name, content=input_stream),
                purpose="batch",
            )
        return getattr(upload, "id")

    def _submit_batch_job(self, file_id: str) -> Any:
        return self._client.batch.jobs.create(
            input_files=[file_id],
            endpoint="/v1/conversations",
            model=self.MODEL,
        )

    def _wait_for_batch_job(self, job_id: str) -> Any:
        deadline = time.time() + self._batch_timeout
        while True:
            job = self._client.batch.jobs.get(job_id=job_id)
            status = getattr(job, "status", "")
            if status in {"SUCCESS", "FAILED", "TIMEOUT_EXCEEDED", "CANCELLED"}:
                return job
            if time.time() > deadline:
                raise LLMProviderError(
                    f"Mistral batch job {job_id} did not finish within the allotted time."
                )
            time.sleep(self._batch_poll_interval)

    def _describe_batch_failure(self, job: Any) -> str:
        status = getattr(job, "status", "UNKNOWN")
        message_parts = [f"Mistral batch job failed with status {status}"]

        errors = getattr(job, "errors", None)
        if errors:
            serialized = ", ".join(str(err) for err in errors)
            message_parts.append(f"errors: {serialized}")

        error_file = getattr(job, "error_file", None)
        if error_file:
            try:
                text = self._download_file_text(error_file)
                if text:
                    message_parts.append(f"error file contents: {text.strip()[:500]}")
            except Exception:  # pragma: no cover - best effort
                message_parts.append("error file could not be retrieved")

        return "; ".join(message_parts)

    def _read_batch_output(self, file_id: str) -> list[str]:
        text = self._download_file_text(file_id)
        return [line for line in text.splitlines() if line.strip()]

    def _download_file_text(self, file_id: str) -> str:
        response_obj = self._client.files.download(file_id=file_id)

        # If the SDK's response is a context manager (e.g., httpx.Response),
        # use it to ensure deterministic cleanup. Otherwise, fall back to manual closing.
        if hasattr(response_obj, "__enter__") and callable(
            getattr(response_obj, "__enter__")
        ):
            with response_obj as response:
                try:
                    return response.text
                except AttributeError:  # pragma: no cover - httpx compatibility
                    return response.read().decode("utf-8")  # type: ignore[call-arg]
        else:
            try:
                try:
                    return response_obj.text
                except AttributeError:  # pragma: no cover - httpx compatibility
                    return response_obj.read().decode("utf-8")  # type: ignore[call-arg]
            finally:
                with contextlib.suppress(Exception):
                    response_obj.close()  # type: ignore[attr-defined]

    def _is_quota_error(self, exc: Exception) -> bool:
        return getattr(exc, "status_code", None) == 429

    @staticmethod
    def _read_float_env(var_name: str, *, default: float) -> float:
        try:
            raw = os.environ.get(var_name)
            if raw is None:
                return default
            value = float(raw)
        except ValueError:
            return default
        return value
