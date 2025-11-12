from __future__ import annotations

import csv
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.language_check import check_single_document, run_language_checks


class DummyMatch:
    def __init__(self) -> None:
        self.ruleId = "TEST_RULE"
        self.message = "Possible spelling mistake"
        self.ruleIssueType = "misspelling"
        self.replacements = ["This"]
        self.context = "Thiss is a test"
        self.contextoffset = 0
        self.offsetInContext = 0
        self.errorLength = 4
        self.matchedText = "Thiss"


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
        "Page",
        "Rule ID",
        "Type",
        "Issue",
        "Message",
        "Suggestions",
        "Context"
    ]

    # Check data row
    assert len(rows) == 2  # header + 1 issue
    assert rows[1][0] == "Subject"  # subject
    assert rows[1][1] == "test-doc.md"  # filename
    # rows[1][2] is page number (could be empty if no page markers)
    assert rows[1][3] == "TEST_RULE"  # rule_id
    assert rows[1][4] == "misspelling"  # type
    assert rows[1][5] == "This"  # issue (extracted text)
    assert "spelling mistake" in rows[1][6]  # message
    assert "This" in rows[1][7]  # suggestions
    assert "Thiss is a test" in rows[1][8]  # context


def test_ignored_words_filtering(tmp_path: Path) -> None:
    """Test that ignored words are filtered from results."""
    root = tmp_path
    subject_dir = root / "Subject" / "markdown"
    subject_dir.mkdir(parents=True)
    document = subject_dir / "test-doc.md"
    document.write_text("WJEC CBAC test document.", encoding="utf-8")

    # Create matches for WJEC and CBAC
    wjec_match = DummyMatch()
    wjec_match.ruleId = "MORFOLOGIK_RULE_EN_GB"
    wjec_match.message = "Possible spelling mistake"
    wjec_match.matchedText = "WJEC"
    
    cbac_match = DummyMatch()
    cbac_match.ruleId = "MORFOLOGIK_RULE_EN_GB"
    cbac_match.message = "Possible spelling mistake"
    cbac_match.matchedText = "CBAC"

    tool = DummyTool([wjec_match, cbac_match])

    report_path = root / "report.md"
    
    # Run with default ignored words (should filter out WJEC and CBAC)
    run_language_checks(
        root,
        report_path=report_path,
        tool=tool,
        ignored_words={"WJEC", "CBAC"},  # Case-sensitive: must match exact casing
    )

    # Check that issues were filtered
    report_text = report_path.read_text(encoding="utf-8")
    assert "Total issues found: 0" in report_text


def test_case_sensitive_ignored_words_uppercase(tmp_path: Path) -> None:
    """Test that uppercase acronyms are filtered when in the ignore list."""
    root = tmp_path
    subject_dir = root / "Subject" / "markdown"
    subject_dir.mkdir(parents=True)
    document = subject_dir / "test-doc.md"
    document.write_text("This document mentions WJEC and CPU.", encoding="utf-8")

    # Create matches for WJEC and CPU (both uppercase)
    wjec_match = DummyMatch()
    wjec_match.matchedText = "WJEC"
    
    cpu_match = DummyMatch()
    cpu_match.matchedText = "CPU"

    tool = DummyTool([wjec_match, cpu_match])
    report_path = root / "report.md"
    
    # Both WJEC and CPU are in DEFAULT_IGNORED_WORDS (uppercase)
    # so they should be filtered out
    run_language_checks(
        root,
        report_path=report_path,
        tool=tool,
    )

    report_text = report_path.read_text(encoding="utf-8")
    assert "Total issues found: 0" in report_text


def test_case_sensitive_ignored_words_lowercase_not_filtered(tmp_path: Path) -> None:
    """Test that lowercase variants are NOT filtered when only uppercase is in the list."""
    root = tmp_path
    subject_dir = root / "Subject" / "markdown"
    subject_dir.mkdir(parents=True)
    document = subject_dir / "test-doc.md"
    document.write_text("This mentions wjec and cpu in lowercase.", encoding="utf-8")

    # Create matches for lowercase variants
    wjec_match = DummyMatch()
    wjec_match.matchedText = "wjec"
    wjec_context = "This mentions wjec and cpu in lowercase."
    wjec_match.context = wjec_context
    wjec_match.offsetInContext = wjec_context.index("wjec")
    wjec_match.errorLength = len("wjec")
    
    cpu_match = DummyMatch()
    cpu_match.matchedText = "cpu"
    cpu_match.context = wjec_context
    cpu_match.offsetInContext = wjec_context.index("cpu")
    cpu_match.errorLength = len("cpu")

    tool = DummyTool([wjec_match, cpu_match])
    report_path = root / "report.md"
    
    # Only uppercase WJEC and CPU are in DEFAULT_IGNORED_WORDS
    # lowercase "wjec" and "cpu" should NOT be filtered (case-sensitive)
    run_language_checks(
        root,
        report_path=report_path,
        tool=tool,
    )

    report_text = report_path.read_text(encoding="utf-8")
    # Both issues should still be present (not filtered)
    assert "Total issues found: 2" in report_text
    assert "wjec" in report_text.lower()
    assert "cpu" in report_text.lower()


def test_case_sensitive_ignored_words_mixed_case_not_filtered(tmp_path: Path) -> None:
    """Test that mixed case (Titlecase) is NOT filtered when only uppercase is in the list."""
    root = tmp_path
    subject_dir = root / "Subject" / "markdown"
    subject_dir.mkdir(parents=True)
    document = subject_dir / "test-doc.md"
    document.write_text("References to Wjec and Cpu.", encoding="utf-8")

    # Create matches for Titlecase variants
    wjec_match = DummyMatch()
    wjec_match.matchedText = "Wjec"
    
    cpu_match = DummyMatch()
    cpu_match.matchedText = "Cpu"

    tool = DummyTool([wjec_match, cpu_match])
    report_path = root / "report.md"
    
    # Only uppercase WJEC and CPU are in DEFAULT_IGNORED_WORDS
    # Titlecase "Wjec" and "Cpu" should NOT be filtered
    run_language_checks(
        root,
        report_path=report_path,
        tool=tool,
    )

    report_text = report_path.read_text(encoding="utf-8")
    # Both issues should still be present (not filtered)
    assert "Total issues found: 2" in report_text


def test_case_sensitive_ignored_words_with_plural(tmp_path: Path) -> None:
    """Test that plural forms with trailing 's' are handled correctly."""
    root = tmp_path
    subject_dir = root / "Subject" / "markdown"
    subject_dir.mkdir(parents=True)
    document = subject_dir / "test-doc.md"
    document.write_text("Multiple NICs are needed.", encoding="utf-8")

    # Create match for "NICs" (plural)
    nics_match = DummyMatch()
    nics_match.matchedText = "NICs"

    tool = DummyTool([nics_match])
    report_path = root / "report.md"
    
    # "NICs" is in DEFAULT_IGNORED_WORDS, so it should be filtered
    run_language_checks(
        root,
        report_path=report_path,
        tool=tool,
    )

    report_text = report_path.read_text(encoding="utf-8")
    assert "Total issues found: 0" in report_text


def test_case_sensitive_ignored_words_singular_strips_s(tmp_path: Path) -> None:
    """Test that plural acronym is filtered when only the singular form is in the ignored words list (tests plural-stripping logic)."""
    root = tmp_path
    subject_dir = root / "Subject" / "markdown"
    subject_dir.mkdir(parents=True)
    document = subject_dir / "test-doc.md"
    document.write_text("Multiple CUSTOMWORDs are sufficient.", encoding="utf-8")

    # Create match for "CUSTOMWORDs" (plural with lowercase 's' - treated as acronym)
    customwords_match = DummyMatch()
    customwords_match.matchedText = "CUSTOMWORDs"

    tool = DummyTool([customwords_match])
    report_path = root / "report.md"
    
    # Only the singular "CUSTOMWORD" is in the ignored words list
    # The plural "CUSTOMWORDs" should still be filtered due to plural-stripping logic
    # (The code checks: "CUSTOMWORD" in list OR "CUSTOMWORDs".rstrip("s") = "CUSTOMWORD" in list)
    run_language_checks(
        root,
        report_path=report_path,
        tool=tool,
        ignored_words={"CUSTOMWORD"},
    )

    report_text = report_path.read_text(encoding="utf-8")
    assert "Total issues found: 0" in report_text


def test_case_sensitive_with_explicit_ignored_words(tmp_path: Path) -> None:
    """Test that explicitly passed ignored_words merge with defaults (case-sensitive)."""
    root = tmp_path
    subject_dir = root / "Subject" / "markdown"
    subject_dir.mkdir(parents=True)
    document = subject_dir / "test-doc.md"
    document.write_text("CustomWord and WJEC appear here.", encoding="utf-8")

    # Create matches
    custom_match = DummyMatch()
    custom_match.matchedText = "CustomWord"
    
    wjec_match = DummyMatch()
    wjec_match.matchedText = "WJEC"

    tool = DummyTool([custom_match, wjec_match])
    report_path = root / "report.md"
    
    # Pass "CustomWord" as an additional ignored word (case-sensitive)
    # WJEC should be filtered from DEFAULT_IGNORED_WORDS
    # CustomWord should be filtered from the explicit list
    run_language_checks(
        root,
        report_path=report_path,
        tool=tool,
        ignored_words={"CustomWord"},
    )

    report_text = report_path.read_text(encoding="utf-8")
    assert "Total issues found: 0" in report_text
    
    
def test_case_sensitive_explicit_wrong_case_not_filtered(tmp_path: Path) -> None:
    """Test that wrong case in explicit ignored_words doesn't filter the match."""
    root = tmp_path
    subject_dir = root / "Subject" / "markdown"
    subject_dir.mkdir(parents=True)
    document = subject_dir / "test-doc.md"
    document.write_text("CustomWord appears here.", encoding="utf-8")

    # Create match for "CustomWord" (mixed case)
    custom_match = DummyMatch()
    custom_match.matchedText = "CustomWord"

    tool = DummyTool([custom_match])
    report_path = root / "report.md"
    
    
    # Pass "customword" (all lowercase) - should NOT match "CustomWord"
    run_language_checks(
        root,
        report_path=report_path,
        tool=tool,
        ignored_words={"customword"},  # Wrong case!
    )

    report_text = report_path.read_text(encoding="utf-8")
    # Issue should still be present (not filtered due to case mismatch)
    assert "Total issues found: 1" in report_text


def test_page_number_extraction_basic(tmp_path: Path) -> None:
    """Test that page numbers are correctly extracted from page markers."""
    root = tmp_path
    subject_dir = root / "Subject" / "markdown"
    subject_dir.mkdir(parents=True)
    document = subject_dir / "test-doc.md"
    
    # Document with page markers
    content = """# Test Document

{0}------------------------------------------------

This is content on page 0.
Thiss is a spelling mistake.

{1}------------------------------------------------

Content on page 1 starts here.
Another errror here.
"""
    document.write_text(content, encoding="utf-8")

    # Create matches at different positions
    match1 = DummyMatch()
    match1.message = "Spelling mistake 1"
    match1.context = "Thiss is a spelling mistake."
    
    match2 = DummyMatch()
    match2.message = "Spelling mistake 2"
    match2.context = "Another errror here."

    tool = DummyTool([match1, match2])

    report = check_single_document(document, tool=tool)

    # Both issues should have page numbers extracted
    assert len(report.issues) == 2
    assert report.issues[0].page_number == 0
    assert report.issues[1].page_number == 1


def test_page_number_in_csv_report(tmp_path: Path) -> None:
    """Test that page numbers appear in CSV report."""
    root = tmp_path
    subject_dir = root / "Subject" / "markdown"
    subject_dir.mkdir(parents=True)
    document = subject_dir / "test-doc.md"
    
    content = """{0}------------------------------------------------

Thiss is a test.

{1}------------------------------------------------

Another errror.
"""
    document.write_text(content, encoding="utf-8")

    match1 = DummyMatch()
    match1.context = "Thiss is a test."
    
    match2 = DummyMatch()
    match2.context = "Another errror."

    tool = DummyTool([match1, match2])

    report_path = root / "report.md"
    run_language_checks(root, report_path=report_path, tool=tool)

    # Check CSV includes page number column
    csv_path = root / "report.csv"
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Header should include Page column
    assert "Page" in rows[0]
    page_col_idx = rows[0].index("Page")
    
    # Data rows should have page numbers
    assert len(rows) == 3  # header + 2 issues
    assert rows[1][page_col_idx] == "0"
    assert rows[2][page_col_idx] == "1"


def test_page_number_in_markdown_report(tmp_path: Path) -> None:
    """Test that page numbers appear in Markdown report."""
    root = tmp_path
    subject_dir = root / "Subject" / "markdown"
    subject_dir.mkdir(parents=True)
    document = subject_dir / "test-doc.md"
    
    content = """{0}------------------------------------------------

Thiss is a test.

{1}------------------------------------------------

Another errror.
"""
    document.write_text(content, encoding="utf-8")

    match1 = DummyMatch()
    match1.context = "Thiss is a test."
    
    match2 = DummyMatch()
    match2.context = "Another errror."

    tool = DummyTool([match1, match2])

    report_path = root / "report.md"
    run_language_checks(root, report_path=report_path, tool=tool)

    report_text = report_path.read_text(encoding="utf-8")
    
    # Markdown table should include Page column
    assert "| Page |" in report_text or "Page" in report_text


def test_page_number_no_markers(tmp_path: Path) -> None:
    """Test that documents without page markers have None or empty page number."""
    root = tmp_path
    subject_dir = root / "Subject" / "markdown"
    subject_dir.mkdir(parents=True)
    document = subject_dir / "test-doc.md"
    
    # Document without page markers
    document.write_text("Thiss is a test without page markers.", encoding="utf-8")

    match = DummyMatch()
    match.context = "Thiss is a test without page markers."

    tool = DummyTool([match])

    report = check_single_document(document, tool=tool)

    assert len(report.issues) == 1
    # Should have None or some default value
    assert report.issues[0].page_number is None


def test_page_number_with_real_document(tmp_path: Path) -> None:
    """Test page number extraction with a copy of real document structure."""
    root = tmp_path
    subject_dir = root / "Business" / "markdown"
    subject_dir.mkdir(parents=True)
    
    # Copy the real document structure
    source_doc = Path("/home/hamish/GitProjects/WjecDocumentScraper/Documents/Business/markdown/gcse-business---delivery-guide.md")
    if source_doc.exists():
        dest_doc = subject_dir / "gcse-business---delivery-guide.md"
        dest_doc.write_text(source_doc.read_text(encoding="utf-8"), encoding="utf-8")
        
        # Create a match that would appear somewhere in the document
        match = DummyMatch()
        match.context = "some context from the document"
        
        tool = DummyTool([match])
        
        report = check_single_document(dest_doc, tool=tool)
        
        # Just verify we can process it without errors
        assert report is not None
        if report.issues:
            # Page number should be an integer or None
            assert isinstance(report.issues[0].page_number, (int, type(None)))


def test_page_number_extraction_with_real_business_doc(tmp_path: Path) -> None:
    """Test that we correctly extract page numbers from the real Business delivery guide."""
    root = tmp_path
    subject_dir = root / "Business" / "markdown"
    subject_dir.mkdir(parents=True)
    
    # Create a simplified version of the document with known page markers and content
    content = """{0}------------------------------------------------

# Title Page

Some content on page 0.
The qualifications are approved.

{1}------------------------------------------------

# Contents Page

Content listing on page 1.

{2}------------------------------------------------

## Introduction

This is page 2 content.
Thiss is a deliberate spelling mistake on page 2.

{3}------------------------------------------------

## More Details

Content on page 3.
Another errror deliberately on page 3.
"""
    
    dest_doc = subject_dir / "test-business-guide.md"
    dest_doc.write_text(content, encoding="utf-8")
    
    # Create matches for the deliberate errors
    match1 = DummyMatch()
    match1.message = "Spelling mistake: Thiss"
    match1.context = "Thiss is a deliberate spelling mistake on page 2."
    match1.matchedText = "Thiss"
    
    match2 = DummyMatch()
    match2.message = "Spelling mistake: errror"
    match2.context = "Another errror deliberately on page 3."
    match2.matchedText = "errror"
    
    tool = DummyTool([match1, match2])
    
    report = check_single_document(dest_doc, tool=tool)
    
    # Verify page numbers are correctly assigned
    assert len(report.issues) == 2
    assert report.issues[0].page_number == 2
    assert report.issues[1].page_number == 3




