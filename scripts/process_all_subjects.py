#!/usr/bin/env python3
"""Post-process PDF files incrementally with git-based checkpointing.

This script is designed for long-running post-processing operations (potentially days) on a server.
It converts PDF files to Markdown one at a time, committing changes after each file
completes, allowing resumption if interrupted.

The script assumes PDFs have already been downloaded (e.g., via main.py).

Features:
- Creates or checks out a git branch for processed documents
- Maintains a state file (unprocessedFiles.txt) tracking remaining work
- Processes PDF files sequentially using process_single_pdf from postprocess_documents
- Commits changes after each file completion
- Can resume from where it left off if interrupted
- Skips PDFs that already have a corresponding Markdown file
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def find_pdf_files(root: Path) -> list[Path]:
    """Return sorted list of PDF file paths (relative to root) that need to be converted to Markdown.
    
    This looks for:
    1. PDFs in subject root (will be copied to pdfs/ and converted)
    2. PDFs in pdfs/ subdirectory that don't have a corresponding .md file in markdown/
    """
    if not root.exists() or not root.is_dir():
        return []
    
    pdf_files: list[Path] = []
    
    # Find all subject directories
    for subject_dir in sorted(root.iterdir()):
        if not subject_dir.is_dir() or subject_dir.name.startswith('.'):
            continue
        
        markdown_dir = subject_dir / "markdown"
        
        # Look for PDFs in subject root (these always need processing)
        for pdf_path in subject_dir.glob("*.pdf"):
            # Store relative path from root
            pdf_files.append(pdf_path.relative_to(root))
        
        # Look for PDFs in pdfs/ subdirectory that haven't been converted yet
        pdfs_subdir = subject_dir / "pdfs"
        if pdfs_subdir.exists() and pdfs_subdir.is_dir():
            for pdf_path in pdfs_subdir.glob("*.pdf"):
                # Check if corresponding markdown file exists
                markdown_path = markdown_dir / f"{pdf_path.stem}.md"
                if not markdown_path.exists():
                    # This PDF needs to be converted
                    pdf_files.append(pdf_path.relative_to(root))
    
    return sorted(pdf_files)


def read_state_file(state_file: Path) -> list[str]:
    """Read PDF file paths from state file, one per line."""
    if not state_file.exists():
        return []
    return [line.strip() for line in state_file.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_state_file(state_file: Path, pdf_files: list[str]) -> None:
    """Write PDF file paths to state file, one per line."""
    state_file.write_text("\n".join(pdf_files) + "\n" if pdf_files else "", encoding="utf-8")


def git_command(args: list[str], cwd: Path) -> tuple[int, str]:
    """Run a git command and return (exit_code, output)."""
    cmd = ["git"] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode, result.stdout + result.stderr
    except Exception as exc:
        return 1, str(exc)


def ensure_branch(branch_name: str, cwd: Path) -> bool:
    """Create or checkout the specified branch. Returns True on success."""
    # Check if branch exists
    exit_code, output = git_command(["rev-parse", "--verify", branch_name], cwd)
    
    if exit_code == 0:
        # Branch exists, check it out
        print(f"Branch '{branch_name}' exists, checking out...")
        exit_code, output = git_command(["checkout", branch_name], cwd)
        if exit_code != 0:
            print(f"Failed to checkout branch '{branch_name}': {output}", file=sys.stderr)
            return False
        print(f"Checked out branch '{branch_name}'")
    else:
        # Branch doesn't exist, create it
        print(f"Creating new branch '{branch_name}'...")
        exit_code, output = git_command(["checkout", "-b", branch_name], cwd)
        if exit_code != 0:
            print(f"Failed to create branch '{branch_name}': {output}", file=sys.stderr)
            return False
        print(f"Created and checked out branch '{branch_name}'")
    
    return True


def commit_changes(pdf_file: str, cwd: Path) -> bool:
    """Commit all changes with a message about the processed PDF file. Returns True on success."""
    # Add all changes
    exit_code, output = git_command(["add", "."], cwd)
    if exit_code != 0:
        print(f"Failed to stage changes: {output}", file=sys.stderr)
        return False
    
    # Check if there are changes to commit
    exit_code, output = git_command(["diff", "--cached", "--quiet"], cwd)
    if exit_code == 0:
        # No changes to commit
        print(f"No changes to commit for PDF '{pdf_file}'")
        return True
    
    # Commit changes
    commit_message = f"Process PDF: {pdf_file}"
    exit_code, output = git_command(["commit", "-m", commit_message], cwd)
    if exit_code != 0:
        print(f"Failed to commit changes: {output}", file=sys.stderr)
        return False
    
    print(f"Committed changes for PDF '{pdf_file}'")
    return True


def process_pdf_file(
    pdf_file: Path,
    converter: str,
    cwd: Path,
) -> bool:
    """Process a single PDF file using process_single_pdf from postprocess_documents. Returns True on success."""
    print(f"\n{'='*60}")
    print(f"Processing PDF: {pdf_file}")
    print(f"{'='*60}\n")
    
    # Import here to avoid issues with path setup
    sys.path.insert(0, str(cwd))
    try:
        from postprocess_documents import process_single_pdf
        
        result = process_single_pdf(pdf_file, converter)
        
        if result.success:
            print(f"\n✓ Successfully converted to: {result.markdown_path}")
            return True
        else:
            print(f"\n✗ Failed to process PDF: {result.error}", file=sys.stderr)
            return False
    
    except Exception as exc:
        print(f"\nException while processing PDF '{pdf_file}': {exc}", file=sys.stderr)
        return False


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Post-process WJEC PDF files incrementally with git-based checkpointing. Converts PDFs to Markdown one at a time. Assumes PDFs have already been downloaded.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start post-processing all PDF files (or resume if previously interrupted)
  uv run python scripts/process_all_subjects.py

  # Use a different branch name
  uv run python scripts/process_all_subjects.py --branch myBranch

  # Reset and start from scratch
  uv run python scripts/process_all_subjects.py --reset

  # Dry run to see what would be processed
  uv run python scripts/process_all_subjects.py --dry-run

  # Use markitdown converter instead of marker
  uv run python scripts/process_all_subjects.py --converter markitdown
        """,
    )
    
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("Documents"),
        help="Root directory containing subject folders (default: Documents)",
    )
    
    parser.add_argument(
        "--branch",
        default="processedDocuments",
        help="Git branch name for processed documents (default: processedDocuments)",
    )
    
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("unprocessedFiles.txt"),
        help="State file tracking unprocessed PDF files (default: unprocessedFiles.txt)",
    )
    
    parser.add_argument(
        "--converter",
        default="marker",
        choices=["markitdown", "marker"],
        help="Converter to use for PDF to Markdown conversion (default: marker)",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making changes",
    )
    
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset state file to start from scratch (rediscover all PDF files)",
    )
    
    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    
    # Validate root directory
    if not args.root.exists() or not args.root.is_dir():
        print(f"Error: Root directory '{args.root}' does not exist or is not a directory", file=sys.stderr)
        return 2
    
    # Get repository root (assume we're in the repo)
    repo_root = Path.cwd()
    
    # Handle state file path (relative to repo root)
    state_file = args.state_file
    if not state_file.is_absolute():
        state_file = repo_root / state_file
    
    # Reset state file if requested
    if args.reset:
        print(f"Resetting state file '{state_file}'...")
        if state_file.exists():
            state_file.unlink()
        print("State file reset")
    
    # Read or initialize state file
    pdf_files_str = read_state_file(state_file)
    
    if not pdf_files_str:
        # Discover PDF files from directory
        print(f"Discovering PDF files in '{args.root}'...")
        pdf_files = find_pdf_files(args.root)
        
        if not pdf_files:
            print(f"No PDF files found in '{args.root}'")
            return 1
        
        print(f"Found {len(pdf_files)} PDF file(s)")
        
        # Convert to strings for state file
        pdf_files_str = [str(p) for p in pdf_files]
        
        # Write initial state file
        write_state_file(state_file, pdf_files_str)
        print(f"Initialized state file '{state_file}' with {len(pdf_files_str)} PDF file(s)")
    else:
        print(f"Resuming from state file '{state_file}' with {len(pdf_files_str)} PDF file(s) remaining")
    
    # Show first few files to be processed
    print(f"\nPDF files to process:")
    for pdf_file in pdf_files_str[:10]:
        print(f"  - {pdf_file}")
    if len(pdf_files_str) > 10:
        print(f"  ... and {len(pdf_files_str) - 10} more")
    
    if args.dry_run:
        print("\nDry run mode: no changes will be made")
        return 0
    
    # Ensure git branch
    if not ensure_branch(args.branch, repo_root):
        return 2
    
    # Process PDF files one by one
    processed_count = 0
    failed_files = []
    
    while pdf_files_str:
        current_pdf_str = pdf_files_str[0]
        current_pdf = args.root / current_pdf_str
        
        # Process the PDF file
        success = process_pdf_file(
            current_pdf,
            args.converter,
            repo_root,
        )
        
        if not success:
            print(f"\nWarning: Failed to process PDF '{current_pdf_str}'", file=sys.stderr)
            failed_files.append(current_pdf_str)
            # Remove from list anyway to avoid infinite loop
            pdf_files_str.pop(0)
            write_state_file(state_file, pdf_files_str)
            continue
        
        # Commit changes
        if not commit_changes(current_pdf_str, repo_root):
            print(f"\nWarning: Failed to commit changes for PDF '{current_pdf_str}'", file=sys.stderr)
            # Continue anyway
        
        # Remove from unprocessed list
        pdf_files_str.pop(0)
        write_state_file(state_file, pdf_files_str)
        processed_count += 1
        
        print(f"\nProgress: {processed_count} completed, {len(pdf_files_str)} remaining")
    
    # Final summary
    print(f"\n{'='*60}")
    print("Processing complete!")
    print(f"Successfully processed: {processed_count} PDF file(s)")
    
    if failed_files:
        print(f"Failed to process: {len(failed_files)} PDF file(s)")
        for pdf_file in failed_files:
            print(f"  - {pdf_file}")
        return 2
    
    # Clean up state file
    if state_file.exists():
        state_file.unlink()
        print(f"Removed state file '{state_file}'")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
