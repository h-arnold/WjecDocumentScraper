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
from .page_runner import PageBasedProofreaderRunner


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

  # Use a different pages per batch
  python -m src.llm_review.llm_proofreader --pages-per-batch 5

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
  LLM_PROOFREADER_BATCH_SIZE     Default pages per batch (default: 3)
  LLM_PROOFREADER_MAX_RETRIES    Maximum retries (default: 2)
  LLM_PROOFREADER_STATE_FILE     State file path (default: data/llm_page_proofreader_state.json)
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
        "--pages-per-batch",
        type=int,
        default=int(os.environ.get("LLM_PROOFREADER_BATCH_SIZE", "3")),
        help="Number of pages per batch (default: 3, or LLM_PROOFREADER_BATCH_SIZE env var)",
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
            os.environ.get(
                "LLM_PROOFREADER_STATE_FILE", "data/llm_proofreader_state.json"
            )
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

    # Provider options
    parser.add_argument(
        "--provider",
        help="Primary LLM provider (default: gemini or LLM_PRIMARY)",
    )

    parser.add_argument(
        "--dotenv",
        type=Path,
        help="Path to .env file for API keys",
    )

    # Special modes
    parser.add_argument(
        "--emit-batch-payload",
        action="store_true",
        help="Write batch payloads to data/batch_payloads/ and exit (for manual testing)",
    )

    parser.add_argument(
        "--emit-prompts",
        action="store_true",
        help=(
            "Write plain-text prompts (system + user) to files under data/prompt_payloads/ "
            "and exit (useful for manual testing in AI Studio)"
        ),
    )

    # Quota behaviour: default True, can be overridden by env or CLI switch
    parser.add_argument(
        "--fail-on-quota",
        dest="fail_on_quota",
        action="store_true",
        default=None,
        help="Exit the run when LLM providers report quota/rate-limit exhaustion (default: true)",
    )

    parser.add_argument(
        "--no-fail-on-quota",
        dest="fail_on_quota",
        action="store_false",
        default=None,
        help="Do not abort the whole run on quota exhaustion; continue processing other documents",
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

        if args.dotenv:
            load_dotenv(dotenv_path=str(args.dotenv), override=True)
        else:
            load_dotenv(override=True)

        # Handle --emit-batch-payload mode
        if args.emit_batch_payload:
            return emit_batch_payloads(args)

        # Handle --emit-prompts mode
        if args.emit_prompts:
            return emit_prompts(args)

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
            primary=args.provider,
        )

        if not provider_chain:
            print("Error: No LLM providers configured", file=sys.stderr)
            return 1

        print(f"Using LLM provider(s): {[p.name for p in provider_chain]}")
        llm_service = LLMService(provider_chain)

        # Initialize state manager
        state = StateManager(args.state_file)

        # Determine fail_on_quota: CLI arg wins, else environment variable, else default True
        if args.fail_on_quota is not None:
            fail_on_quota = args.fail_on_quota
        else:
            env_flag = os.environ.get("LLM_FAIL_ON_QUOTA", "true")
            fail_on_quota = env_flag.strip().lower() in {"true", "1", "yes", "on"}

        # Create page-based runner (this is now the default and only mode)
        runner = PageBasedProofreaderRunner(
            llm_service,
            state,
            pages_per_batch=args.pages_per_batch,
            max_retries=args.max_retries,
            fail_on_quota=fail_on_quota,
        )

        # Set config parameters for the run
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
        print(f"  Total pages: {summary['total_pages']}")
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


def emit_batch_payloads(parsed_args: argparse.Namespace) -> int:
    """Emit batch payloads to files for manual testing.

    This mode loads issues, creates batches, builds prompts, and writes them
    to data/batch_payloads/ as JSON files. Useful for manually submitting to
    provider batch consoles.
    """
    import json

    from .page_batcher import iter_page_batches
    from .page_data_loader import load_page_based_documents
    from .prompt_factory import build_page_prompts

    print("Emitting batch payloads (not calling LLM)...")

    try:
        documents_root = Path("Documents")
        existing_report = Path("Documents/language-check-report.csv")

        document_metadata = load_page_based_documents(
            documents_root,
            existing_report if existing_report.exists() else None,
            subjects=set(parsed_args.subjects) if parsed_args.subjects else None,
            documents=set(parsed_args.documents) if parsed_args.documents else None,
        )
    except Exception as e:
        print(f"Error loading issues: {e}", file=sys.stderr)
        return 1

    if not document_metadata:
        print("No documents found matching the filters")
        return 0

    output_dir = Path("data/batch_payloads")
    output_dir.mkdir(parents=True, exist_ok=True)

    payload_count = 0

    for key, metadata in document_metadata.items():
        markdown_path = metadata["markdown_path"]

        for batch in iter_page_batches(
            metadata,
            parsed_args.pages_per_batch,
            markdown_path,
            subject=key.subject,
            filename=key.filename,
        ):
            prompts = build_page_prompts(batch)

            # Determine system and user parts for the payload; keep 'prompts'
            # for backward compatibility but also expose explicit keys.
            if len(prompts) > 1:
                system_text = prompts[0]
                user_prompts = prompts[1:]
            else:
                system_text = ""
                user_prompts = prompts

            # Create payload file
            payload = {
                "subject": batch.subject,
                "filename": batch.filename,
                "batch_index": batch.index,
                "page_range": {
                    "start": batch.page_range[0],
                    "end": batch.page_range[1],
                },
                "page_count": len(batch.page_context),
                "prompts": prompts,
                "system": system_text,
                "user": user_prompts,
            }

            # Safe filename
            safe_subject = batch.subject.replace("/", "-")
            safe_filename = batch.filename.replace("/", "-").replace(".md", "")
            output_file = (
                output_dir / f"{safe_subject}_{safe_filename}_batch{batch.index}.json"
            )

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            print(f"  Wrote {output_file}")
            payload_count += 1

    print(f"\nEmitted {payload_count} batch payload(s) to {output_dir}")
    return 0


def emit_prompts(parsed_args: argparse.Namespace) -> int:
    """Emit prompts as plain-text files for AI studio testing.

    For each batch this writes a system file (if present) and a user file.
    """
    from .page_batcher import iter_page_batches
    from .page_data_loader import load_page_based_documents
    from .prompt_factory import build_page_prompts

    print("Emitting prompts (plain text)...")

    try:
        documents_root = Path("Documents")
        existing_report = Path("Documents/language-check-report.csv")

        document_metadata = load_page_based_documents(
            documents_root,
            existing_report if existing_report.exists() else None,
            subjects=set(parsed_args.subjects) if parsed_args.subjects else None,
            documents=set(parsed_args.documents) if parsed_args.documents else None,
        )
    except Exception as e:
        print(f"Error loading issues: {e}", file=sys.stderr)
        return 1

    if not document_metadata:
        print("No documents found matching the filters")
        return 0

    output_dir = Path("data/prompt_payloads")
    output_dir.mkdir(parents=True, exist_ok=True)

    file_count = 0

    for key, metadata in document_metadata.items():
        markdown_path = metadata["markdown_path"]

        for batch in iter_page_batches(
            metadata,
            parsed_args.pages_per_batch,
            markdown_path,
            subject=key.subject,
            filename=key.filename,
        ):
            prompts = build_page_prompts(batch)

            # System prompt is optional
            system_text = prompts[0] if len(prompts) > 1 else ""
            user_prompts = prompts[1:] if len(prompts) > 1 else prompts

            safe_subject = batch.subject.replace("/", "-")
            safe_filename = batch.filename.replace("/", "-").replace(".md", "")

            # Use a simple plain-text format: one file per role
            if system_text:
                system_file = (
                    output_dir
                    / f"{safe_subject}_{safe_filename}_batch{batch.index}_system.txt"
                )
                system_file.write_text(system_text, encoding="utf-8")
                print(f"  Wrote {system_file}")
                file_count += 1

            # Write user prompt(s). If multiple prompts, join them with a separator.
            user_text = "\n\n---\n\n".join(user_prompts)
            user_file = (
                output_dir
                / f"{safe_subject}_{safe_filename}_batch{batch.index}_user.txt"
            )
            user_file.write_text(user_text, encoding="utf-8")
            print(f"  Wrote {user_file}")
            file_count += 1

    print(f"\nEmitted {file_count} prompt file(s) to {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
