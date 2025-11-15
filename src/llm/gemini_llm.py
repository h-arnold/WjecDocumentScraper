from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from dotenv import load_dotenv
from google import genai
from google.genai import types

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
        response = self._client.models.generate_content(
            model=self.MODEL,
            contents=contents,
            config=config,
        )
        if not apply_filter:
            return response

        return self._parse_response_json(response)

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
