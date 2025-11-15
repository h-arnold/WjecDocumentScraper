from __future__ import annotations

from pydantic import ValidationError

from src.models import ErrorCategory, LlmLanguageIssue


def test_llm_language_issue_valid() -> None:
    data = {
        "rule_from_tool": "EN_QUOTES",
        "type_from_tool": "grammar",
        "message_from_tool": "Use smart quotes.",
        "suggestions_from_tool": "Use ‘ and ’ instead of '",
        "context_from_tool": "she said 'hello'",
    "error_category": "PARSING_ERROR",
        "confidence_score": 87,
        "reasoning": "Tool flags ASCII quotes where typographic ones are expected.",
    }

    issue = LlmLanguageIssue.model_validate(data)
    assert isinstance(issue, LlmLanguageIssue)
    assert issue.error_category == ErrorCategory.PARSING_ERROR
    assert issue.suggestions_from_tool == ["Use ‘ and ’ instead of '"]


def test_llm_language_issue_invalid_confidence() -> None:
    data = {
        "rule_from_tool": "EN_QUOTES",
        "type_from_tool": "grammar",
        "message_from_tool": "Use smart quotes.",
        "suggestions_from_tool": ["Use ‘ and ’"],
        "context_from_tool": "she said 'hello'",
        "error_category": ErrorCategory.PARSING_ERROR,
        "confidence_score": 150,
        "reasoning": "Too high confidence.",
    }
    try:
        LlmLanguageIssue.model_validate(data)
        assert False, "Expected ValidationError for confidence_score"
    except ValidationError as exc:
        assert "confidence_score must be between 0 and 100" in str(exc)


def test_llm_language_issue_missing_required() -> None:
    data = {
        "rule_from_tool": "",
        "type_from_tool": "",
        "message_from_tool": "",
        "suggestions_from_tool": [],
        "context_from_tool": "",
    "error_category": "FALSE_POSITIVE",
        "confidence_score": 10,
        "reasoning": "",
    }

    try:
        LlmLanguageIssue.model_validate(data)
        assert False, "Expected ValidationError because several fields are empty"
    except ValidationError as exc:
        assert "must not be empty" in str(exc)
