"""Command-line interface for the categoriser verifier.

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
    handle_batch_cancel,
    handle_batch_create,
    handle_batch_fetch,
    handle_batch_list,
    handle_batch_refresh_errors,
)
from .runner import VerifierRunner


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Verify LLM-categorised LanguageTool issues (second pass)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Verify all categorised issues
  python -m src.llm_review.categoriser_verifier

  # Verify specific subjects
  python -m src.llm_review.categoriser_verifier --subjects "Art and Design" Geography

  # Verify specific documents
  python -m src.llm_review.categoriser_verifier --documents gcse-geography.md

  # Force reprocessing (ignore state)
  python -m src.llm_review.categoriser_verifier --force

  # Use a different batch size
  python -m src.llm_review.categoriser_verifier --batch-size 5

  # Dry run (validate data loading only)
  python -m src.llm_review.categoriser_verifier --dry-run

Batch API Examples:
  # Create batch jobs
  python -m src.llm_review.categoriser_verifier batch-create

  # Fetch all pending batch results
  python -m src.llm_review.categoriser_verifier batch-fetch --check-all-pending

  # List all batch jobs
  python -m src.llm_review.categoriser_verifier batch-list

Environment Variables:
  VERIFIER_BATCH_SIZE        Default batch size (default: 10)
  VERIFIER_MAX_RETRIES       Maximum retries (default: 2)
  VERIFIER_STATE_FILE        State file path (default: data/verifier_state.json)
  VERIFIER_LOG_RESPONSES     Set to true/1 to dump raw LLM JSON responses
  VERIFIER_LOG_DIR           Override directory for raw response logs (default: data/verifier_responses)
  GEMINI_MIN_REQUEST_INTERVAL  Min seconds between Gemini requests (default: 0)
  GEMINI_MAX_RETRIES          Number of retry attempts for 429 rate limit errors (default: 0)
  LLM_PRIMARY                Primary LLM provider (default: gemini)
  LLM_FALLBACK               Fallback providers (comma-separated)
  LLM_FAIL_ON_QUOTA          When set (true/1/yes/on), exit the run on quota exhaustion (default: true)
        """,
    )

    # Add subparsers for batch commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    add_batch_subparsers(subparsers)

    # Input/output options
    parser.add_argument(
        "--from-report",
        type=Path,
        default=Path("Documents/llm_categorised-language-check-report.csv"),
        help="Path to llm_categorised-language-check-report.csv (default: Documents/llm_categorised-language-check-report.csv)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("Documents/verified-llm-categorised-language-check-report.csv"),
        help="Path to output CSV (default: Documents/verified-llm-categorised-language-check-report.csv)",
    )

    # Filtering options
    parser.add_argument(
        "--subjects",
        nargs="+",
        help="Filter by subject(s). Case-insensitive, partial matches allowed.",
    )

    parser.add_argument(
        "--documents",
        nargs="+",
        help="Filter by document filename(s). Case-insensitive, partial matches allowed.",
    )

    # Batch configuration
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.environ.get("VERIFIER_BATCH_SIZE", "10")),
        help="Number of issues per batch (default: 10, or VERIFIER_BATCH_SIZE env var)",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=int(os.environ.get("VERIFIER_MAX_RETRIES", "2")),
        help="Maximum retry attempts for failed validations (default: 2, or VERIFIER_MAX_RETRIES env var)",
    )

    # State management
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path(os.environ.get("VERIFIER_STATE_FILE", "data/verifier_state.json")),
        help="Path to state file (default: data/verifier_state.json, or VERIFIER_STATE_FILE env var)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocessing (ignore state)",
    )

    # LLM provider selection
    parser.add_argument(
        "--llm-provider",
        choices=["gemini", "openai"],
        help="LLM provider to use (default: uses provider chain from env vars)",
    )

    # Debugging options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate data loading only (don't call LLM)",
    )

    parser.add_argument(
        "--fail-on-quota",
        action="store_true",
        default=os.environ.get("LLM_FAIL_ON_QUOTA", "true").lower()
        in {"true", "1", "yes", "on"},
        help="Exit immediately on quota exhaustion (default: true)",
    )

    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    """Main entry point for the categoriser verifier CLI.

    Args:
        args: Command-line arguments (None = use sys.argv)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parsed_args = parse_args(args)

    # Handle batch subcommands
    if parsed_args.command == "batch-create":
        return handle_batch_create(parsed_args)
    elif parsed_args.command == "batch-fetch":
        return handle_batch_fetch(parsed_args)
    elif parsed_args.command == "batch-list":
        return handle_batch_list(parsed_args)
    elif parsed_args.command == "batch-refresh-errors":
        return handle_batch_refresh_errors(parsed_args)
    elif parsed_args.command == "batch-cancel":
        return handle_batch_cancel(parsed_args)

    # Normalize subject and document filters to sets (case-insensitive)
    subjects = (
        {s.strip().lower() for s in parsed_args.subjects}
        if parsed_args.subjects
        else None
    )
    documents = (
        {d.strip().lower() for d in parsed_args.documents}
        if parsed_args.documents
        else None
    )

    # Create LLM service
    if parsed_args.llm_provider:
        os.environ["LLM_PRIMARY"] = parsed_args.llm_provider

    try:
        # Render the system prompt and pass it to the provider chain
        from src.prompt.render_prompt import render_prompts

        system_prompt_text, _ = render_prompts(
            "system_categoriser_verifier",
            "user_language_tool_categoriser.md",
            {},
        )

        provider_chain = create_provider_chain(
            system_prompt=system_prompt_text,
            filter_json=True,
            dotenv_path=None,
            primary=parsed_args.llm_provider,
        )

        if not provider_chain:
            print("Error: No LLM providers configured", file=sys.stderr)
            return 1

        llm_service = LLMService(provider_chain)
    except Exception as e:
        print(f"Error creating LLM service: {e}", file=sys.stderr)
        return 1

    # Create state manager
    state = StateManager(parsed_args.state_file)

    # Create runner
    runner = VerifierRunner(
        llm_service,
        state,
        batch_size=parsed_args.batch_size,
        max_retries=parsed_args.max_retries,
        fail_on_quota=parsed_args.fail_on_quota,
    )

    # Update output path in config
    runner.config.aggregated_output_path = parsed_args.output

    # Run verification
    try:
        runner.run(
            parsed_args.from_report,
            subjects=subjects,
            documents=documents,
            force=parsed_args.force,
            dry_run=parsed_args.dry_run,
        )
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
