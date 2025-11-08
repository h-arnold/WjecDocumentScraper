from __future__ import annotations

import csv
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
    assert issue.filename == "example.md"
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


def test_csv_report_generated(tmp_path: Path) -> None:
    """Test that CSV report is created with correct structure and content."""
    root = tmp_path
    subject_dir = root / "Subject" / "markdown"
    subject_dir.mkdir(parents=True)
    document = subject_dir / "test-doc.md"
    document.write_text("Thiss is a test.", encoding="utf-8")

    match = DummyMatch()
    tool = DummyTool([match])

    report_path = root / "report.md"
    run_language_checks(
        root,
        report_path=report_path,
        tool=tool,
    )

    # Check that CSV file was created
    csv_path = root / "report.csv"
    assert csv_path.is_file()

    # Read and verify CSV content
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Check header row
    assert rows[0] == [
        "Subject",
        "Filename",
        "Line",
        "Column",
        "Rule ID",
        "Type",
        "Message",
        "Suggestions",
        "Context"
    ]

    # Check data row
    assert len(rows) == 2  # header + 1 issue
    assert rows[1][0] == "Subject"  # subject
    assert rows[1][1] == "test-doc.md"  # filename
    assert rows[1][2] == "1"  # line
    assert rows[1][3] == "1"  # column
    assert rows[1][4] == "TEST_RULE"  # rule_id
    assert rows[1][5] == "misspelling"  # type
    assert "spelling mistake" in rows[1][6]  # message
    assert "This" in rows[1][7]  # suggestions
    assert "Thiss is a test" in rows[1][8]  # context

