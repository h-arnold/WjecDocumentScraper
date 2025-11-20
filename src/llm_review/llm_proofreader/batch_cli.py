"""CLI for batch orchestration commands for proofreader.

Provides subcommands for creating and fetching batch jobs.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def add_batch_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Add batch-related subcommands to the parser.

    Args:
        subparsers: The subparsers object from argparse
    """
    # Create batch jobs subcommand
    create_parser = subparsers.add_parser(
        "batch-create",
        help="Create batch jobs for proofreading",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create batch jobs for all documents
  python -m src.llm_review.llm_proofreader batch-create

  # Create for specific subjects
  python -m src.llm_review.llm_proofreader batch-create --subjects Geography "Art and Design"

  # Use custom batch size
  python -m src.llm_review.llm_proofreader batch-create --batch-size 5
        """,
    )

    create_parser.add_argument(
        "--from-report",
        type=Path,
        default=Path("Documents/verified-llm-categorised-language-check-report.csv"),
        help="Path to verified categorised report CSV",
    )

    create_parser.add_argument(
        "--subjects",
        nargs="+",
        help="Filter by subject names",
    )

    create_parser.add_argument(
        "--documents",
        nargs="+",
        help="Filter by document filenames",
    )

    create_parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.environ.get("LLM_PROOFREADER_BATCH_SIZE", "10")),
        help="Number of issues per batch",
    )

    create_parser.add_argument(
        "--tracking-file",
        type=Path,
        default=Path("data/proofreader_batch_jobs.json"),
        help="Path to job tracking file",
    )

    create_parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("data/llm_proofreader_state.json"),
        help="Path to state file",
    )

    # Fetch results subcommand
    fetch_parser = subparsers.add_parser(
        "batch-fetch",
        help="Fetch batch job results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch all pending jobs
  python -m src.llm_review.llm_proofreader batch-fetch --check-all-pending

  # Fetch specific job
  python -m src.llm_review.llm_proofreader batch-fetch --job-names batch-job-123
        """,
    )

    fetch_parser.add_argument(
        "--tracking-file",
        type=Path,
        default=Path("data/proofreader_batch_jobs.json"),
        help="Path to job tracking file",
    )

    fetch_parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("data/llm_proofreader_state.json"),
        help="Path to state file",
    )

    fetch_parser.add_argument(
        "--job-names",
        nargs="+",
        help="Specific job names to fetch",
    )

    fetch_parser.add_argument(
        "--check-all-pending",
        action="store_true",
        help="Check and fetch all pending jobs",
    )

    # List jobs subcommand
    list_parser = subparsers.add_parser(
        "batch-list",
        help="List batch jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    list_parser.add_argument(
        "--tracking-file",
        type=Path,
        default=Path("data/proofreader_batch_jobs.json"),
        help="Path to job tracking file",
    )

    list_parser.add_argument(
        "--status",
        choices=["pending", "completed", "failed"],
        help="Filter by status",
    )


def handle_batch_create(args: argparse.Namespace) -> int:
    """Handle batch-create command."""
    print("Creating batch jobs for proofreading...")
    print("Batch creation not fully implemented yet")
    return 0


def handle_batch_fetch(args: argparse.Namespace) -> int:
    """Handle batch-fetch command."""
    print("Fetching batch job results...")
    print("Batch fetch not fully implemented yet")
    return 0


def handle_batch_list(args: argparse.Namespace) -> int:
    """Handle batch-list command."""
    print("Listing batch jobs...")
    print("Batch list not fully implemented yet")
    return 0
