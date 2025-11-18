from __future__ import annotations

import argparse
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path

from src.llm.provider_registry import create_provider_chain
from src.llm.service import LLMService

from .config import ReviewConfiguration
from .review_runner import ReviewRunner
from .state_manager import StateManager


class BaseCLI(ABC):
    """Base CLI for LLM review tools."""

    def __init__(self, description: str, env_prefix: str):
        self.description = description
        self.env_prefix = env_prefix
        self.parser = argparse.ArgumentParser(
            description=description,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        self._setup_args()

    def _setup_args(self) -> None:
        """Setup common arguments."""
        # Input/output options
        self.parser.add_argument(
            "--from-report",
            type=Path,
            help="Path to input CSV report",
        )

        # Filtering
        self.parser.add_argument(
            "--subjects",
            nargs="+",
            help="Filter by subject(s) (case-insensitive)",
        )
        self.parser.add_argument(
            "--documents",
            nargs="+",
            help="Filter by document filename(s)",
        )

        # Batch configuration
        self.parser.add_argument(
            "--batch-size",
            type=int,
            help=f"Number of issues per batch (default: env {self.env_prefix}_BATCH_SIZE or 10)",
        )
        self.parser.add_argument(
            "--max-retries",
            type=int,
            help=(
                f"Maximum retries for failed validation "
                f"(default: env {self.env_prefix}_MAX_RETRIES or 2)"
            ),
        )

        # Execution control
        self.parser.add_argument(
            "--force",
            action="store_true",
            help="Force reprocessing of already completed batches",
        )
        self.parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate data loading and batching without calling LLM",
        )

        # LLM Provider options
        self.parser.add_argument(
            "--provider",
            help="Primary LLM provider to use (overrides LLM_PRIMARY env var)",
        )

        # Add batch subparsers hook
        self.subparsers = self.parser.add_subparsers(
            dest="command", help="Command to run"
        )
        self._add_batch_commands(self.subparsers)

        # Allow subclasses to add more args
        self._add_extra_args()

    def _add_extra_args(self) -> None:
        """Hook for subclasses to add extra arguments."""
        pass

    def _add_batch_commands(self, subparsers: argparse._SubParsersAction) -> None:
        """Hook for subclasses to add batch commands."""
        pass

    def parse_args(self, args: list[str] | None = None) -> argparse.Namespace:
        return self.parser.parse_args(args)

    def run(self, args: list[str] | None = None) -> int:
        parsed_args = self.parse_args(args)

        # Handle batch commands if any
        if parsed_args.command:
            return self._handle_batch_command(parsed_args)

        return self._run_sync(parsed_args)

    def _run_sync(self, args: argparse.Namespace) -> int:
        """Run synchronous workflow."""
        config = self._create_config(args)

        # Setup LLM service
        llm_service = self._create_llm_service(args)

        # Setup state manager
        state = StateManager(config.state_file)

        # Create runner
        runner = self._create_runner(llm_service, state, config)

        # Run
        try:
            summary = runner.run(force=args.force, dry_run=args.dry_run)
            if summary["total_documents"] == 0:
                print("No documents processed.")
                return 0
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    def _create_llm_service(self, args: argparse.Namespace) -> LLMService:
        """Create LLM service."""
        # Determine provider
        provider = args.provider or os.environ.get("LLM_PRIMARY", "gemini")

        # Create provider chain
        # Note: create_provider_chain expects specific args, we might need to adapt
        # It reads from env vars mostly.

        # We need to pass system prompt. Subclass should provide it.
        system_prompt = self._get_system_prompt()

        providers = create_provider_chain(
            primary=provider,
            system_prompt=system_prompt,
            filter_json=True,  # Usually we want JSON
        )

        return LLMService(providers)

    @abstractmethod
    def _create_config(self, args: argparse.Namespace) -> ReviewConfiguration:
        """Create configuration object."""
        pass

    @abstractmethod
    def _create_runner(
        self, llm_service: LLMService, state: StateManager, config: ReviewConfiguration
    ) -> ReviewRunner:
        """Create runner instance."""
        pass

    @abstractmethod
    def _get_system_prompt(self) -> str | Path:
        """Get system prompt for LLM."""
        pass

    @abstractmethod
    def _handle_batch_command(self, args: argparse.Namespace) -> int:
        """Handle batch commands."""
        pass
