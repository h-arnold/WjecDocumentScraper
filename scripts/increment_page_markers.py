#!/usr/bin/env python3
"""Script to increment page markers in existing markdown files from 0-indexed to 1-indexed.

This script scans the Documents folder for markdown files that start with {0}---
and increments all page markers by 1 to convert from 0-indexed to 1-indexed pagination.

Usage:
    python -m scripts.increment_page_markers [--dry-run] [--documents-dir PATH]

Options:
    --dry-run          Show what would be changed without modifying files
    --documents-dir    Path to Documents folder (default: ./Documents)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.utils.page_utils import find_page_markers, increment_page_markers


def process_markdown_file(
    file_path: Path, *, dry_run: bool = False
) -> tuple[bool, str]:
    """Process a single markdown file.

    Args:
        file_path: Path to the markdown file
        dry_run: If True, don't modify the file

    Returns:
        Tuple of (was_modified, status_message)
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"Error reading: {e}"

    # Check if file has page markers and starts with {0}
    markers = find_page_markers(content)

    if not markers:
        return False, "No page markers found"

    if markers[0].page_number != 0:
        return False, f"Already 1-indexed (starts with {{{markers[0].page_number}}})"

    # Increment the page markers
    new_content = increment_page_markers(content)

    if new_content == content:
        return False, "No changes made (unexpected)"

    # Verify the change worked
    new_markers = find_page_markers(new_content)
    if not new_markers or new_markers[0].page_number != 1:
        return False, "Increment failed (verification error)"

    if dry_run:
        return (
            True,
            f"Would increment {len(markers)} markers ({{0}} → {{1}}, {{1}} → {{2}}, ...)",
        )

    # Write the modified content back
    try:
        file_path.write_text(new_content, encoding="utf-8")
        return (
            True,
            f"Incremented {len(markers)} markers ({{0}} → {{1}}, {{1}} → {{2}}, ...)",
        )
    except Exception as e:
        return False, f"Error writing: {e}"


def process_documents_folder(
    documents_dir: Path, *, dry_run: bool = False
) -> dict[str, int]:
    """Process all markdown files in the Documents folder.

    Args:
        documents_dir: Path to the Documents folder
        dry_run: If True, don't modify files

    Returns:
        Dictionary with processing statistics
    """
    stats = {
        "total": 0,
        "modified": 0,
        "skipped": 0,
        "errors": 0,
    }

    # Find all markdown files
    markdown_files = list(documents_dir.rglob("*.md"))

    if not markdown_files:
        print(f"No markdown files found in {documents_dir}")
        return stats

    print(f"Found {len(markdown_files)} markdown files")
    print()

    for md_file in sorted(markdown_files):
        stats["total"] += 1
        relative_path = md_file.relative_to(documents_dir)

        was_modified, message = process_markdown_file(md_file, dry_run=dry_run)

        if was_modified:
            stats["modified"] += 1
            prefix = "✓ [DRY RUN]" if dry_run else "✓"
            print(f"{prefix} {relative_path}: {message}")
        else:
            if "Error" in message:
                stats["errors"] += 1
                print(f"✗ {relative_path}: {message}")
            else:
                stats["skipped"] += 1
                # Uncomment to show skipped files:
                # print(f"- {relative_path}: {message}")

    return stats


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Increment page markers in markdown files from 0-indexed to 1-indexed",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files",
    )
    parser.add_argument(
        "--documents-dir",
        type=Path,
        default=Path("Documents"),
        help="Path to Documents folder (default: ./Documents)",
    )

    args = parser.parse_args()

    documents_dir: Path = args.documents_dir

    if not documents_dir.exists():
        print(f"Error: Documents directory not found: {documents_dir}", file=sys.stderr)
        return 1

    if not documents_dir.is_dir():
        print(
            f"Error: Documents path is not a directory: {documents_dir}",
            file=sys.stderr,
        )
        return 1

    print(f"Processing markdown files in: {documents_dir}")
    if args.dry_run:
        print("DRY RUN MODE - No files will be modified")
    print()

    stats = process_documents_folder(documents_dir, dry_run=args.dry_run)

    print()
    print("=" * 60)
    print(f"Total files:     {stats['total']}")
    print(f"Modified:        {stats['modified']}")
    print(f"Skipped:         {stats['skipped']}")
    print(f"Errors:          {stats['errors']}")
    print("=" * 60)

    if args.dry_run and stats["modified"] > 0:
        print()
        print("Run without --dry-run to apply these changes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
