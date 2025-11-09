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


def find_subject_directories(root: Path) -> list[str]:
    """Return a sorted list of subject directory names under ``root``.

    Hidden directories (names starting with a dot) are ignored. If the
    provided path does not exist or is not a directory an empty list is
    returned.
    """
    if not root.exists() or not root.is_dir():
        return []

    subjects: list[str] = []
    for item in sorted(root.iterdir()):
        if not item.is_dir():
            continue
        if item.name.startswith("."):
            continue
        subjects.append(item.name)

    return sorted(subjects)


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


def commit_changes(subject: str, documents_root_or_cwd: Path, cwd: Path | None = None) -> bool:
    """Commit changes after processing a subject.

    Two supported call signatures for convenience in tests and script usage:
    - Legacy: commit_changes(subject, cwd)
      -> stages all changes (git add .) in ``cwd`` and commits (original behaviour).
    - New: commit_changes(subject, documents_root, cwd)
      -> stages only markdown files under ``<documents_root>/<subject>/markdown``, commits
         and pushes the current branch.

    Returns True on success or when there is nothing to commit.
    """
    # Determine which calling convention is used
    if cwd is None:
        # Legacy form: second arg is cwd
        cwd = documents_root_or_cwd
        # Stage all changes (original behaviour)
        exit_code, output = git_command(["add", "."], cwd)
        if exit_code != 0:
            print(f"Failed to stage changes: {output}", file=sys.stderr)
            return False

        # Check if there are changes to commit
        exit_code, output = git_command(["diff", "--cached", "--quiet"], cwd)
        if exit_code == 0:
            # No changes to commit
            print(f"No changes to commit for subject '{subject}'")
            return True

        # Commit changes
        commit_message = f"Process subject: {subject}"
        exit_code, output = git_command(["commit", "-m", commit_message], cwd)
        if exit_code != 0:
            print(f"Failed to commit changes: {output}", file=sys.stderr)
            return False

        print(f"Committed changes for subject '{subject}'")
        return True

    # New calling convention: documents_root_or_cwd is documents_root, cwd is repo cwd
    documents_root = documents_root_or_cwd

    markdown_dir = documents_root / subject / "markdown"

    if not markdown_dir.exists() or not markdown_dir.is_dir():
        print(f"No markdown directory for subject '{subject}' -> nothing to commit")
        return True

    # Ask git for any changed files under the markdown directory
    rel_path = str(markdown_dir)
    exit_code, output = git_command(["status", "--porcelain", "--", rel_path], cwd)
    if exit_code != 0:
        print(f"Failed to query git status for '{rel_path}': {output}", file=sys.stderr)
        return False

    changed_files: list[str] = []
    for line in output.splitlines():
        if not line:
            continue
        # git status --porcelain format: XY <path>
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            path_part = parts[1]
            # Only consider markdown files
            if path_part.endswith('.md'):
                changed_files.append(path_part)

    if not changed_files:
        print(f"No markdown changes to commit for subject '{subject}'")
        return True

    # Stage only the markdown files
    cmd = ["add", "--"] + changed_files
    exit_code, output = git_command(cmd, cwd)
    if exit_code != 0:
        print(f"Failed to stage markdown files: {output}", file=sys.stderr)
        return False

    # Check if there are staged changes
    exit_code, output = git_command(["diff", "--cached", "--quiet"], cwd)
    if exit_code == 0:
        print(f"No staged changes to commit for subject '{subject}'")
        return True

    commit_message = f"Process subject: {subject} (generated markdown)"
    exit_code, output = git_command(["commit", "-m", commit_message], cwd)
    if exit_code != 0:
        print(f"Failed to commit changes: {output}", file=sys.stderr)
        return False

    print(f"Committed markdown changes for subject '{subject}'")

    # Determine current branch and push
    exit_code, branch = git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    if exit_code != 0:
        print(f"Failed to determine current branch: {branch}", file=sys.stderr)
        return True  # commit succeeded; treat push as non-fatal

    branch = branch.strip()
    if not branch:
        print("Unable to determine current branch to push", file=sys.stderr)
        return True

    exit_code, output = git_command(["push", "--set-upstream", "origin", branch], cwd)
    if exit_code != 0:
        print(f"Warning: failed to push branch '{branch}': {output}", file=sys.stderr)
        # push failure is non-fatal for the conversion process

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
        from src.postprocessing import process_single_pdf
        
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


def process_subject(
    subject: str,
    root: Path,
    converter: str,
    uv_cmd: str,
    cwd: Path,
) -> bool:
    """Process a single subject by invoking the conversion subprocess.

    This function is intentionally lightweight for the test-suite: it
    spawns a subprocess using the provided ``uv_cmd`` token (for example
    "uv run python"), consumes stdout lines and returns True when the
    subprocess exit code is zero and False otherwise.
    """
    # If a per-subject helper script exists, prefer calling it via subprocess.
    helper_script = cwd / "scripts" / "process_single_subject.py"
    if helper_script.exists():
        try:
            cmd = list(uv_cmd.split()) + [str(helper_script), str(subject), "--converter", converter]
            proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

            if proc.stdout is not None:
                for _line in proc.stdout:
                    pass

            return getattr(proc, "returncode", None) == 0
        except Exception:
            return False

    # Fallback: process PDFs directly for the subject directory. This mirrors
    # the original, pre-refactor behaviour so running the script in the repo
    # still works even when the helper script is absent.
    subject_dir = root / subject
    if not subject_dir.exists() or not subject_dir.is_dir():
        return False

    # Collect PDFs in the subject root and in pdfs/ that lack markdown
    pdfs_to_process: list[Path] = []
    markdown_dir = subject_dir / "markdown"

    for pdf_path in subject_dir.glob("*.pdf"):
        pdfs_to_process.append(pdf_path)

    pdfs_subdir = subject_dir / "pdfs"
    if pdfs_subdir.exists() and pdfs_subdir.is_dir():
        for pdf_path in pdfs_subdir.glob("*.pdf"):
            markdown_path = markdown_dir / f"{pdf_path.stem}.md"
            if not markdown_path.exists():
                pdfs_to_process.append(pdf_path)

    if not pdfs_to_process:
        # Nothing to do; not an error
        return True

    any_success = False
    for pdf in sorted(pdfs_to_process):
        ok = process_pdf_file(pdf, converter, cwd)
        if ok:
            any_success = True
        # continue processing other PDFs even if one fails

    return any_success


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
        default=Path("unprocessedSubjects.txt"),
        help="State file tracking unprocessed subjects (default: unprocessedSubjects.txt)",
    )
    
    parser.add_argument(
        "--converter",
        default="marker",
        choices=["markitdown", "marker"],
        help="Converter to use for PDF to Markdown conversion (default: marker)",
    )

    parser.add_argument(
        "--uv-cmd",
        dest="uv_cmd",
        default="uv run python",
        help="Command prefix to invoke Python within the project's uv environment (default: 'uv run python')",
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
    
    # Handle state file path (relative to the provided root directory when relative)
    state_file = args.state_file
    if not state_file.is_absolute():
        # Place the state file alongside the provided root so running against a
        # temporary Documents dir (tests) doesn't pick up the repo-level state file.
        state_file = args.root / state_file
    
    # Reset state file if requested
    if args.reset:
        print(f"Resetting state file '{state_file}'...")
        if state_file.exists():
            state_file.unlink()
        print("State file reset")
    
    # Read or initialize state file (subject-oriented)
    subjects = read_state_file(state_file)

    if not subjects:
        print(f"Discovering subjects in '{args.root}'...")
        subjects = find_subject_directories(args.root)

        if not subjects:
            print(f"No subject directories found in '{args.root}'")
            return 1

        print(f"Found {len(subjects)} subject(s)")
        write_state_file(state_file, subjects)
        print(f"Initialized state file '{state_file}' with {len(subjects)} subject(s)")
    else:
        print(f"Resuming from state file '{state_file}' with {len(subjects)} subject(s) remaining")

    # Show a sample of subjects to be processed
    print(f"\nSubjects to process:")
    for subj in subjects[:10]:
        print(f"  - {subj}")
    if len(subjects) > 10:
        print(f"  ... and {len(subjects) - 10} more")

    if args.dry_run:
        print("\nDry run mode: no changes will be made")
        return 0

    # Ensure git branch
    if not ensure_branch(args.branch, repo_root):
        return 2

    processed_count = 0
    failed = []

    while subjects:
        current = subjects[0]

        success = process_subject(
            current,
            args.root,
            args.converter,
            args.uv_cmd,
            repo_root,
        )

        if not success:
            print(f"\nWarning: Failed to process subject '{current}'", file=sys.stderr)
            failed.append(current)
            # Remove from list to avoid infinite loop
            subjects.pop(0)
            write_state_file(state_file, subjects)
            continue

        # Commit changes for this subject
        if not commit_changes(current, repo_root):
            print(f"\nWarning: Failed to commit changes for subject '{current}'", file=sys.stderr)
            # Continue anyway

        subjects.pop(0)
        write_state_file(state_file, subjects)
        processed_count += 1
        print(f"\nProgress: {processed_count} completed, {len(subjects)} remaining")

    # Final summary
    print(f"\n{'='*60}")
    print("Processing complete!")
    print(f"Successfully processed: {processed_count} subject(s)")

    if failed:
        print(f"Failed to process: {len(failed)} subject(s)")
        for subj in failed:
            print(f"  - {subj}")
        return 2

    # Clean up state file
    if state_file.exists():
        state_file.unlink()
        print(f"Removed state file '{state_file}'")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
