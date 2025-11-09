"""Tests for page_utils module."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from page_utils import (
    PageMarker,
    build_page_number_map,
    extract_page_text,
    extract_pages_text,
    find_page_markers,
    get_page_number_at_position,
)


# Simple test document with known structure
SIMPLE_DOC = """{0}------------------------------------------------

This is page 0.
First page of the document.

{1}------------------------------------------------

This is page 1.
Second page content.

{2}------------------------------------------------

This is page 2.
Final page.
"""


def test_find_page_markers_simple() -> None:
    """Test finding page markers in a simple document."""
    markers = find_page_markers(SIMPLE_DOC)
    
    assert len(markers) == 3
    assert markers[0].page_number == 0
    assert markers[1].page_number == 1
    assert markers[2].page_number == 2
    
    # Verify they are sorted by position
    assert markers[0].position < markers[1].position < markers[2].position


def test_find_page_markers_empty() -> None:
    """Test finding page markers in empty text."""
    markers = find_page_markers("")
    assert len(markers) == 0


def test_find_page_markers_no_markers() -> None:
    """Test finding page markers when none exist."""
    text = "This is a document without page markers."
    markers = find_page_markers(text)
    assert len(markers) == 0


def test_find_page_markers_non_sequential() -> None:
    """Test finding page markers that aren't sequential."""
    text = """{5}------------------------------------------------
Content
{10}------------------------------------------------
More content
{2}------------------------------------------------
Even more
"""
    markers = find_page_markers(text)
    
    assert len(markers) == 3
    # Should be sorted by position in text, not by page number
    assert markers[0].page_number == 5
    assert markers[1].page_number == 10
    assert markers[2].page_number == 2


def test_build_page_number_map_simple() -> None:
    """Test building page number map from simple document."""
    page_map = build_page_number_map(SIMPLE_DOC)
    
    # Should have entries for all positions
    assert len(page_map) > 0
    
    # Find positions in different pages
    page0_pos = SIMPLE_DOC.find("This is page 0")
    page1_pos = SIMPLE_DOC.find("This is page 1")
    page2_pos = SIMPLE_DOC.find("This is page 2")
    
    assert page_map[page0_pos] == 0
    assert page_map[page1_pos] == 1
    assert page_map[page2_pos] == 2


def test_build_page_number_map_empty() -> None:
    """Test building page number map from empty text."""
    page_map = build_page_number_map("")
    assert len(page_map) == 0


def test_build_page_number_map_no_markers() -> None:
    """Test building page number map when no markers exist."""
    text = "This is a document without page markers."
    page_map = build_page_number_map(text)
    assert len(page_map) == 0


def test_get_page_number_at_position() -> None:
    """Test getting page number at specific positions."""
    page_map = build_page_number_map(SIMPLE_DOC)
    
    page1_pos = SIMPLE_DOC.find("Second page content")
    page_num = get_page_number_at_position(page1_pos, page_map)
    assert page_num == 1


def test_get_page_number_at_position_not_found() -> None:
    """Test getting page number at position not in map."""
    page_map = build_page_number_map(SIMPLE_DOC)
    
    # Position before any page marker
    page_num = get_page_number_at_position(0, page_map)
    assert page_num is None or page_num == 0  # Depends on implementation


def test_extract_page_text_single_page() -> None:
    """Test extracting text from a single page."""
    result = extract_page_text(SIMPLE_DOC, page_number=1)
    
    # Should include the page marker
    assert "{1}------------------------------------------------" in result
    assert "This is page 1" in result
    assert "Second page content" in result
    
    # Should not include other pages
    assert "This is page 0" not in result
    assert "This is page 2" not in result


def test_extract_page_text_first_page() -> None:
    """Test extracting the first page."""
    result = extract_page_text(SIMPLE_DOC, page_number=0)
    
    assert "{0}------------------------------------------------" in result
    assert "This is page 0" in result
    assert "First page of the document" in result
    
    # Should not include page 1
    assert "{1}------------------------------------------------" not in result


def test_extract_page_text_last_page() -> None:
    """Test extracting the last page."""
    result = extract_page_text(SIMPLE_DOC, page_number=2)
    
    assert "{2}------------------------------------------------" in result
    assert "This is page 2" in result
    assert "Final page" in result


def test_extract_page_text_range() -> None:
    """Test extracting a range of pages."""
    result = extract_page_text(SIMPLE_DOC, start_page=0, end_page=1)
    
    # Should include both pages
    assert "{0}------------------------------------------------" in result
    assert "{1}------------------------------------------------" in result
    assert "This is page 0" in result
    assert "This is page 1" in result
    
    # Should not include page 2
    assert "This is page 2" not in result


def test_extract_page_text_range_all_pages() -> None:
    """Test extracting all pages as a range."""
    result = extract_page_text(SIMPLE_DOC, start_page=0, end_page=2)
    
    # Should include all pages
    assert "{0}------------------------------------------------" in result
    assert "{1}------------------------------------------------" in result
    assert "{2}------------------------------------------------" in result
    assert "This is page 0" in result
    assert "This is page 1" in result
    assert "This is page 2" in result


def test_extract_page_text_page_not_found() -> None:
    """Test extracting a page that doesn't exist."""
    result = extract_page_text(SIMPLE_DOC, page_number=99)
    
    # Should return empty string
    assert result == ""


def test_extract_page_text_invalid_arguments() -> None:
    """Test extract_page_text with invalid argument combinations."""
    # Both page_number and start_page
    with pytest.raises(ValueError):
        extract_page_text(SIMPLE_DOC, page_number=1, start_page=0, end_page=2)
    
    # Only start_page
    with pytest.raises(ValueError):
        extract_page_text(SIMPLE_DOC, start_page=0)
    
    # Only end_page
    with pytest.raises(ValueError):
        extract_page_text(SIMPLE_DOC, end_page=2)
    
    # Neither page_number nor range
    with pytest.raises(ValueError):
        extract_page_text(SIMPLE_DOC)


def test_extract_pages_text_multiple() -> None:
    """Test extracting multiple specific pages."""
    result = extract_pages_text(SIMPLE_DOC, [0, 2])
    
    assert len(result) == 2
    assert 0 in result
    assert 2 in result
    assert 1 not in result
    
    assert "{0}------------------------------------------------" in result[0]
    assert "This is page 0" in result[0]
    
    assert "{2}------------------------------------------------" in result[2]
    assert "This is page 2" in result[2]


def test_extract_pages_text_all() -> None:
    """Test extracting all pages individually."""
    result = extract_pages_text(SIMPLE_DOC, [0, 1, 2])
    
    assert len(result) == 3
    assert all(page in result for page in [0, 1, 2])
    
    for page_num in [0, 1, 2]:
        assert f"{{" + f"{page_num}" + "}" in result[page_num]
        assert f"This is page {page_num}" in result[page_num]


def test_extract_pages_text_some_not_found() -> None:
    """Test extracting pages where some don't exist."""
    result = extract_pages_text(SIMPLE_DOC, [0, 99, 1, 100])
    
    # Should only include pages that exist
    assert len(result) == 2
    assert 0 in result
    assert 1 in result
    assert 99 not in result
    assert 100 not in result


def test_extract_pages_text_empty_list() -> None:
    """Test extracting with empty page list."""
    result = extract_pages_text(SIMPLE_DOC, [])
    
    assert len(result) == 0
    assert result == {}


def test_real_document_structure() -> None:
    """Test with the real Business unit 1 teacher guidance document."""
    # Load the test fixture
    fixture_path = Path(__file__).parent / "fixtures" / "gcse-business---guidance-for-teaching-unit-1.md"
    
    if not fixture_path.exists():
        pytest.skip("Test fixture not found")
    
    text = fixture_path.read_text(encoding="utf-8")
    
    # Find markers
    markers = find_page_markers(text)
    
    # Should have multiple pages
    assert len(markers) > 0
    
    # First page should be 0
    assert markers[0].page_number == 0
    
    # Test extracting a specific page
    page_3_text = extract_page_text(text, page_number=3)
    assert page_3_text != ""
    assert "{3}------------------------------------------------" in page_3_text


def test_real_document_page_content() -> None:
    """Test extracting specific content from real document."""
    fixture_path = Path(__file__).parent / "fixtures" / "gcse-business---guidance-for-teaching-unit-1.md"
    
    if not fixture_path.exists():
        pytest.skip("Test fixture not found")
    
    text = fixture_path.read_text(encoding="utf-8")
    
    # Extract page 2 which contains the table of contents
    page_2_text = extract_page_text(text, page_number=2)
    
    # Verify it includes expected content
    assert "Contents" in page_2_text or "contents" in page_2_text.lower()
    assert "{2}------------------------------------------------" in page_2_text


def test_real_document_page_range() -> None:
    """Test extracting a page range from real document."""
    fixture_path = Path(__file__).parent / "fixtures" / "gcse-business---guidance-for-teaching-unit-1.md"
    
    if not fixture_path.exists():
        pytest.skip("Test fixture not found")
    
    text = fixture_path.read_text(encoding="utf-8")
    
    # Extract pages 0-2 (cover and table of contents)
    pages_text = extract_page_text(text, start_page=0, end_page=2)
    
    # Should include all three page markers
    assert "{0}------------------------------------------------" in pages_text
    assert "{1}------------------------------------------------" in pages_text
    assert "{2}------------------------------------------------" in pages_text
    
    # Should not include page 3
    assert "{3}------------------------------------------------" not in pages_text


def test_real_document_multiple_pages() -> None:
    """Test extracting multiple non-consecutive pages from real document."""
    fixture_path = Path(__file__).parent / "fixtures" / "gcse-business---guidance-for-teaching-unit-1.md"
    
    if not fixture_path.exists():
        pytest.skip("Test fixture not found")
    
    text = fixture_path.read_text(encoding="utf-8")
    
    # Extract non-consecutive pages
    pages = extract_pages_text(text, [0, 3, 5])
    
    # Should get all requested pages that exist
    assert 0 in pages
    assert len(pages) >= 1  # At least page 0 should exist
    
    # Each page should have its marker
    for page_num, page_text in pages.items():
        assert f"{{{page_num}}}------------------------------------------------" in page_text


def test_page_marker_dataclass() -> None:
    """Test PageMarker dataclass."""
    marker = PageMarker(page_number=5, position=100)
    
    assert marker.page_number == 5
    assert marker.position == 100
    
    # Test equality
    marker2 = PageMarker(page_number=5, position=100)
    assert marker == marker2


def test_find_page_markers_ordering() -> None:
    """Test that page markers are correctly ordered by position."""
    # Create text with markers in non-sequential page order
    text = """{10}----
Content
{5}----
More
{1}----
Final
"""
    
    markers = find_page_markers(text)
    
    # Should be sorted by position in text
    assert len(markers) == 3
    assert markers[0].page_number == 10
    assert markers[1].page_number == 5
    assert markers[2].page_number == 1
    
    # Verify positions are increasing
    assert markers[0].position < markers[1].position < markers[2].position
