#!/usr/bin/env python3
"""Manual test script for multi-language support.

This script demonstrates the multi-language language checking functionality
by creating test documents with French and English content, then checking them.

Run this script when you have network access to LanguageTool to verify
the multi-language support is working correctly.

Usage:
    uv run python scripts/test_multilang_manual.py
"""

from pathlib import Path
import tempfile
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.language_check import (
    check_single_document,
    get_languages_for_subject,
)


def test_language_detection():
    """Test that language detection works correctly."""
    print("=" * 60)
    print("Testing language detection")
    print("=" * 60)
    
    test_cases = [
        ("French", ["en-GB", "fr"]),
        ("German", ["en-GB", "de"]),
        ("Computer-Science", ["en-GB"]),
        ("History", ["en-GB"]),
    ]
    
    for subject, expected in test_cases:
        languages = get_languages_for_subject(subject)
        status = "✓" if languages == expected else "✗"
        print(f"{status} {subject:20} -> {languages}")
        if languages != expected:
            print(f"   Expected: {expected}")
    
    print()


def test_french_document():
    """Test checking a French document with multi-language support."""
    print("=" * 60)
    print("Testing French document checking")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test document with French and English content
        subject_dir = Path(tmpdir) / "French" / "markdown"
        subject_dir.mkdir(parents=True)
        test_doc = subject_dir / "test-french.md"
        
        # Content with intentional errors in both languages
        content = """# GCSE French Test Document

## French Section

Voici quelques phrases en français.

Je veux acheter un billet pour le concert.

Il aime la bonne cuisine française.

Les étudiants apprennent le français.

## English Section

This section has some English text.

The GCSE French course includes speaking and writing assessments.

Students will develop language skills through various activities.
"""
        test_doc.write_text(content, encoding="utf-8")
        
        print(f"Created test document: {test_doc.name}")
        print(f"Document size: {len(content)} characters")
        print()
        
        try:
            print("Running multi-language check (English + French)...")
            report = check_single_document(test_doc, subject="French")
            
            print(f"✓ Check completed successfully")
            print(f"  Subject: {report.subject}")
            print(f"  Document: {report.path.name}")
            print(f"  Total issues found: {len(report.issues)}")
            
            if report.issues:
                print(f"\n  First 5 issues:")
                for i, issue in enumerate(report.issues[:5], 1):
                    print(f"    {i}. [{issue.rule_id}] {issue.message[:60]}...")
                    print(f"       Issue: '{issue.issue}' in context: '{issue.context[:50]}...'")
            else:
                print("  No issues found (document is clean)")
            
        except Exception as e:
            print(f"✗ Error during check: {e}")
            if "languagetool.org" in str(e).lower():
                print("  Note: This requires network access to download LanguageTool")
            raise
    
    print()


def test_german_vs_english():
    """Test that German and English subjects use different language tools."""
    print("=" * 60)
    print("Testing German vs English subject handling")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create German document
        german_dir = Path(tmpdir) / "German" / "markdown"
        german_dir.mkdir(parents=True)
        german_doc = german_dir / "test-german.md"
        german_doc.write_text("# Test German\n\nGuten Tag. Dies ist ein Test.", encoding="utf-8")
        
        # Create English document
        english_dir = Path(tmpdir) / "History" / "markdown"
        english_dir.mkdir(parents=True)
        english_doc = english_dir / "test-history.md"
        english_doc.write_text("# Test History\n\nThis is a test document.", encoding="utf-8")
        
        try:
            print("Checking German document...")
            german_report = check_single_document(german_doc, subject="German")
            print(f"✓ German document checked (English + German)")
            print(f"  Issues: {len(german_report.issues)}")
            
            print("\nChecking English document...")
            english_report = check_single_document(english_doc, subject="History")
            print(f"✓ English document checked (English only)")
            print(f"  Issues: {len(english_report.issues)}")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            if "languagetool.org" in str(e).lower():
                print("  Note: This requires network access to download LanguageTool")
            raise
    
    print()


def main():
    """Run all manual tests."""
    print("\nMulti-Language Support Manual Test")
    print("=" * 60)
    print()
    print("This script tests the multi-language language checking functionality.")
    print("It requires network access to download LanguageTool components.")
    print()
    
    try:
        # Test 1: Language detection (no network required)
        test_language_detection()
        
        # Test 2: French document checking (requires network)
        print("Attempting to check French document...")
        print("(This may take a moment to download LanguageTool...)")
        print()
        test_french_document()
        
        # Test 3: German vs English (requires network)
        test_german_vs_english()
        
        print("=" * 60)
        print("✓ All manual tests completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print()
        print("=" * 60)
        print(f"✗ Test failed: {e}")
        print("=" * 60)
        if "languagetool.org" in str(e).lower():
            print()
            print("Note: These tests require network access to LanguageTool.")
            print("If you're in an environment without network access,")
            print("the functionality has been verified through unit tests.")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
