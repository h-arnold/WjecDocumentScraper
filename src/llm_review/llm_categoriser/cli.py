"""Command-line interface for the LLM categoriser.

Provides options for filtering, batch configuration, state management, and provider selection.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from src.llm.provider_registry import create_provider_chain
from src.llm.service import LLMService

from .runner import CategoriserRunner
from .state import CategoriserState


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Categorise LanguageTool issues using LLMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all issues in the default report
  python -m src.llm_review.llm_categoriser

  # Process specific subjects
  python -m src.llm_review.llm_categoriser --subjects "Art and Design" Geography

  # Process specific documents
  python -m src.llm_review.llm_categoriser --documents gcse-geography.md

  # Force reprocessing (ignore state)
  python -m src.llm_review.llm_categoriser --force

  # Use a different batch size
  python -m src.llm_review.llm_categoriser --batch-size 5

  # Dry run (validate data loading only)
  python -m src.llm_review.llm_categoriser --dry-run

Environment Variables:
  LLM_CATEGORISER_BATCH_SIZE     Default batch size (default: 10)
  LLM_CATEGORISER_MAX_RETRIES    Maximum retries (default: 2)
  LLM_CATEGORISER_STATE_FILE     State file path (default: data/llm_categoriser_state.json)
  GEMINI_MIN_REQUEST_INTERVAL    Min seconds between Gemini requests (default: 0)
  LLM_PRIMARY                    Primary LLM provider (default: gemini)
  LLM_FALLBACK                   Fallback providers (comma-separated)
        """,
    )
    
    # Input/output options
    parser.add_argument(
        "--from-report",
        type=Path,
        default=Path("Documents/language-check-report.csv"),
        help="Path to language-check-report.csv (default: Documents/language-check-report.csv)",
    )
    
    # Filtering options
    parser.add_argument(
        "--subjects",
        nargs="+",
        help="Filter by subject names (case-insensitive)",
    )
    
    parser.add_argument(
        "--documents",
        nargs="+",
        help="Filter by document filenames (case-insensitive)",
    )
    
    # Batch configuration
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.environ.get("LLM_CATEGORISER_BATCH_SIZE", "10")),
        help="Number of issues per batch (default: 10 or LLM_CATEGORISER_BATCH_SIZE)",
    )
    
    parser.add_argument(
        "--max-retries",
        type=int,
        default=int(os.environ.get("LLM_CATEGORISER_MAX_RETRIES", "2")),
        help="Maximum validation retries per batch (default: 2 or LLM_CATEGORISER_MAX_RETRIES)",
    )
    
    # State management
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path(os.environ.get("LLM_CATEGORISER_STATE_FILE", "data/llm_categoriser_state.json")),
        help="State file path (default: data/llm_categoriser_state.json or LLM_CATEGORISER_STATE_FILE)",
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess all batches (ignore state)",
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
        "--dry-run",
        action="store_true",
        help="Validate data loading only (don't call LLM)",
    )
    
    parser.add_argument(
        "--use-batch-endpoint",
        action="store_true",
        help="Use batch endpoint if provider supports it (not implemented yet)",
    )
    
    parser.add_argument(
        "--emit-batch-payload",
        action="store_true",
        help="Write batch payloads to data/batch_payloads/ and exit (for manual testing)",
    )
    
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    """Main entry point for the CLI.
    
    Args:
        args: Command-line arguments (defaults to sys.argv[1:])
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    parsed_args = parse_args(args)
    
    # Validate report file exists
    if not parsed_args.from_report.exists():
        print(f"Error: Report file not found: {parsed_args.from_report}", file=sys.stderr)
        return 1
    
    # Handle --emit-batch-payload mode
    if parsed_args.emit_batch_payload:
        return emit_batch_payloads(parsed_args)
    
    # Create LLM service
    try:
        providers = create_provider_chain(
            system_prompt="",  # System prompt is embedded in the template
            filter_json=True,
            dotenv_path=parsed_args.dotenv,
            primary=parsed_args.provider,
        )
        
        if not providers:
            print("Error: No LLM providers configured", file=sys.stderr)
            return 1
        
        print(f"Using LLM provider(s): {[p.name for p in providers]}")
        
        llm_service = LLMService(providers)
        
    except Exception as e:
        print(f"Error creating LLM service: {e}", file=sys.stderr)
        return 1
    
    # Get minimum request interval from environment
    try:
        min_interval = float(os.environ.get("GEMINI_MIN_REQUEST_INTERVAL", "0"))
    except ValueError:
        min_interval = 0.0
    
    # Create state manager
    state = CategoriserState(parsed_args.state_file)
    
    # Create runner
    runner = CategoriserRunner(
        llm_service=llm_service,
        state=state,
        batch_size=parsed_args.batch_size,
        max_retries=parsed_args.max_retries,
        min_request_interval=min_interval,
    )
    
    # Run categorisation
    try:
        subjects_set = set(parsed_args.subjects) if parsed_args.subjects else None
        documents_set = set(parsed_args.documents) if parsed_args.documents else None
        
        runner.run(
            parsed_args.from_report,
            subjects=subjects_set,
            documents=documents_set,
            force=parsed_args.force,
            dry_run=parsed_args.dry_run,
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


def emit_batch_payloads(parsed_args: argparse.Namespace) -> int:
    """Emit batch payloads to files for manual testing.
    
    This mode loads issues, creates batches, builds prompts, and writes them
    to data/batch_payloads/ as JSON files. Useful for manually submitting to
    provider batch consoles.
    """
    import json
    from .data_loader import load_issues
    from .batcher import iter_batches
    from .prompt_factory import build_prompts
    
    print("Emitting batch payloads (not calling LLM)...")
    
    try:
        grouped_issues = load_issues(
            parsed_args.from_report,
            subjects=set(parsed_args.subjects) if parsed_args.subjects else None,
            documents=set(parsed_args.documents) if parsed_args.documents else None,
        )
    except Exception as e:
        print(f"Error loading issues: {e}", file=sys.stderr)
        return 1
    
    if not grouped_issues:
        print("No issues found matching the filters")
        return 0
    
    output_dir = Path("data/batch_payloads")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    payload_count = 0
    
    for key, issues in grouped_issues.items():
        markdown_path = Path("Documents") / key.subject / "markdown" / key.filename
        
        for batch in iter_batches(
            issues,
            parsed_args.batch_size,
            markdown_path,
            subject=key.subject,
            filename=key.filename,
        ):
            prompts = build_prompts(batch)
            
            # Create payload file
            payload = {
                "subject": batch.subject,
                "filename": batch.filename,
                "batch_index": batch.index,
                "issue_count": len(batch.issues),
                "prompts": prompts,
            }
            
            # Safe filename
            safe_subject = batch.subject.replace("/", "-")
            safe_filename = batch.filename.replace("/", "-").replace(".md", "")
            output_file = output_dir / f"{safe_subject}_{safe_filename}_batch{batch.index}.json"
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            
            print(f"  Wrote {output_file}")
            payload_count += 1
    
    print(f"\nEmitted {payload_count} batch payload(s) to {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
