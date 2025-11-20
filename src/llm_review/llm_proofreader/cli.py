"""Command-line interface for the LLM proofreader.

Provides options for filtering, batch configuration, state management, and provider selection.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from src.llm.provider_registry import create_provider_chain
from src.llm.service import LLMService

from ..core.state_manager import StateManager
from .batch_cli import (
    add_batch_subparsers,
    handle_batch_create,
    handle_batch_fetch,
    handle_batch_list,
)
from .runner import ProofreaderRunner


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Proofread categorised issues using LLMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Synchronous Examples:
  # Process all issues in the default report
  python -m src.llm_review.llm_proofreader

  # Process specific subjects
  python -m src.llm_review.llm_proofreader --subjects "Art and Design" Geography

  # Process specific documents
  python -m src.llm_review.llm_proofreader --documents gcse-geography.md

  # Force reprocessing (ignore state)
  python -m src.llm_review.llm_proofreader --force

  # Use a different batch size
  python -m src.llm_review.llm_proofreader --batch-size 5

  # Dry run (validate data loading only)
  python -m src.llm_review.llm_proofreader --dry-run

Batch API Examples:
  # Create batch jobs
  python -m src.llm_review.llm_proofreader batch-create

  # Create batch jobs for specific subjects
  python -m src.llm_review.llm_proofreader batch-create --subjects Geography

  # Fetch all pending batch results
  python -m src.llm_review.llm_proofreader batch-fetch --check-all-pending

  # List all batch jobs
  python -m src.llm_review.llm_proofreader batch-list

Environment Variables:
  LLM_PROOFREADER_BATCH_SIZE     Default batch size (default: 10)
  LLM_PROOFREADER_MAX_RETRIES    Maximum retries (default: 2)
  LLM_PROOFREADER_STATE_FILE     State file path (default: data/llm_proofreader_state.json)
  LLM_PROOFREADER_LOG_RESPONSES  Set to true/1 to dump raw LLM JSON responses for each batch attempt
  LLM_PROOFREADER_LOG_DIR        Override directory for raw response logs (default: data/llm_proofreader_responses)
  GEMINI_MIN_REQUEST_INTERVAL    Min seconds between Gemini requests (default: 0)
  GEMINI_MAX_RETRIES             Number of retry attempts for 429 rate limit errors (default: 0)
  LLM_PRIMARY                    Primary LLM provider (default: gemini)
  LLM_FALLBACK                   Fallback providers (comma-separated)
  LLM_FAIL_ON_QUOTA              When set (true/1/yes/on), exit the run on quota exhaustion (default: true)
        """,
    )

    # Add subparsers for batch commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    add_batch_subparsers(subparsers)

    # Input/output options
    parser.add_argument(
        "--from-report",
        type=Path,
        default=Path("Documents/verified-llm-categorised-language-check-report.csv"),
        help="Path to verified-llm-categorised-language-check-report.csv (default: Documents/verified-llm-categorised-language-check-report.csv)",
    )

    # Filtering options
    parser.add_argument(
        "--subjects",
        nargs="+",
        help="Filter by subject names (case-insensitive substring match)",
    )

    parser.add_argument(
        "--documents",
        nargs="+",
        help="Filter by document filenames (case-insensitive substring match)",
    )

    # Batch configuration
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.environ.get("LLM_PROOFREADER_BATCH_SIZE", "10")),
        help="Number of issues per batch (default: 10)",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=int(os.environ.get("LLM_PROOFREADER_MAX_RETRIES", "2")),
        help="Maximum retry attempts for failed batches (default: 2)",
    )

    # State management
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path(
            os.environ.get("LLM_PROOFREADER_STATE_FILE", "data/llm_proofreader_state.json")
        ),
        help="Path to state file for tracking progress",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocessing of all batches (ignore existing state)",
    )

    # Execution mode
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate data loading without calling LLM",
    )

    return parser.parse_args(args)


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI.

    Args:
        argv: Command-line arguments (None = use sys.argv)

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    args = parse_args(argv)

    # Handle batch subcommands
    if args.command == "batch-create":
        return handle_batch_create(args)
    elif args.command == "batch-fetch":
        return handle_batch_fetch(args)
    elif args.command == "batch-list":
        return handle_batch_list(args)

    # Synchronous processing mode
    try:
        # Load .env file
        from dotenv import load_dotenv
        load_dotenv(override=True)

        # Validate report file exists
        if not args.from_report.exists():
            print(
                f"Error: Report file not found: {args.from_report}", file=sys.stderr
            )
            return 1

        # Render the system prompt and pass it to the provider chain
        from src.prompt.render_prompt import render_prompts

        system_prompt_text, _ = render_prompts(
            "llm_proofreader.md",
            "user_llm_proofreader.md",
            {},
        )

        # Initialize LLM service with provider chain
        provider_chain = create_provider_chain(
            system_prompt=system_prompt_text,
            filter_json=True,
            dotenv_path=None,
        )

        if not provider_chain:
            print("Error: No LLM providers configured", file=sys.stderr)
            return 1

        print(f"Using LLM provider(s): {[p.name for p in provider_chain]}")
        llm_service = LLMService(provider_chain)

        # Initialize state manager
        state = StateManager(args.state_file)

        # Create runner
        runner = ProofreaderRunner(
            llm_service,
            state,
            batch_size=args.batch_size,
            max_retries=args.max_retries,
        )

        # Set config parameters for the run
        runner.config.input_csv_path = args.from_report
        runner.config.subjects = set(args.subjects) if args.subjects else None
        runner.config.documents = set(args.documents) if args.documents else None

        # Run the workflow
        summary = runner.run(
            force=args.force,
            dry_run=args.dry_run,
        )

        # Print summary
        print("\n" + "=" * 60)
        print("Summary:")
        print(f"  Total documents: {summary['total_documents']}")
        print(f"  Total batches: {summary['total_batches']}")
        print(f"  Processed batches: {summary['processed_batches']}")
        print(f"  Skipped batches: {summary['skipped_batches']}")
        print(f"  Total issues: {summary['total_issues']}")
        print("=" * 60)

        return 0

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
