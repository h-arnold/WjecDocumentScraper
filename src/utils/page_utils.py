"""Utilities for working with page numbers and extracting page content.

This module provides functions to work with page markers in Markdown documents
that use the format: {N}------------------------------------------------

Functions:
    - find_page_markers: Find all page markers in text
    - build_page_number_map: Build a map from character position to page number
    - get_page_number_at_position: Get the page number at a specific position
    - extract_page_text: Extract text from a specific page or range of pages
    - increment_page_markers: Convert page markers from 0-indexed to 1-indexed
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

# Page marker pattern: {N}------------------------------------------------
PAGE_MARKER_PATTERN = re.compile(r"^\{(\d+)\}[-]+\s*$", re.MULTILINE)


@dataclass
class PageMarker:
    """Represents a page marker found in text."""

    page_number: int
    position: int  # Character position in text where marker starts


def find_page_markers(text: str) -> list[PageMarker]:
    """Find all page markers in the text.

    Scans for markers in the format {N}------------------------------------------------
    where N is a page number.

    Args:
        text: The document text to scan

    Returns:
        A sorted list of PageMarker objects (sorted by position)

    Example:
        >>> text = "{0}----\\nPage 0 content\\n{1}----\\nPage 1 content"
        >>> markers = find_page_markers(text)
        >>> len(markers)
        2
        >>> markers[0].page_number
        0
    """
    markers: list[PageMarker] = []

    for match in PAGE_MARKER_PATTERN.finditer(text):
        page_num = int(match.group(1))
        position = match.start()
        markers.append(PageMarker(page_number=page_num, position=position))

    # Sort by position to ensure correct ordering
    markers.sort(key=lambda m: m.position)

    return markers


def build_page_number_map(text: str) -> dict[int, int]:
    """Build a map from character position to page number.

    Scans the text for page markers in the format {N}------------------------------------------------
    and creates a mapping where each character position maps to its page number.

    Args:
        text: The document text to scan

    Returns:
        A dictionary mapping character positions to page numbers

    Example:
        >>> text = "{0}----\\nContent\\n{1}----\\nMore"
        >>> page_map = build_page_number_map(text)
        >>> page_map[7]  # Position in "Content"
        0
    """
    markers = find_page_markers(text)

    if not markers:
        # No page markers found
        return {}

    # Build position-to-page map in a single pass
    position_to_page: dict[int, int] = {}

    # For each marker, fill the range from its position up to the next marker (or end of text)
    for idx, marker in enumerate(markers):
        start = marker.position
        end = markers[idx + 1].position if idx + 1 < len(markers) else len(text)
        for i in range(start, end):
            position_to_page[i] = marker.page_number

    return position_to_page


def get_page_number_at_position(position: int, page_map: dict[int, int]) -> int | None:
    """Get the page number at a specific character position.

    Args:
        position: Character position in the text
        page_map: Map from character position to page number (from build_page_number_map)

    Returns:
        The page number at the position, or None if not found
    """
    return page_map.get(position)


def extract_page_text(
    text: str,
    page_number: int | None = None,
    start_page: int | None = None,
    end_page: int | None = None,
) -> str:
    """Extract text from a specific page or range of pages.

    The extracted text will include the page markers themselves.

    Args:
        text: The document text to extract from
        page_number: Extract a single page (mutually exclusive with start_page/end_page)
        start_page: Start of page range (inclusive, use with end_page)
        end_page: End of page range (inclusive, use with start_page)

    Returns:
        The extracted text including page markers, or empty string if pages not found

    Raises:
        ValueError: If arguments are invalid (e.g., both page_number and start_page provided)

    Example:
        >>> text = "{0}----\\nPage 0\\n{1}----\\nPage 1\\n{2}----\\nPage 2"
        >>> extract_page_text(text, page_number=1)
        '{1}----\\nPage 1\\n'
        >>> extract_page_text(text, start_page=0, end_page=1)
        '{0}----\\nPage 0\\n{1}----\\nPage 1\\n'
    """
    # Validate arguments
    if page_number is not None and (start_page is not None or end_page is not None):
        raise ValueError("Cannot specify both page_number and start_page/end_page")

    if (start_page is not None) != (end_page is not None):
        raise ValueError("Must specify both start_page and end_page together")

    if page_number is None and start_page is None:
        raise ValueError("Must specify either page_number or start_page/end_page")

    # Convert single page to range
    if page_number is not None:
        start_page = page_number
        end_page = page_number

    # Find all page markers
    markers = find_page_markers(text)

    if not markers:
        return ""

    # Find markers for requested pages
    start_marker = None
    end_marker = None

    for marker in markers:
        if marker.page_number == start_page:
            start_marker = marker
        if marker.page_number == end_page:
            end_marker = marker

    if start_marker is None:
        return ""

    # Determine start position
    start_pos = start_marker.position

    # Determine end position
    if end_marker is None:
        # Requested end page not found
        return ""

    # Find the next marker after end_marker to know where to stop
    next_marker_pos = len(text)  # Default to end of text
    for marker in markers:
        if marker.position > end_marker.position:
            next_marker_pos = marker.position
            break

    # Extract the text from start_pos to next_marker_pos
    return text[start_pos:next_marker_pos]


def extract_pages_text(text: str, page_numbers: Iterable[int]) -> dict[int, str]:
    """Extract text from multiple pages.

    The extracted text for each page will include the page marker.

    Args:
        text: The document text to extract from
        page_numbers: Iterable of page numbers to extract

    Returns:
        A dictionary mapping page numbers to their text content.
        Pages not found will not be in the dictionary.

    Example:
        >>> text = "{0}----\\nPage 0\\n{1}----\\nPage 1\\n{2}----\\nPage 2"
        >>> pages = extract_pages_text(text, [0, 2])
        >>> pages[0]
        '{0}----\\nPage 0\\n'
        >>> pages[2]
        '{2}----\\nPage 2'
    """
    result: dict[int, str] = {}

    for page_num in page_numbers:
        try:
            page_text = extract_page_text(text, page_number=page_num)
            if page_text:
                result[page_num] = page_text
        except ValueError:
            # Skip invalid page numbers
            continue

    return result


def increment_page_markers(text: str) -> str:
    """Increment all page markers from 0-indexed to 1-indexed.

    Converts page markers in the format {N}---- to {N+1}----, preserving
    the exact number of dashes. This is idempotent - if the first marker
    is not {0}, the text is returned unchanged.

    Args:
        text: The markdown text containing page markers

    Returns:
        The text with all page markers incremented by 1, or original text
        if already 1-indexed

    Example:
        >>> text = "{0}----\\nPage 0\\n{1}----\\nPage 1"
        >>> increment_page_markers(text)
        '{1}----\\nPage 0\\n{2}----\\nPage 1'
        >>> increment_page_markers("{1}----\\nAlready 1-indexed")
        '{1}----\\nAlready 1-indexed'
    """
    markers = find_page_markers(text)

    if not markers:
        # No markers found, return unchanged
        return text

    # Check if first marker is {0} - if not, assume already 1-indexed
    if markers[0].page_number != 0:
        return text

    # Build list of (page_number, match_object) tuples for all markers
    marker_matches: list[tuple[int, re.Match[str]]] = []
    for match in PAGE_MARKER_PATTERN.finditer(text):
        page_num = int(match.group(1))
        marker_matches.append((page_num, match))

    # Sort by page number in descending order to avoid double-incrementing
    # (we want to replace {10} before {1} so we don't accidentally change {1} to {2}
    # and then {10} to {11} when we later encounter the original {10})
    marker_matches.sort(key=lambda x: x[0], reverse=True)

    # Replace each marker, working backwards
    result = text
    for page_num, match in marker_matches:
        old_marker = match.group(0)
        # Preserve the exact dash count and whitespace
        dashes = match.group(0)[len(f"{{{page_num}}}") :]
        new_marker = f"{{{page_num + 1}}}{dashes}"
        result = result.replace(old_marker, new_marker, 1)

    return result
