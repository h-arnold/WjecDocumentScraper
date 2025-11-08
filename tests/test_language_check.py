from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from language_check import check_single_document, run_language_checks


class DummyMatch:
    def __init__(self) -> None:
        self.line = 0
        self.column = 0
        self.ruleId = "TEST_RULE"
        self.message = "Possible spelling mistake"
        self.ruleIssueType = "misspelling"
        self.replacements = ["This"]
        self.context = "Thiss is a test"
        self.contextoffset = 0
        self.errorLength = 4


class DummyTool:
    def __init__(self, matches: list[DummyMatch]) -> None:
        self._matches = matches
        self.captured_text: str | None = None
        self.captured_texts: list[str] = []

    def check(self, text: str) -> list[DummyMatch]:
        self.captured_text = text
        self.captured_texts.append(text)
        return self._matches

    def close(self) -> None:  # pragma: no cover - mirrors real API but unused
        return None


def test_check_single_document(tmp_path: Path) -> None:
    doc_dir = tmp_path / "Subject" / "markdown"
    doc_dir.mkdir(parents=True)
    document = doc_dir / "example.md"
    document.write_text("Thiss is a test.", encoding="utf-8")

    match = DummyMatch()
    tool = DummyTool([match])

    report = check_single_document(document, tool=tool)

    assert report.subject == "Subject"
    assert report.path == document
    assert len(report.issues) == 1

    issue = report.issues[0]
    assert issue.rule_id == "TEST_RULE"
    assert "**This**" in issue.highlighted_context
    assert tool.captured_text == "Thiss is a test."


def test_run_language_checks_document_filter(tmp_path: Path) -> None:
    root = tmp_path
    subject_dir = root / "Subject" / "markdown"
    subject_dir.mkdir(parents=True)
    document_one = subject_dir / "example-one.md"
    document_two = subject_dir / "example-two.md"
    document_one.write_text("Thiss is a test.", encoding="utf-8")
    document_two.write_text("This is fine.", encoding="utf-8")

    match = DummyMatch()
    tool = DummyTool([match])

    report_path = root / "report.md"

    run_language_checks(
        root,
        report_path=report_path,
        document=document_one.relative_to(root),
        tool=tool,
    )

    assert tool.captured_texts == ["Thiss is a test."]
    assert report_path.is_file()
    report_text = report_path.read_text(encoding="utf-8")
    assert "example-one.md" in report_text
    assert "example-two.md" not in report_text
