"""Unified language issue model for both detection and LLM categorisation.

This model combines the attributes from the original LanguageIssue dataclass
and the LlmLanguageIssue Pydantic model, supporting both use cases:
1. Storing detected issues from LanguageTool
2. Validating LLM-categorised issues with additional metadata
"""

from __future__ import annotations

from typing import Any, List

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import ErrorCategory, PassCode


class LanguageIssue(BaseModel):
    """Unified model for language issues, supporting both detection and LLM categorisation.

    Core fields (from LanguageTool detection):
    - filename: Document filename
    - rule_id: Rule identifier from the tool
    - message: Tool-provided message
    - issue_type: Type from the tool (e.g., "misspelling", "grammar")
    - replacements: List of suggested replacements
    - context: Original context string (deprecated, use highlighted_context)
    - highlighted_context: Context with the issue highlighted (e.g., with ** markers)
    - issue: The actual issue text extracted
    - page_number: Optional page number in the document
    - issue_id: Auto-incremented per document (-1 if not set)
    - pass_code: Optional marker indicating which workflow pass produced the issue

    LLM categorisation fields (optional):
    - error_category: LLM-assigned category (None if not categorised)
    - confidence_score: LLM confidence 0-100 (None if not categorised)
    - reasoning: LLM reasoning for the categorisation (None if not categorised)
    """

    model_config = ConfigDict(extra="forbid")

    # Core fields from LanguageTool detection
    filename: str
    rule_id: str
    message: str
    issue_type: str
    replacements: List[str] = Field(default_factory=list)
    context: str = ""  # Deprecated in favor of highlighted_context
    highlighted_context: str
    issue: str
    page_number: int | None = None
    issue_id: int = -1  # Auto-incremented per document by categoriser; -1 = not set
    pass_code: PassCode | None = None

    # LLM categorisation fields (optional)
    error_category: ErrorCategory | None = None
    confidence_score: int | None = Field(default=None, ge=0, le=100)
    reasoning: str | None = None

    # Normalisation and validation
    @field_validator("rule_id", mode="before")
    def _strip_rule(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator(
        "issue_type",
        "message",
        "context",
        "highlighted_context",
        "issue",
        mode="before",
    )
    def _strip_strings(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("filename", mode="before")
    def _strip_filename(cls, value: object) -> str:
        result = str(value or "").strip()
        if not result:
            raise ValueError("filename must not be empty")
        return result

    @field_validator("reasoning", mode="before")
    def _strip_reasoning(cls, value: object) -> str | None:
        if value is None:
            return None
        return str(value).strip() or None

    @field_validator("pass_code", mode="before")
    def _normalise_pass_code(cls, value: object) -> PassCode | None:
        if value is None or value == "":
            return None
        if isinstance(value, PassCode):
            return value
        try:
            return PassCode(str(value).strip())
        except ValueError as exc:  # pragma: no cover - handled by Pydantic validation
            raise ValueError(f"Invalid pass_code value: {value!r}") from exc

    @field_validator("replacements", mode="before")
    def _normalise_replacements(cls, value: object) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
        # allow a single suggestion as a bare string
        return [str(value).strip()]

    @field_validator("confidence_score", mode="before")
    def _validate_confidence(cls, value: Any) -> int | None:
        if value is None:
            return None
        try:
            val = int(value)
        except Exception:
            raise ValueError("confidence_score must be an integer between 0 and 100")
        if val < 0 or val > 100:
            raise ValueError("confidence_score must be between 0 and 100")
        return val

    @model_validator(mode="after")
    def final_checks(self) -> "LanguageIssue":
        # Required fields must be non-empty after normalisation
        if not self.rule_id:
            raise ValueError("rule_id must not be empty")
        if not self.issue_type:
            raise ValueError("issue_type must not be empty")
        if not self.message:
            raise ValueError("message must not be empty")
        if not self.highlighted_context:
            raise ValueError("highlighted_context must not be empty")

        # If any LLM field is set, all LLM fields should be set
        llm_fields_set = [
            self.error_category is not None,
            self.confidence_score is not None,
            self.reasoning is not None,
        ]
        if any(llm_fields_set) and not all(llm_fields_set):
            raise ValueError(
                "If LLM categorisation is present, error_category, confidence_score, "
                "and reasoning must all be provided"
            )

        if self.reasoning is not None and not self.reasoning:
            raise ValueError("reasoning must not be empty when provided")

        return self

    @classmethod
    def from_llm_response(cls, data: dict, filename: str = "") -> "LanguageIssue":
        """Create a LanguageIssue from LLM response format.

        The LLM returns fields with '_from_tool' suffix which need to be mapped
        to the standard field names.

        Args:
            data: Dictionary from LLM response with fields like rule_from_tool, type_from_tool, etc.
            filename: Document filename (not included in LLM response)

        Returns:
            A LanguageIssue instance with both tool data and LLM categorisation
        """
        return cls(
            filename=filename,
            rule_id=data.get("rule_from_tool", ""),
            message=data.get("message_from_tool", ""),
            issue_type=data.get("type_from_tool", ""),
            replacements=data.get("suggestions_from_tool", []),
            context=data.get("context_from_tool", ""),
            highlighted_context=data.get("context_from_tool", ""),
            issue=data.get(
                "context_from_tool", ""
            ),  # Use context as issue for LLM responses
            page_number=data.get("page_number"),
            issue_id=data.get("issue_id", -1),
            pass_code=data.get("pass_code") or PassCode.LTC,
            error_category=data.get("error_category"),
            confidence_score=data.get("confidence_score"),
            reasoning=data.get("reasoning"),
        )
