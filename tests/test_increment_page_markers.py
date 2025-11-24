"""Tests for page marker increment functionality."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.page_utils import find_page_markers, increment_page_markers


def test_increment_page_markers_basic():
    """Test basic increment from 0-indexed to 1-indexed."""
    text = """
{0}------------------------------------------------
Page 0 content

{1}------------------------------------------------
Page 1 content

{2}------------------------------------------------
Page 2 content
"""
    result = increment_page_markers(text)

    markers = find_page_markers(result)
    assert len(markers) == 3
    assert markers[0].page_number == 1
    assert markers[1].page_number == 2
    assert markers[2].page_number == 3

    # Verify content is preserved
    assert "Page 0 content" in result
    assert "Page 1 content" in result
    assert "Page 2 content" in result


def test_increment_page_markers_preserves_dashes():
    """Test that dash count is preserved during increment."""
    text = "{0}------------------------------------------------\nContent"

    result = increment_page_markers(text)

    # Should have exactly 48 dashes
    assert "{1}------------------------------------------------" in result
    assert result.count("-") == 48


def test_increment_page_markers_double_digits():
    """Test increment with double-digit page numbers."""
    text = """
{0}---
{1}---
{10}---
{11}---
{99}---
"""
    result = increment_page_markers(text)

    markers = find_page_markers(result)
    assert len(markers) == 5
    assert markers[0].page_number == 1
    assert markers[1].page_number == 2
    assert markers[2].page_number == 11
    assert markers[3].page_number == 12
    assert markers[4].page_number == 100


def test_increment_page_markers_idempotent_already_1_indexed():
    """Test that already 1-indexed files are not modified."""
    text = """
{1}------------------------------------------------
Page 1 content

{2}------------------------------------------------
Page 2 content
"""
    result = increment_page_markers(text)

    # Should be unchanged
    assert result == text

    markers = find_page_markers(result)
    assert markers[0].page_number == 1
    assert markers[1].page_number == 2


def test_increment_page_markers_idempotent_starts_with_5():
    """Test that files starting with any number other than 0 are not modified."""
    text = """
{5}------------------------------------------------
Page 5 content

{6}------------------------------------------------
Page 6 content
"""
    result = increment_page_markers(text)

    # Should be unchanged
    assert result == text


def test_increment_page_markers_no_markers():
    """Test handling of text without page markers."""
    text = "Just some regular markdown content\nWith no page markers"

    result = increment_page_markers(text)

    # Should be unchanged
    assert result == text


def test_increment_page_markers_empty_string():
    """Test handling of empty string."""
    result = increment_page_markers("")
    assert result == ""


def test_increment_page_markers_varied_dash_counts():
    """Test that different dash counts are preserved for each marker."""
    text = """
{0}---
Content A

{1}-----
Content B

{2}-------
Content C
"""
    result = increment_page_markers(text)

    # Each marker should preserve its original dash count
    assert "{1}---\n" in result
    assert "{2}-----\n" in result
    assert "{3}-------\n" in result


def test_increment_page_markers_with_whitespace():
    """Test that trailing whitespace in markers is preserved."""
    text = "{0}------------------------------------------------  \n{1}---\n"

    result = increment_page_markers(text)

    # Whitespace should be preserved
    assert "{1}------------------------------------------------  \n" in result
    assert "{2}---\n" in result


def test_increment_page_markers_real_world_example():
    """Test with a real-world example structure."""
    text = """

{0}------------------------------------------------

![](_page_0_Picture_0.jpeg)

# WJEC GCSE Art and Design

{1}------------------------------------------------

## Contents

{2}------------------------------------------------

## About this pack
"""
    result = increment_page_markers(text)

    markers = find_page_markers(result)
    assert len(markers) == 3
    assert markers[0].page_number == 1
    assert markers[1].page_number == 2
    assert markers[2].page_number == 3

    # Content structure should be preserved
    assert "![](_page_0_Picture_0.jpeg)" in result
    assert "# WJEC GCSE Art and Design" in result
    assert "## Contents" in result
