#!/usr/bin/env python3
"""Process all subjects incrementally with git-based checkpointing.

This script is designed for long-running operations (potentially days) on a server.
It processes WJEC subject folders one at a time, committing changes after each subject
completes, allowing resumption if interrupted.

Features:
- Creates or checks out a git branch for processed documents
- Maintains a state file (unprocessedSubjects.txt) tracking remaining work
- Processes subjects sequentially using main.py --post-process-only
- Commits changes after each subject completion
- Can resume from where it left off if interrupted
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


def find_subject_directories(root: Path) -> list[str]:
    """Return sorted list of subject directory names under the provided root."""
    if not root.exists() or not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith('.'))


def read_state_file(state_file: Path) -> list[str]:
    """Read subjects from state file, one per line."""
    if not state_file.exists():
        return []
    return [line.strip() for line in state_file.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_state_file(state_file: Path, subjects: list[str]) -> None:
    """Write subjects to state file, one per line."""
    state_file.write_text("\n".join(subjects) + "\n" if subjects else "", encoding="utf-8")


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


def commit_changes(subject: str, cwd: Path) -> bool:
    """Commit all changes with a message about the processed subject. Returns True on success."""
    # Add all changes
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


def process_subject(
    subject: str,
    root: Path,
    converter: str,
    uv_cmd: str,
    cwd: Path,
) -> bool:
    """Process a single subject using main.py. Returns True on success."""
    # Build the command as a list for safety
    parts = [*shlex.split(uv_cmd), 'main.py', '--post-process-only', '--subjects', subject, '--output', str(root), '--converter', converter]
    
    print(f"\n{'='*60}")
    print(f"Processing subject: {subject}")
    print(f"Command: {' '.join(shlex.quote(arg) for arg in parts)}")
    print(f"{'='*60}\n")
    
    # Run the command
    try:
        proc = subprocess.Popen(
            parts,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        
        # Stream output in real-time
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
        
        proc.wait()
        
        if proc.returncode != 0:
            print(f"\nError: Processing failed for subject '{subject}' with exit code {proc.returncode}", file=sys.stderr)
            return False
        
        print(f"\nSuccessfully processed subject '{subject}'")
        return True
        
    except Exception as exc:
        print(f"\nException while processing subject '{subject}': {exc}", file=sys.stderr)
        return False


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Process all WJEC subjects incrementally with git-based checkpointing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start processing all subjects (or resume if previously interrupted)
  python scripts/process_all_subjects.py

  # Use a different branch name
  python scripts/process_all_subjects.py --branch myBranch

  # Reset and start from scratch
  python scripts/process_all_subjects.py --reset

  # Dry run to see what would be processed
  python scripts/process_all_subjects.py --dry-run

  # Use markitdown converter instead of marker
  python scripts/process_all_subjects.py --converter markitdown
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
        default="uv run python",
        help="Command prefix to run Python via uv (default: 'uv run python')",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making changes",
    )
    
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset state file to start from scratch (rediscover all subjects)",
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
    subjects = read_state_file(state_file)
    
    if not subjects:
        # Discover subjects from directory
        print(f"Discovering subjects in '{args.root}'...")
        subjects = find_subject_directories(args.root)
        
        if not subjects:
            print(f"No subject directories found in '{args.root}'")
            return 1
        
        print(f"Found {len(subjects)} subject(s)")
        
        # Write initial state file
        write_state_file(state_file, subjects)
        print(f"Initialized state file '{state_file}' with {len(subjects)} subject(s)")
    else:
        print(f"Resuming from state file '{state_file}' with {len(subjects)} subject(s) remaining")
    
    # Show subjects to be processed
    print(f"\nSubjects to process:")
    for subject in subjects:
        print(f"  - {subject}")
    
    if args.dry_run:
        print("\nDry run mode: no changes will be made")
        return 0
    
    # Ensure git branch
    if not ensure_branch(args.branch, repo_root):
        return 2
    
    # Process subjects one by one
    processed_count = 0
    failed_subjects = []
    
    while subjects:
        current_subject = subjects[0]
        
        # Process the subject
        success = process_subject(
            current_subject,
            args.root,
            args.converter,
            args.uv_cmd,
            repo_root,
        )
        
        if not success:
            print(f"\nWarning: Failed to process subject '{current_subject}'", file=sys.stderr)
            failed_subjects.append(current_subject)
            # Remove from list anyway to avoid infinite loop
            subjects.pop(0)
            write_state_file(state_file, subjects)
            continue
        
        # Commit changes
        if not commit_changes(current_subject, repo_root):
            print(f"\nWarning: Failed to commit changes for subject '{current_subject}'", file=sys.stderr)
            # Continue anyway
        
        # Remove from unprocessed list
        subjects.pop(0)
        write_state_file(state_file, subjects)
        processed_count += 1
        
        print(f"\nProgress: {processed_count} completed, {len(subjects)} remaining")
    
    # Final summary
    print(f"\n{'='*60}")
    print("Processing complete!")
    print(f"Successfully processed: {processed_count} subject(s)")
    
    if failed_subjects:
        print(f"Failed to process: {len(failed_subjects)} subject(s)")
        for subject in failed_subjects:
            print(f"  - {subject}")
        return 2
    
    # Clean up state file
    if state_file.exists():
        state_file.unlink()
        print(f"Removed state file '{state_file}'")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
