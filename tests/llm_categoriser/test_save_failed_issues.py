from __future__ import annotations

from pathlib import Path
import json

from src.models.document_key import DocumentKey
from src.models.language_issue import LanguageIssue
from src.llm_review.llm_categoriser.persistence import save_failed_issues


def make_issue() -> LanguageIssue:
    return LanguageIssue(
        filename="gcse-art-and-design.md",
        rule_id="R1",
        message="Sample",
        issue_type="misspelling",
        replacements=["Sample"],
        highlighted_context="Sample",
        issue="Sample",
        page_number=1,
        issue_id=123,
    )


def test_save_failed_issues_writes_file(tmp_path: Path) -> None:
    key = DocumentKey(subject="Art-and-Design", filename="gcse-art-and-design.md")
    issue = make_issue()

    output_path = save_failed_issues(key, 0, [issue], error_messages={issue.issue_id: ["validation failed"]}, output_dir=tmp_path)
    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["subject"] == key.subject
    assert data["filename"] == key.filename
    assert data["batch_index"] == 0
    assert isinstance(data["issues"], list) and data["issues"]
    assert data["issues"][0]["issue_id"] == 123
    # Check we wrote error messages correctly
    assert "errors" in data
    assert data["errors"][str(issue.issue_id)] == ["validation failed"]


def test_runner_saves_failed_issues(tmp_path: Path, monkeypatch) -> None:
    # Create a dummy provider that returns an empty dict -> validation fails
    class DummyProvider:
        name = "dummy"

        def __init__(self, system_prompt, filter_json, dotenv_path):
            pass

        def generate(self, user_prompts, *, filter_json=False):
            return {}

        def batch_generate(self, batch_payload, *, filter_json=False):
            raise NotImplementedError()

        def health_check(self):
            return True

    from src.llm.service import LLMService
    from src.llm_review.llm_categoriser.runner import CategoriserRunner
    from src.llm_review.llm_categoriser.state import CategoriserState
    from src.llm_review.llm_categoriser.batcher import Batch
    from src.models.document_key import DocumentKey

    providers = [DummyProvider(system_prompt="s", filter_json=True, dotenv_path=None)]
    llm_service = LLMService(providers)
    state = CategoriserState(tmp_path / "state.json")

    # Create runner
    runner = CategoriserRunner(llm_service, state, max_retries=1)

    # Create a single issue and batch
    issue = LanguageIssue(
        filename="gcse-test.md",
        rule_id="R1",
        message="Test",
        issue_type="misspelling",
        replacements=[],
        highlighted_context="Test",
        issue="Test",
        page_number=1,
        issue_id=5,
    )

    batch = Batch(subject="Art-and-Design", filename="gcse-test.md", index=0, issues=[issue], page_context={1: "content"}, markdown_table="|issue|")

    # Monkeypatch save_failed_issues to write into tmp_path and capture call
    saved = {}

    def fake_save_failed_issues(key, batch_idx, failed_issues, *, error_messages=None, output_dir=Path("data")):
        p = tmp_path / "errors" / key.subject
        p.mkdir(parents=True, exist_ok=True)
        f = p / f"{key.filename}.batch-{batch_idx}.errors.json"
        f.write_text('{"ok": true}')
        saved["path"] = f
        saved["errors"] = error_messages
        return f

    # Patch the function used by runner (imported into runner module at import time)
    monkeypatch.setattr("src.llm_review.llm_categoriser.runner.save_failed_issues", fake_save_failed_issues)

    ok = runner._process_batch(DocumentKey(subject="Art-and-Design", filename="gcse-test.md"), batch)
    # _process_batch returns False because no valid results saved
    assert ok is False
    assert "path" in saved
    assert saved["path"].exists()
    # Check we saw aggregated errors from _validate_response
    assert saved.get("errors") is not None
    assert "batch_errors" in saved["errors"]


def test_runner_writes_errors_to_data(tmp_path: Path, monkeypatch) -> None:
    """Integration test: runner should write a failed-issues file with errors to data."""

    # Use the real persistence function but write into tmp_path
    from src.llm_review.llm_categoriser import persistence as persistence_mod

    # Create a dummy provider that returns an empty dict -> validation fails
    class DummyProvider:
        name = "dummy"

        def __init__(self, system_prompt, filter_json, dotenv_path):
            pass

        def generate(self, user_prompts, *, filter_json=False):
            return {}

        def batch_generate(self, batch_payload, *, filter_json=False):
            raise NotImplementedError()

        def health_check(self):
            return True

    from src.llm.service import LLMService
    from src.llm_review.llm_categoriser.runner import CategoriserRunner
    from src.llm_review.llm_categoriser.state import CategoriserState
    from src.llm_review.llm_categoriser.batcher import Batch
    from src.models.document_key import DocumentKey

    providers = [DummyProvider(system_prompt="s", filter_json=True, dotenv_path=None)]
    llm_service = LLMService(providers)
    state = CategoriserState(tmp_path / "state.json")

    runner = CategoriserRunner(llm_service, state, max_retries=1)

    issue = LanguageIssue(
        filename="gcse-test.md",
        rule_id="R1",
        message="Test",
        issue_type="misspelling",
        replacements=[],
        highlighted_context="Test",
        issue="Test",
        page_number=1,
        issue_id=5,
    )

    batch = Batch(subject="Art-and-Design", filename="gcse-test.md", index=0, issues=[issue], page_context={1: "content"}, markdown_table="|issue|")

    # Wrap the real persistence so it writes into tmp_path
    def real_save_failed_issues(key, batch_idx, failed_issues, *, error_messages=None, output_dir=Path("data")):
        return persistence_mod.save_failed_issues(key, batch_idx, failed_issues, error_messages=error_messages, output_dir=tmp_path)

    monkeypatch.setattr("src.llm_review.llm_categoriser.runner.save_failed_issues", real_save_failed_issues)

    ok = runner._process_batch(DocumentKey(subject="Art-and-Design", filename="gcse-test.md"), batch)

    assert ok is False
    # Ensure file was written into tmp_path
    err_path = tmp_path / "llm_categoriser_errors" / "Art-and-Design" / "gcse-test.md.batch-0.errors.json"
    assert err_path.exists()

    data = json.loads(err_path.read_text(encoding="utf-8"))
    assert "errors" in data
    assert data["errors"].get("batch_errors") is not None