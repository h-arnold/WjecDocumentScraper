"""CLI for batch orchestration commands (Verifier).

Provides subcommands for creating and fetching batch jobs for the categoriser verifier.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from src.llm.provider_registry import create_provider_chain
from src.llm.service import LLMService

from ..core.batch_orchestrator import BatchJobTracker
from ..core.state_manager import StateManager
from .batch_orchestrator import VerifierBatchOrchestrator


def add_batch_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Add batch-related subcommands to the parser.

    Args:
        subparsers: The subparsers object from argparse
    """
    # Create batch jobs subcommand
    create_parser = subparsers.add_parser(
        "batch-create",
        help="Create batch jobs for verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create batch jobs for all documents
  python -m src.llm_review.categoriser_verifier batch-create

  # Create for specific subjects
  python -m src.llm_review.categoriser_verifier batch-create --subjects Geography "Art and Design"

  # Use custom batch size
  python -m src.llm_review.categoriser_verifier batch-create --batch-size 5
        """,
    )

    create_parser.add_argument(
        "--from-report",
        type=Path,
        default=Path("Documents/llm_categorised-language-check-report.csv"),
        help="Path to llm_categorised-language-check-report.csv",
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
        default=int(os.environ.get("VERIFIER_BATCH_SIZE", "10")),
        help="Number of issues per batch",
    )

    create_parser.add_argument(
        "--tracking-file",
        type=Path,
        default=Path("data/verifier_batch_jobs.json"),
        help="Path to job tracking file",
    )

    create_parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("data/verifier_state.json"),
        help="State file path for tracking completed batches",
    )

    create_parser.add_argument(
        "--provider",
        help="Primary LLM provider (default: gemini)",
    )

    create_parser.add_argument(
        "--dotenv",
        type=Path,
        help="Path to .env file for API keys",
    )

    # Fetch batch results subcommand
    fetch_parser = subparsers.add_parser(
        "batch-fetch",
        help="Fetch results from completed batch jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check all pending jobs
  python -m src.llm_review.categoriser_verifier batch-fetch --check-all-pending

  # Fetch specific jobs
  python -m src.llm_review.categoriser_verifier batch-fetch --job-names batch-123 batch-456

  # Refetch batches completed in last 6 hours
  python -m src.llm_review.categoriser_verifier batch-fetch --refetch-hours 6

  # Use custom tracking file
  python -m src.llm_review.categoriser_verifier batch-fetch --check-all-pending --tracking-file data/my_jobs.json
        """,
    )

    fetch_parser.add_argument(
        "--job-names",
        nargs="+",
        help="Specific job names to fetch",
    )

    fetch_parser.add_argument(
        "--check-all-pending",
        action="store_true",
        help="Check all pending jobs for completion",
    )

    fetch_parser.add_argument(
        "--refetch-hours",
        type=float,
        help="Refetch and reprocess batches completed within this many hours (resets them to pending)",
    )

    fetch_parser.add_argument(
        "--from-report",
        type=Path,
        default=Path("Documents/llm_categorised-language-check-report.csv"),
        help="Path to llm_categorised-language-check-report.csv (for loading original issue data)",
    )

    fetch_parser.add_argument(
        "--tracking-file",
        type=Path,
        default=Path("data/verifier_batch_jobs.json"),
        help="Path to job tracking file",
    )

    fetch_parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("data/verifier_state.json"),
        help="State file path for marking batches complete",
    )

    fetch_parser.add_argument(
        "--provider",
        help="Primary LLM provider (default: gemini)",
    )

    fetch_parser.add_argument(
        "--dotenv",
        type=Path,
        help="Path to .env file for API keys",
    )

    # List batch jobs subcommand
    list_parser = subparsers.add_parser(
        "batch-list",
        help="List tracked batch jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all jobs
  python -m src.llm_review.categoriser_verifier batch-list

  # List only pending jobs
  python -m src.llm_review.categoriser_verifier batch-list --status pending

  # List only completed jobs
  python -m src.llm_review.categoriser_verifier batch-list --status completed
  
  # List failed jobs with error details
  python -m src.llm_review.categoriser_verifier batch-list --status failed --show-errors
        """,
    )

    list_parser.add_argument(
        "--status",
        choices=["pending", "completed", "failed"],
        help="Filter jobs by status",
    )

    list_parser.add_argument(
        "--show-errors",
        action="store_true",
        help="Display error messages for failed jobs",
    )

    list_parser.add_argument(
        "--tracking-file",
        type=Path,
        default=Path("data/verifier_batch_jobs.json"),
        help="Path to job tracking file",
    )

    # Refresh error details subcommand
    refresh_parser = subparsers.add_parser(
        "batch-refresh-errors",
        help="Fetch and update error details for failed jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Refresh error details for all failed jobs
  python -m src.llm_review.categoriser_verifier batch-refresh-errors

  # Refresh specific job
  python -m src.llm_review.categoriser_verifier batch-refresh-errors --job-name batches/abc123...
        """,
    )

    refresh_parser.add_argument(
        "--job-name",
        help="Specific job name to refresh (if not provided, refreshes all failed jobs)",
    )

    refresh_parser.add_argument(
        "--tracking-file",
        type=Path,
        default=Path("data/verifier_batch_jobs.json"),
        help="Path to job tracking file",
    )

    refresh_parser.add_argument(
        "--dotenv",
        type=Path,
        help="Path to .env file for API keys",
    )

    # Cancel batch jobs subcommand
    cancel_parser = subparsers.add_parser(
        "batch-cancel",
        help="Cancel pending batch jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Cancel all pending jobs
  python -m src.llm_review.categoriser_verifier batch-cancel --cancel-all-pending

  # Cancel specific jobs
  python -m src.llm_review.categoriser_verifier batch-cancel --job-names batch-123 batch-456

  # Use custom tracking file
  python -m src.llm_review.categoriser_verifier batch-cancel --cancel-all-pending --tracking-file data/my_jobs.json
        """,
    )

    cancel_parser.add_argument(
        "--job-names",
        nargs="+",
        help="Specific job names to cancel",
    )

    cancel_parser.add_argument(
        "--cancel-all-pending",
        action="store_true",
        help="Cancel all pending jobs",
    )

    cancel_parser.add_argument(
        "--tracking-file",
        type=Path,
        default=Path("data/verifier_batch_jobs.json"),
        help="Path to job tracking file",
    )

    cancel_parser.add_argument(
        "--dotenv",
        type=Path,
        help="Path to .env file for API keys",
    )


def handle_batch_create(args: argparse.Namespace) -> int:
    """Handle batch-create subcommand."""
    from dotenv import load_dotenv

    from .config import VerifierConfiguration

    if args.dotenv:
        load_dotenv(dotenv_path=str(args.dotenv), override=True)
    else:
        load_dotenv(override=True)

    if not args.from_report.exists():
        print(f"Error: Report file not found: {args.from_report}", file=sys.stderr)
        return 1

    try:
        from .prompt_factory import get_system_prompt_text

        system_prompt_text = get_system_prompt_text()

        providers = create_provider_chain(
            system_prompt=system_prompt_text,
            filter_json=True,
            dotenv_path=None,
            primary=args.provider,
        )

        if not providers:
            print("Error: No LLM providers configured", file=sys.stderr)
            return 1

        print(f"Using LLM provider(s): {[p.name for p in providers]}")
        llm_service = LLMService(providers)

    except Exception as e:
        print(f"Error creating LLM service: {e}", file=sys.stderr)
        return 1

    tracker = BatchJobTracker(args.tracking_file)
    state = StateManager(args.state_file)

    # Create a dummy config for the orchestrator
    config = VerifierConfiguration(
        input_csv_path=args.from_report,
        output_base_dir=Path("Documents"),
        output_subdir="verifier_reports",
        batch_size=args.batch_size,
        state_file=args.state_file,
        subjects=set(args.subjects) if args.subjects else None,
        documents=set(args.documents) if args.documents else None,
        max_retries=2,
        llm_provider=args.provider,
        fail_on_quota=True,
        log_raw_responses=False,
        log_response_dir=Path("data/verifier_responses"),
        output_csv_columns=[],
    )

    orchestrator = VerifierBatchOrchestrator(
        llm_service=llm_service,
        tracker=tracker,
        state=state,
        config=config,
    )

    try:
        orchestrator.create_batch_jobs()
        return 0

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


def handle_batch_fetch(args: argparse.Namespace) -> int:
    """Handle batch-fetch subcommand."""
    from dotenv import load_dotenv

    from .config import VerifierConfiguration

    if args.dotenv:
        load_dotenv(dotenv_path=str(args.dotenv), override=True)
    else:
        load_dotenv(override=True)

    try:
        from .prompt_factory import get_system_prompt_text

        system_prompt_text = get_system_prompt_text()

        providers = create_provider_chain(
            system_prompt=system_prompt_text,
            filter_json=True,
            dotenv_path=None,
            primary=args.provider,
        )

        if not providers:
            print("Error: No LLM providers configured", file=sys.stderr)
            return 1

        print(f"Using LLM provider(s): {[p.name for p in providers]}")
        llm_service = LLMService(providers)

    except Exception as e:
        print(f"Error creating LLM service: {e}", file=sys.stderr)
        return 1

    state = StateManager(args.state_file)
    tracker = BatchJobTracker(args.tracking_file)

    # Create a dummy config for the orchestrator
    config = VerifierConfiguration(
        input_csv_path=args.from_report,
        output_base_dir=Path("Documents"),
        output_subdir="verifier_reports",
        batch_size=10,  # Not used for fetching
        state_file=args.state_file,
        subjects=None,
        documents=None,
        max_retries=2,
        llm_provider=args.provider,
        fail_on_quota=True,
        log_raw_responses=False,
        log_response_dir=Path("data/verifier_responses"),
        output_csv_columns=[],
    )

    orchestrator = VerifierBatchOrchestrator(
        llm_service=llm_service,
        tracker=tracker,
        state=state,
        config=config,
    )

    try:
        orchestrator.fetch_batch_results(
            job_names=args.job_names,
            check_all_pending=args.check_all_pending,
            refetch_hours=args.refetch_hours,
        )
        return 0

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


def handle_batch_list(args: argparse.Namespace) -> int:
    """Handle batch-list subcommand."""
    try:
        from src.llm.service import LLMService

        from .config import VerifierConfiguration

        tracker = BatchJobTracker(args.tracking_file)
        state = StateManager(Path("data/verifier_state.json"))

        # Dummy config
        config = VerifierConfiguration(
            input_csv_path=Path("Documents/llm_categorised-language-check-report.csv"),
            output_base_dir=Path("Documents"),
            output_subdir="verifier_reports",
            batch_size=10,
            state_file=Path("data/verifier_state.json"),
            subjects=None,
            documents=None,
            max_retries=2,
            llm_provider=None,
            fail_on_quota=True,
            log_raw_responses=False,
            log_response_dir=Path("data/verifier_responses"),
            output_csv_columns=[],
        )

        orchestrator = VerifierBatchOrchestrator(
            llm_service=LLMService([]),
            tracker=tracker,
            state=state,
            config=config,
        )

        orchestrator.list_jobs(status_filter=args.status, show_errors=args.show_errors)
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def handle_batch_refresh_errors(args: argparse.Namespace) -> int:
    """Handle batch-refresh-errors subcommand."""
    from dotenv import load_dotenv

    if args.dotenv:
        load_dotenv(dotenv_path=str(args.dotenv), override=True)
    else:
        load_dotenv(override=True)

    try:
        tracker = BatchJobTracker(args.tracking_file)

        providers = create_provider_chain(
            system_prompt="",
            filter_json=False,
            dotenv_path=None,
            primary=None,
        )
        llm_service = LLMService(providers)

        if args.job_name:
            job = tracker.get_job(args.job_name)
            if not job:
                print(f"Error: Job {args.job_name} not found", file=sys.stderr)
                return 1
            jobs_to_refresh = [job]
        else:
            all_jobs = tracker.get_all_jobs()
            jobs_to_refresh = [j for j in all_jobs if j.status == "failed"]

        if not jobs_to_refresh:
            print("No failed jobs to refresh")
            return 0

        print(f"Refreshing error details for {len(jobs_to_refresh)} job(s)...\n")

        updated = 0
        skipped = 0
        actually_succeeded = 0

        for job in jobs_to_refresh:
            job_name = job.job_name
            print(f"Checking {job_name[:16]}... ({job.subject}/{job.filename})")

            try:
                status = llm_service.get_batch_job_status(job.provider_name, job_name)

                if hasattr(status, "state"):
                    state_name = str(status.state)
                    if "SUCCEEDED" in state_name:
                        print("  Job actually succeeded! Updating status...")
                        tracker.update_job_status(job_name, "pending")
                        actually_succeeded += 1
                        continue

                if hasattr(status, "error") and status.error:
                    error_msg = str(status.error)
                    print(f"  Error: {error_msg}")
                    tracker.update_job_status(job_name, "failed", error_msg)
                    updated += 1
                else:
                    print("  No error details available")
                    skipped += 1

            except Exception as e:
                print(f"  Error fetching status: {e}")
                skipped += 1

        print(f"\n{'=' * 60}")
        print("Summary:")
        print(f"  Updated with errors: {updated}")
        print(f"  Actually succeeded (reset to pending): {actually_succeeded}")
        print(f"  Skipped: {skipped}")
        print(f"{'=' * 60}")

        if actually_succeeded > 0:
            print(f"\nNote: {actually_succeeded} job(s) were reset to pending.")
            print("Run 'batch-fetch --check-all-pending' to process them.")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


def handle_batch_cancel(args: argparse.Namespace) -> int:
    """Handle batch-cancel subcommand."""
    from dotenv import load_dotenv

    from .config import VerifierConfiguration

    if args.dotenv:
        load_dotenv(dotenv_path=str(args.dotenv), override=True)
    else:
        load_dotenv(override=True)

    try:
        from .prompt_factory import get_system_prompt_text

        system_prompt_text = get_system_prompt_text()

        providers = create_provider_chain(
            system_prompt=system_prompt_text,
            filter_json=True,
            dotenv_path=None,
            primary=None,
        )

        if not providers:
            print("Error: No LLM providers configured", file=sys.stderr)
            return 1

        print(f"Using LLM provider(s): {[p.name for p in providers]}")
        llm_service = LLMService(providers)

    except Exception as e:
        print(f"Error creating LLM service: {e}", file=sys.stderr)
        return 1

    tracker = BatchJobTracker(args.tracking_file)
    state = StateManager(Path("data/verifier_state.json"))

    # Dummy config
    config = VerifierConfiguration(
        input_csv_path=Path("Documents/llm_categorised-language-check-report.csv"),
        output_base_dir=Path("Documents"),
        output_subdir="verifier_reports",
        batch_size=10,
        state_file=Path("data/verifier_state.json"),
        subjects=None,
        documents=None,
        max_retries=2,
        llm_provider=None,
        fail_on_quota=True,
        log_raw_responses=False,
        log_response_dir=Path("data/verifier_responses"),
        output_csv_columns=[],
    )

    orchestrator = VerifierBatchOrchestrator(
        llm_service=llm_service,
        tracker=tracker,
        state=state,
        config=config,
    )

    try:
        orchestrator.cancel_batch_jobs(
            job_names=args.job_names,
            cancel_all_pending=args.cancel_all_pending,
        )
        return 0

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1
