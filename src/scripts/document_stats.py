#!/usr/bin/env python3
"""
Script to generate statistics about documents in the Documents folder.

Counts:
- Number of PDF documents per subject
- Number of converted markdown documents per subject
- Total pages per subject (from page markers in markdown)
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.page_utils import find_page_markers


def count_pdfs(subject_dir: Path) -> int:
    """Count PDF documents in the subject's pdfs directory.

    Args:
        subject_dir: Path to the subject directory

    Returns:
        Number of PDF files found
    """
    pdf_dir = subject_dir / "pdfs"
    if not pdf_dir.exists():
        return 0

    return len(list(pdf_dir.glob("*.pdf")))


def count_markdown_files(subject_dir: Path) -> int:
    """Count markdown documents in the subject's markdown directory.

    Args:
        subject_dir: Path to the subject directory

    Returns:
        Number of markdown files found
    """
    markdown_dir = subject_dir / "markdown"
    if not markdown_dir.exists():
        return 0

    return len(list(markdown_dir.glob("*.md")))


def count_total_pages(subject_dir: Path) -> int:
    """Count total pages across all markdown documents in the subject.

    For each markdown document, finds the last page marker {N}----
    If there's no page marker (page 0 only), counts as 1 page.

    Args:
        subject_dir: Path to the subject directory

    Returns:
        Total number of pages across all markdown documents
    """
    markdown_dir = subject_dir / "markdown"
    if not markdown_dir.exists():
        return 0

    total_pages = 0

    for md_file in markdown_dir.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            markers = find_page_markers(content)

            if not markers:
                # No page markers means it's a single page document
                total_pages += 1
            else:
                # Get the last page number and add 1 (pages are 0-indexed)
                last_page = max(marker.page_number for marker in markers)
                total_pages += last_page + 1

        except (IOError, OSError, UnicodeDecodeError) as e:
            print(f"Warning: Could not read {md_file.name}: {e}", file=sys.stderr)
            continue

    return total_pages


def get_subject_directories(documents_root: Path) -> list[Path]:
    """Get all subject directories from the Documents folder.

    Args:
        documents_root: Path to the Documents folder

    Returns:
        List of subject directory paths
    """
    if not documents_root.exists():
        return []

    # Get all directories that contain either pdfs or markdown subdirectories
    subjects = []
    for item in documents_root.iterdir():
        if item.is_dir() and ((item / "pdfs").exists() or (item / "markdown").exists()):
            subjects.append(item)

    return sorted(subjects, key=lambda p: p.name)


def main():
    """Main entry point for the script."""
    # Default to Documents folder in the repository
    repo_root = Path(__file__).parent.parent.parent
    documents_root = repo_root / "Documents"

    if not documents_root.exists():
        print(f"Error: Documents folder not found at {documents_root}", file=sys.stderr)
        return 1

    subjects = get_subject_directories(documents_root)

    if not subjects:
        print("No subject directories found in Documents folder", file=sys.stderr)
        return 1

    # Print header
    print(f"{'Subject':<50} {'PDFs':>8} {'Markdown':>10} {'Pages':>8}")
    print("-" * 80)

    # Track totals
    total_pdfs = 0
    total_markdown = 0
    total_pages = 0

    # Process each subject
    for subject_dir in subjects:
        subject_name = subject_dir.name
        pdf_count = count_pdfs(subject_dir)
        markdown_count = count_markdown_files(subject_dir)
        page_count = count_total_pages(subject_dir)

        print(f"{subject_name:<50} {pdf_count:>8} {markdown_count:>10} {page_count:>8}")

        total_pdfs += pdf_count
        total_markdown += markdown_count
        total_pages += page_count

    # Print totals
    print("-" * 80)
    print(f"{'TOTAL':<50} {total_pdfs:>8} {total_markdown:>10} {total_pages:>8}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
