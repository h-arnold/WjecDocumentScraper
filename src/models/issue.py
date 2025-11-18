"""Pydantic models representing a single LLM-validated language tool issue.

This maps to the JSON 'Error Object' from the categoriser prompt. We apply
validation rules to ensure fields follow expectations and that values are
sanitised (trimmed strings, limited confidence, enum-backed categories).
"""

from __future__ import annotations

from typing import Any, List

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.models.enums import ErrorCategory


class LlmLanguageIssue(BaseModel):
    """Model for a single language tool issue categorised by the LLM.

    Contract:
    - rule_from_tool: the rule name returned by the tool (non-empty string)
    - type_from_tool: the tool type (e.g., "misspelling", "grammar")
    - message_from_tool: tool-provided explanatory message
    - suggestions_from_tool: list of suggestions returned by the tool; a
      single string will be converted to a one-item list for convenience
    - context_from_tool: short snippet of the document for disambiguation
    - error_category: one of the ErrorCategory enum values
    - confidence_score: integer 0-100
    - reasoning: a short single-sentence justification
    """

    model_config = ConfigDict(extra="forbid")

    rule_from_tool: str
    type_from_tool: str
    message_from_tool: str
    suggestions_from_tool: List[str] = Field(default_factory=list)
    context_from_tool: str
    error_category: ErrorCategory
    confidence_score: int = Field(default=0)
    reasoning: str

    # Normalisation: trim strings, accept None->empty, coerce single string to list
    @field_validator("rule_from_tool", mode="before")
    def _strip_rule(cls, value: object) -> str:  # type: ignore[override]
        return str(value or "").strip()

    @field_validator(
        "type_from_tool",
        "message_from_tool",
        "context_from_tool",
        "reasoning",
        mode="before",
    )
    def _strip_strings(cls, value: object) -> str:  # type: ignore[override]
        return str(value or "").strip()

    @field_validator("suggestions_from_tool", mode="before")
    def _normalise_suggestions(cls, value: object) -> List[str]:  # type: ignore[override]
        if value is None:
            return []
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
        # allow a single suggestion as a bare string
        return [str(value).strip()]

    @field_validator("confidence_score", mode="before")
    def _validate_confidence(cls, value: Any) -> int:  # type: ignore[override]
        try:
            val = int(value)
        except Exception:
            raise ValueError("confidence_score must be an integer between 0 and 100")
        if val < 0 or val > 100:
            raise ValueError("confidence_score must be between 0 and 100")
        return val

    @model_validator(mode="after")
    def final_checks(self) -> "LlmLanguageIssue":
        # Required fields must be non-empty after normalisation
        if not self.rule_from_tool:
            raise ValueError("rule_from_tool must not be empty")
        if not self.type_from_tool:
            raise ValueError("type_from_tool must not be empty")
        if not self.message_from_tool:
            raise ValueError("message_from_tool must not be empty")
        if not self.context_from_tool:
            raise ValueError("context_from_tool must not be empty")
        if not self.reasoning:
            raise ValueError("reasoning must not be empty")

        # The error category is already validated by pydantic via enum coercion.
        return self
