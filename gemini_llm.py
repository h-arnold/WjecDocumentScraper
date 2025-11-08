from __future__ import annotations

from pathlib import Path
from typing import Sequence

from google import genai
from google.genai import types


class GeminiLLM:
    """Wrapper around the Gemini SDK with file-backed system instructions."""

    MODEL = "gemini-flash-2.5"
    MAX_THINKING_BUDGET = 24_576

    def __init__(self, system_prompt_path: str | Path, *, client: genai.Client | None = None) -> None:
        self._system_prompt_path = Path(system_prompt_path)
        self._system_prompt = self._system_prompt_path.read_text(encoding="utf-8")
        self._client = client or genai.Client()

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    def generate(self, user_prompts: Sequence[str]) -> types.GenerateContentResponse:
        if not user_prompts:
            raise ValueError("user_prompts must not be empty.")

        contents = "\n".join(user_prompts)
        config = types.GenerateContentConfig(
            system_instruction=self._system_prompt,
            thinking_config=types.ThinkingConfig(thinking_budget=self.MAX_THINKING_BUDGET),
        )
        return self._client.models.generate_content(
            model=self.MODEL,
            contents=contents,
            config=config,
        )
