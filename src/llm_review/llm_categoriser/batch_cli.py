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
from .state import CategoriserState


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
        """,
    )
    
    list_parser.add_argument(
        "--status",
        choices=["pending", "completed", "failed"],
        help="Filter jobs by status",
    )
    
    list_parser.add_argument(
        "--tracking-file",
        type=Path,
        default=Path("data/batch_jobs.json"),
        help="Path to job tracking file",
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
    orchestrator = BatchOrchestrator(
        llm_service=llm_service,
        tracker=tracker,
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
        orchestrator = BatchOrchestrator(
            llm_service=LLMService([]),  # Empty service, not used for listing
            tracker=tracker,
            batch_size=10,
        )
        
        orchestrator.list_jobs(status_filter=args.status)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
