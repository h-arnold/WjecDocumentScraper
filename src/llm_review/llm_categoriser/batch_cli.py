"""CLI for batch orchestration commands.

Provides subcommands for creating and fetching batch jobs.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from src.llm.provider_registry import create_provider_chain
from src.llm.service import LLMService

from .batch_orchestrator import BatchOrchestrator, BatchJobTracker
from ..core.state_manager import CategoriserState


def add_batch_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Add batch-related subcommands to the parser.
    
    Args:
        subparsers: The subparsers object from argparse
    """
    # Create batch jobs subcommand
    create_parser = subparsers.add_parser(
        "batch-create",
        help="Create batch jobs for categorisation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create batch jobs for all documents
  python -m src.llm_review.llm_categoriser batch-create

  # Create for specific subjects
  python -m src.llm_review.llm_categoriser batch-create --subjects Geography "Art and Design"

  # Use custom batch size
  python -m src.llm_review.llm_categoriser batch-create --batch-size 5
        """,
    )
    
    create_parser.add_argument(
        "--from-report",
        type=Path,
        default=Path("Documents/language-check-report.csv"),
        help="Path to language-check-report.csv",
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
        default=int(os.environ.get("LLM_CATEGORISER_BATCH_SIZE", "10")),
        help="Number of issues per batch",
    )
    
    create_parser.add_argument(
        "--tracking-file",
        type=Path,
        default=Path("data/batch_jobs.json"),
        help="Path to job tracking file",
    )
    
    create_parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("data/llm_categoriser_state.json"),
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
  python -m src.llm_review.llm_categoriser batch-fetch --check-all-pending

  # Fetch specific jobs
  python -m src.llm_review.llm_categoriser batch-fetch --job-names batch-123 batch-456

  # Use custom tracking file
  python -m src.llm_review.llm_categoriser batch-fetch --check-all-pending --tracking-file data/my_jobs.json
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
        "--tracking-file",
        type=Path,
        default=Path("data/batch_jobs.json"),
        help="Path to job tracking file",
    )
    
    fetch_parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("data/llm_categoriser_state.json"),
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
  python -m src.llm_review.llm_categoriser batch-list

  # List only pending jobs
  python -m src.llm_review.llm_categoriser batch-list --status pending

  # List only completed jobs
  python -m src.llm_review.llm_categoriser batch-list --status completed
  
  # List failed jobs with error details
  python -m src.llm_review.llm_categoriser batch-list --status failed --show-errors
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
        default=Path("data/batch_jobs.json"),
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
  python -m src.llm_review.llm_categoriser batch-refresh-errors

  # Refresh specific job
  python -m src.llm_review.llm_categoriser batch-refresh-errors --job-name batches/abc123...
        """,
    )
    
    refresh_parser.add_argument(
        "--job-name",
        help="Specific job name to refresh (if not provided, refreshes all failed jobs)",
    )
    
    refresh_parser.add_argument(
        "--tracking-file",
        type=Path,
        default=Path("data/batch_jobs.json"),
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
  python -m src.llm_review.llm_categoriser batch-cancel --cancel-all-pending

  # Cancel specific jobs
  python -m src.llm_review.llm_categoriser batch-cancel --job-names batch-123 batch-456

  # Use custom tracking file
  python -m src.llm_review.llm_categoriser batch-cancel --cancel-all-pending --tracking-file data/my_jobs.json
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
        default=Path("data/batch_jobs.json"),
        help="Path to job tracking file",
    )
    
    cancel_parser.add_argument(
        "--dotenv",
        type=Path,
        help="Path to .env file for API keys",
    )


def handle_batch_create(args: argparse.Namespace) -> int:
    """Handle batch-create subcommand.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Load environment
    from dotenv import load_dotenv
    if args.dotenv:
        load_dotenv(dotenv_path=str(args.dotenv), override=True)
    else:
        load_dotenv(override=True)
    
    # Validate report file
    if not args.from_report.exists():
        print(f"Error: Report file not found: {args.from_report}", file=sys.stderr)
        return 1
    
    # Create LLM service
    try:
        from src.prompt.render_prompt import render_prompts
        
        system_prompt_text, _ = render_prompts(
            "system_language_tool_categoriser.md",
            "user_language_tool_categoriser.md",
            {},
        )
        
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
    
    # Create tracker and orchestrator
    tracker = BatchJobTracker(args.tracking_file)
    state = CategoriserState(args.state_file)
    orchestrator = BatchOrchestrator(
        llm_service=llm_service,
        tracker=tracker,
        state=state,
        batch_size=args.batch_size,
    )
    
    # Create batch jobs
    try:
        subjects_set = set(args.subjects) if args.subjects else None
        documents_set = set(args.documents) if args.documents else None
        
        orchestrator.create_batch_jobs(
            args.from_report,
            subjects=subjects_set,
            documents=documents_set,
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


def handle_batch_fetch(args: argparse.Namespace) -> int:
    """Handle batch-fetch subcommand.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Load environment
    from dotenv import load_dotenv
    if args.dotenv:
        load_dotenv(dotenv_path=str(args.dotenv), override=True)
    else:
        load_dotenv(override=True)
    
    # Create LLM service
    try:
        from src.prompt.render_prompt import render_prompts
        
        system_prompt_text, _ = render_prompts(
            "system_language_tool_categoriser.md",
            "user_language_tool_categoriser.md",
            {},
        )
        
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
    
    # Create state manager, tracker, and orchestrator
    state = CategoriserState(args.state_file)
    tracker = BatchJobTracker(args.tracking_file)
    orchestrator = BatchOrchestrator(
        llm_service=llm_service,
        tracker=tracker,
        state=state,
        batch_size=10,  # Not used for fetching
    )
    
    # Fetch batch results
    try:
        orchestrator.fetch_batch_results(
            state=state,
            job_names=args.job_names,
            check_all_pending=args.check_all_pending,
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
    """Handle batch-list subcommand.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        tracker = BatchJobTracker(args.tracking_file)
        
        # Create a dummy orchestrator just for listing
        from src.llm.service import LLMService
        
        # Create a dummy state (not used for listing)
        state = CategoriserState(Path("data/llm_categoriser_state.json"))
        
        orchestrator = BatchOrchestrator(
            llm_service=LLMService([]),  # Empty service, not used for listing
            tracker=tracker,
            state=state,
            batch_size=10,
        )
        
        orchestrator.list_jobs(
            status_filter=args.status,
            show_errors=args.show_errors
        )
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def handle_batch_refresh_errors(args: argparse.Namespace) -> int:
    """Handle batch-refresh-errors subcommand.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Load environment
    from dotenv import load_dotenv
    if args.dotenv:
        load_dotenv(dotenv_path=str(args.dotenv), override=True)
    else:
        load_dotenv(override=True)
    
    try:
        tracker = BatchJobTracker(args.tracking_file)
        
        # Set up LLM service - we only need it for status checks
        # Use empty system prompt since we're not generating
        providers = create_provider_chain(
            system_prompt="",
            filter_json=False,
            dotenv_path=None,
            primary=None,
        )
        llm_service = LLMService(providers)
        
        # Get jobs to refresh
        if args.job_name:
            job = tracker.get_job(args.job_name)
            if not job:
                print(f"Error: Job {args.job_name} not found", file=sys.stderr)
                return 1
            jobs_to_refresh = [job]
        else:
            # Get all failed jobs
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
                # Fetch current status from API
                status = llm_service.get_batch_job_status(
                    job.provider_name,
                    job_name
                )
                
                # Check actual job state
                if hasattr(status, 'state'):
                    state_name = str(status.state)
                    
                    # If job actually succeeded, update status
                    if 'SUCCEEDED' in state_name:
                        print(f"  Job actually succeeded! Updating status...")
                        tracker.update_job_status(job_name, "pending")  # Reset to pending so batch-fetch can process it
                        actually_succeeded += 1
                        continue
                
                # Check if there's an error message
                if hasattr(status, 'error') and status.error:
                    error_msg = str(status.error)
                    print(f"  Error: {error_msg}")
                    tracker.update_job_status(job_name, "failed", error_msg)
                    updated += 1
                else:
                    print(f"  No error details available (job state: {status.state if hasattr(status, 'state') else 'unknown'})")
                    skipped += 1
                    
            except Exception as e:
                print(f"  Error fetching status: {e}")
                skipped += 1
        
        print(f"\n{'=' * 60}")
        print(f"Summary:")
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
    """Handle batch-cancel subcommand.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Load environment
    from dotenv import load_dotenv
    if args.dotenv:
        load_dotenv(dotenv_path=str(args.dotenv), override=True)
    else:
        load_dotenv(override=True)
    
    # Create LLM service
    try:
        from src.prompt.render_prompt import render_prompts
        
        system_prompt_text, _ = render_prompts(
            "system_language_tool_categoriser.md",
            "user_language_tool_categoriser.md",
            {},
        )
        
        providers = create_provider_chain(
            system_prompt=system_prompt_text,
            filter_json=True,
            dotenv_path=None,
            primary=None,  # We only need API access for cancellation
        )
        
        if not providers:
            print("Error: No LLM providers configured", file=sys.stderr)
            return 1
        
        print(f"Using LLM provider(s): {[p.name for p in providers]}")
        llm_service = LLMService(providers)
        
    except Exception as e:
        print(f"Error creating LLM service: {e}", file=sys.stderr)
        return 1
    
    # Create tracker and orchestrator
    tracker = BatchJobTracker(args.tracking_file)
    
    # Create a dummy state (not used for cancellation)
    state = CategoriserState(Path("data/llm_categoriser_state.json"))
    
    orchestrator = BatchOrchestrator(
        llm_service=llm_service,
        tracker=tracker,
        state=state,
        batch_size=10,  # Not used for cancellation
    )
    
    # Cancel batch jobs
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

