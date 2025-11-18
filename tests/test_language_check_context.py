from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.language_check.language_check import _make_issue
from src.models.language_issue import LanguageIssue


class FakeMatch:
    def __init__(
        self,
        *,
        context: str | None = None,
        offset: int | None = 0,
        length: int | None = 0,
    ):
        self.ruleId = "TEST_RULE"
        self.message = "A message"
        self.ruleIssueType = "misspelling"
        self.replacements = ["Foo"]
        self.context = context
        self.offsetInContext = offset
        self.errorLength = length


def test_highlight_context_fallback_to_context_on_failure(
    monkeypatch: object, tmp_path: Path
) -> None:
    # Create a match with a valid context but force _highlight_context to raise
    match = FakeMatch(context="this is a test", offset=8, length=1)

    def explode(*args, **kwargs):
        raise RuntimeError("simulated failure in _highlight_context")

    # Replace the function in the language_check module so _make_issue will call the failing helper
    monkeypatch.setattr("src.language_check.language_check._highlight_context", explode)

    issue = _make_issue(match, filename="file.md", text="this is a test")
    assert isinstance(issue, LanguageIssue)
    # When highlighting fails we should fallback to the raw context
    assert issue.highlighted_context == "this is a test"


def test_error_fetching_context_when_context_empty(monkeypatch: object) -> None:
    # Match with no context
    match = FakeMatch(context=None, offset=None, length=None)

    # Ensure _highlight_context returns empty (it would for None/"")
    issue = _make_issue(match, filename="file.md", text="")
    assert isinstance(issue, LanguageIssue)
    # Both context and highlighted_context should be set to the placeholder
    assert issue.context == "ERROR FETCHING CONTEXT"
    assert issue.highlighted_context == "ERROR FETCHING CONTEXT"
