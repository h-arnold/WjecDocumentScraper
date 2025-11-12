"""Tests for multi-language support in language checking.

This module tests the ability to check documents with multiple language
dictionaries simultaneously, particularly for French and German subjects.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.language_check import (
    check_single_document,
    get_languages_for_subject,
    build_language_tools_for_subject,
)


def test_get_languages_for_subject_french() -> None:
    """Test that French subject returns both French and English."""
    languages = get_languages_for_subject("French")
    assert languages == ["fr", "en-GB"]


def test_get_languages_for_subject_german() -> None:
    """Test that German subject returns both German and English."""
    languages = get_languages_for_subject("German")
    assert languages == ["de", "en-GB"]


def test_get_languages_for_subject_other() -> None:
    """Test that non-language subjects return only English."""
    # Test various subject names
    for subject in ["Computer-Science", "Mathematics", "History", "Art-and-Design"]:
        languages = get_languages_for_subject(subject)
        assert languages == ["en-GB"], f"Subject {subject} should only use English"


def test_get_languages_for_subject_case_sensitive() -> None:
    """Test that subject name matching is case-sensitive."""
    # Lowercase should not match
    languages = get_languages_for_subject("french")
    assert languages == ["en-GB"]
    
    languages = get_languages_for_subject("german")
    assert languages == ["en-GB"]


def test_french_document_integration(tmp_path: Path) -> None:
    """Integration test: Check a French document with actual content.
    
    This test uses a small French markdown file from the Documents folder
    and verifies that the multi-language checking works correctly.
    """
    # Path to a real French document (small one for testing)
    french_docs_path = PROJECT_ROOT / "Documents" / "French" / "markdown"
    
    if not french_docs_path.exists():
        # Skip test if Documents folder doesn't exist (CI environment)
        import pytest
        pytest.skip("French documents not available")
    
    # Find a small French document
    french_files = list(french_docs_path.glob("*.md"))
    if not french_files:
        import pytest
        pytest.skip("No French markdown files found")
    
    # Use the smallest file for faster testing
    test_doc = min(french_files, key=lambda p: p.stat().st_size)
    
    # Run the check with auto-detection of languages
    report = check_single_document(test_doc, subject="French")
    
    # Verify the report was generated
    assert report is not None
    assert report.subject == "French"
    assert report.path == test_doc
    
    # The report should contain issues (we're checking both French and English)
    # We don't assert specific counts as that would be fragile, but we verify
    # the structure is correct
    assert isinstance(report.issues, list)
    
    # Log some info for debugging
    print(f"\nChecked document: {test_doc.name}")
    print(f"Total issues found: {len(report.issues)}")
    if report.issues:
        print(f"Sample issue: {report.issues[0].rule_id} - {report.issues[0].message[:50]}")


def test_french_document_with_french_text(tmp_path: Path) -> None:
    """Test that French text is checked with French language rules.
    
    This test creates a document with French text that should trigger
    French-specific language rules.
    """
    # Skip if we can't access external resources
    import pytest
    pytest.skip("Requires network access to LanguageTool server")
    
    # Create a test document with French content
    subject_dir = tmp_path / "French" / "markdown"
    subject_dir.mkdir(parents=True)
    test_doc = subject_dir / "test-french.md"
    
    # French text with intentional errors
    french_content = """
# Test Document

Voici un texte en français.

Je veux acheter un billet pour le concert.

Il y a une erreur ici: "Je vais à le magasin" (should be "au magasin").

Some English text that should also be checked.
This sentance has a spelling error.
"""
    test_doc.write_text(french_content, encoding="utf-8")
    
    # Check the document
    report = check_single_document(test_doc, subject="French")
    
    # Verify we got issues from both French and English checking
    assert len(report.issues) > 0
    
    # Check that we have issues from both French and English rules
    rule_ids = {issue.rule_id for issue in report.issues}
    print(f"\nRule IDs found: {rule_ids}")
    
    # We should have at least some French and English specific rules
    # (specific rules may vary based on LanguageTool version)


def test_build_language_tools_for_french() -> None:
    """Test that building tools for French creates two tools."""
    import pytest
    pytest.skip("Requires network access to LanguageTool server")
    
    tools = build_language_tools_for_subject("French")
    
    # Should create tools for French and English
    assert len(tools) == 2
    
    # Verify the languages (order: French first, then English)
    assert tools[0].language == "fr"
    assert tools[1].language == "en-GB"
    
    # Clean up
    for tool in tools:
        if hasattr(tool, "close"):
            tool.close()


def test_build_language_tools_for_other_subject() -> None:
    """Test that building tools for non-language subjects creates one tool."""
    import pytest
    pytest.skip("Requires network access to LanguageTool server")
    
    tools = build_language_tools_for_subject("Computer-Science")
    
    # Should create only English tool
    assert len(tools) == 1
    assert tools[0].language == "en-GB"
    
    # Clean up
    for tool in tools:
        if hasattr(tool, "close"):
            tool.close()


def test_backward_compatibility_with_single_tool(tmp_path: Path) -> None:
    """Test that providing a single tool still works (backward compatibility)."""
    from tests.test_language_check import DummyTool, DummyMatch
    
    # Create a test document
    subject_dir = tmp_path / "French" / "markdown"
    subject_dir.mkdir(parents=True)
    test_doc = subject_dir / "test.md"
    test_doc.write_text("Test content.", encoding="utf-8")
    
    # Create a dummy tool
    match = DummyMatch()
    tool = DummyTool([match])
    
    # Check with explicit tool (should bypass multi-language logic)
    report = check_single_document(test_doc, subject="French", tool=tool)
    
    # Should work as before
    assert report.subject == "French"
    assert len(report.issues) == 1
    assert tool.captured_text == "Test content."
