from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import pytest

# Ensure project root is importable (consistent with other tests)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.service import LLMService
from src.llm_review.core.state_manager import StateManager
from src.llm_review.llm_proofreader.runner import ProofreaderRunner
from src.models import DocumentKey, LanguageIssue
from src.models.enums import ErrorCategory


class _StubLLMService(LLMService):
    """Minimal LLMService stub for validation tests."""

    def __init__(self) -> None:
        super().__init__(providers=[])

    def generate(self, user_prompts, *, filter_json=False):  # pragma: no cover - defensive
        raise AssertionError("LLMService.generate should not be called during validation tests")


@dataclass
class _RunnerFixtures:
    runner: ProofreaderRunner
    state: StateManager


@pytest.fixture()
def proofreader_runner(tmp_path) -> _RunnerFixtures:
    state_file = tmp_path / "state.json"
    state = StateManager(state_file)
    runner = ProofreaderRunner(_StubLLMService(), state)

    runner.config.input_csv_path = tmp_path / "input.csv"
    runner.config.output_base_dir = tmp_path / "output"
    runner.config.state_file = state_file
    runner.config.log_response_dir = tmp_path / "logs"
    runner.persistence.config = runner.config

    return _RunnerFixtures(runner=runner, state=state)


def _make_issue(issue_id: int, filename: str = "doc.md") -> LanguageIssue:
    return LanguageIssue(
        filename=filename,
        rule_id="RULE",
        message="Example message",
        issue_type="grammar",
        replacements=[],
        context="The **issue** appears here.",
        highlighted_context="The **issue** appears here.",
        issue="issue",
        page_number=1,
        issue_id=issue_id,
        pass_code=None,
    )


def _make_response_row(issue: str, *, page: int = 1) -> dict[str, object]:
    return {
        "issue": issue,
        "highlighted_context": f"Context with **{issue}**.",
        "error_category": ErrorCategory.SPELLING_ERROR.value,
        "confidence_score": 90,
        "reasoning": "Detected spelling issue.",
        "page_number": page,
    }


def test_issue_ids_start_from_zero_and_increment(proofreader_runner: _RunnerFixtures) -> None:
    runner = proofreader_runner.runner
    key = DocumentKey("Subject", "doc.md")
    issues = [_make_issue(10), _make_issue(11)]
    response = [_make_response_row("alpha"), _make_response_row("beta")]

    runner._active_document_key = key
    try:
        validated, failed, errors = runner.validate_response(response, issues)
    finally:
        runner._active_document_key = None

    assert failed == set()
    assert errors["batch_errors"] == []
    assert [item["issue_id"] for item in validated] == [0, 1]


def test_issue_ids_continue_across_batches(proofreader_runner: _RunnerFixtures) -> None:
    runner = proofreader_runner.runner
    key = DocumentKey("Subject", "doc.md")

    first_batch_issues = [_make_issue(20), _make_issue(21)]
    first_response = [_make_response_row("alpha"), _make_response_row("beta")]

    runner._active_document_key = key
    try:
        validated, _, _ = runner.validate_response(first_response, first_batch_issues)
    finally:
        runner._active_document_key = None

    assert [item["issue_id"] for item in validated] == [0, 1]

    second_batch_issues = [_make_issue(30), _make_issue(31), _make_issue(32)]
    second_response = [
        _make_response_row("gamma"),
        _make_response_row("delta"),
        _make_response_row("epsilon"),
    ]

    runner._active_document_key = key
    try:
        validated_two, failed, errors = runner.validate_response(
            second_response, second_batch_issues
        )
    finally:
        runner._active_document_key = None

    assert failed == set()
    assert errors["batch_errors"] == []
    assert [item["issue_id"] for item in validated_two] == [2, 3, 4]


def test_issue_id_counter_rolls_back_on_validation_error(
    proofreader_runner: _RunnerFixtures,
) -> None:
    runner = proofreader_runner.runner
    key = DocumentKey("Subject", "doc.md")

    issues = [_make_issue(40)]
    bad_response = [
        {
            "issue": "invalid",
            "highlighted_context": "Context with **invalid**.",
            "error_category": ErrorCategory.SPELLING_ERROR.value,
            # Invalid score (>100) triggers validation error
            "confidence_score": 150,
            "reasoning": "Score too high.",
            "page_number": 1,
        }
    ]

    runner._active_document_key = key
    try:
        validated, failed, errors = runner.validate_response(bad_response, issues)
    finally:
        runner._active_document_key = None

    assert validated == []
    assert failed == {40}
    assert errors[40]

    # Next successful validation should still start from zero
    good_response = [_make_response_row("fixed")]
    runner._active_document_key = key
    try:
        validated_next, failed_next, errors_next = runner.validate_response(
            good_response, issues
        )
    finally:
        runner._active_document_key = None

    assert failed_next == set()
    assert errors_next["batch_errors"] == []
    assert [row["issue_id"] for row in validated_next] == [0]
