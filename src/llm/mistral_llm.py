from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from dotenv import load_dotenv
from mistralai import Mistral
from mistralai import models as mistral_models

from .json_utils import parse_json_response
from .provider import LLMProvider, LLMQuotaError


class MistralLLM(LLMProvider):
    """Wrapper around the Mistral SDK with system instructions.
    
    The system prompt can be provided either as a string directly or as a Path to a file.
    Implements thinking mode using prompt_mode="reasoning".
    """

    name = "mistral"
    MODEL = "mistral-small-latest"

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
        
        # Mistral SDK does not automatically read MISTRAL_API_KEY from environment
        # We need to read it and pass it explicitly
        if client is None:
            import os
                        
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
        messages = [
            mistral_models.SystemMessage(content=self._system_prompt),
            mistral_models.UserMessage(content="\n".join(user_prompts)),
        ]

        try:
            response = self._client.chat.complete(
                model=self.MODEL,
                messages=messages,
                prompt_mode="reasoning",  # Enable thinking mode
                temperature=0.2,
            )
        except Exception as exc:
            # Translate Mistral SDK quota/rate-limit exceptions into the
            # project's LLMQuotaError so higher-level logic can handle provider
            # fallbacks or fail fast depending on configuration.
            status_code = getattr(exc, "status_code", None)
            if status_code == 429:
                raise LLMQuotaError("Mistral provider: quota exhausted or rate limited") from exc
            raise

        if not apply_filter:
            return response

        return self._parse_response_json(response)

    def batch_generate(
        self,
        batch_payload: Sequence[Sequence[str]],
        *,
        filter_json: bool = False,
    ) -> Sequence[Any]:
        raise NotImplementedError("Mistral batch generation is not implemented yet.")

    def health_check(self) -> bool:
        return True

    def _parse_response_json(self, response: Any) -> Any:
        """Extract and repair JSON content from a Mistral response."""
        if not response.choices:
            raise AttributeError("Response object has no choices.")
        
        choice = response.choices[0]
        message = choice.message
        
        if not message.content:
            raise AttributeError("Response message does not have content for JSON parsing.")
        
        text = message.content
        if not isinstance(text, str):
            raise AttributeError("Response message content is not a string for JSON parsing.")
        
        return parse_json_response(text)