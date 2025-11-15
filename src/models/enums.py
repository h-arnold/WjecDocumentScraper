"""Enumerations used by the LLM language issue models.

These map directly to the `Error Categories` list in
`src/prompt/promptFiles/language_tool_categoriser.md`.
"""
from __future__ import annotations

from enum import Enum


class ErrorCategory(str, Enum):
    """All valid categories used to classify LanguageTool issues.

    Values must match the wording used in the prompt file. They are intentionally
    human-readable and suitable for use as serialised JSON fields.
    """

    PARSING_ERROR = "PARSING_ERROR"
    SPELLING_ERROR = "SPELLING_ERROR"
    ABSOLUTE_GRAMMATICAL_ERROR = "ABSOLUTE_GRAMMATICAL_ERROR"
    POSSIBLE_AMBIGUOUS_GRAMMATICAL_ERROR = "POSSIBLE_AMBIGUOUS_GRAMMATICAL_ERROR"
    STYLISTIC_PREFERENCE = "STYLISTIC_PREFERENCE"
    FALSE_POSITIVE = "FALSE_POSITIVE"

    @classmethod
    def all_values(cls) -> list[str]:
        return [m.value for m in cls]
