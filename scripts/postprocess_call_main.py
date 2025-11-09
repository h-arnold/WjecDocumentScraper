#!/usr/bin/env python3
"""Call `main.py` per-subject to run post-processing with the marker converter.

This script enumerates subject directories under the provided root (default: `Documents/`),
excludes `Art-and-Design` and `Integrated-Science-Single-Award`, and for each remaining
subject runs the CLI:

    uv run python main.py --post-process-only --subjects "<Subject>" --output <root> --converter marker

Use `--dry-run` to only print the commands that would be executed.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Iterable


DEFAULT_EXCLUDES = {"art-and-design", "integrated-science-single-award"}


def find_subject_directories(root: Path) -> list[Path]:
    return sorted(p for p in root.iterdir() if p.is_dir())


def choose_subjects(root: Path, excludes: Iterable[str]) -> list[str]:
    all_dirs = [p for p in find_subject_directories(root)]
    exclude_lower = {e.lower() for e in excludes}
    return sorted(p.name for p in all_dirs if p.name.lower() not in exclude_lower)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run main.py post-processing per subject using marker converter.")
    p.add_argument("--root", type=Path, default=Path("Documents"), help="Root Documents folder")
    p.add_argument("--exclude", nargs="*", default=None, help="Additional folder names to exclude")
    p.add_argument("--dry-run", action="store_true", help="Print commands without executing them")
    p.add_argument("--uv-cmd", default="uv run python", help="Prefix command to run Python via uv (default: 'uv run python')")
    return p


def run_command(cmd: str) -> int:
    print(f"Running: {cmd}")
    # Use shell=False with shlex.split for safety
    parts = shlex.split(cmd)
    proc = subprocess.Popen(parts, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="")
    proc.wait()
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = args.root
    if not root.exists() or not root.is_dir():
        print(f"Root folder {root} does not exist or is not a directory", file=sys.stderr)
        return 2

    excludes = set(DEFAULT_EXCLUDES)
    if args.exclude:
        excludes.update(args.exclude)

    subjects = choose_subjects(root, excludes)
    if not subjects:
        print("No subjects to process after applying excludes.")
        return 0

    commands = []
    for subject in subjects:
        # Quote the subject name in case it contains spaces
        cmd = f"{args.uv_cmd} main.py --post-process-only --subjects \"{subject}\" --output {shlex.quote(str(root))} --converter marker"
        commands.append(cmd)

    print("Will process the following subjects:")
    for s in subjects:
        print(" -", s)

    if args.dry_run:
        print("\nDry-run mode: the following commands would be executed:")
        for c in commands:
            print(c)
        return 0

    exit_codes = []
    for cmd in commands:
        rc = run_command(cmd)
        exit_codes.append(rc)
        if rc != 0:
            print(f"Command failed with exit code {rc}: {cmd}", file=sys.stderr)

    # Return non-zero if any run failed
    return 0 if all(rc == 0 for rc in exit_codes) else 2


if __name__ == "__main__":
    raise SystemExit(main())
