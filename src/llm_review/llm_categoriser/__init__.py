"""LLM categoriser for language tool issues.

This package orchestrates the categorisation of LanguageTool issues using LLMs.
It batches issues per document, renders prompts with page context, validates
responses, and persists the results as JSON files.

Main entry point:
    python -m src.llm_review.llm_categoriser

Key modules:
    - data_loader: Parse CSV and group issues by DocumentKey
    - batcher: Chunk issues and fetch page context
    - prompt_factory: Render prompts with context
    - runner: Orchestrate workflow with retries
    - persistence: Atomic JSON file writes
    - state: Track completed batches for resume support
    - cli: Command-line interface
"""

from __future__ import annotations

__all__ = [
    "data_loader",
    "batcher",
    "prompt_factory",
    "runner",
    "persistence",
    "state",
    "cli",
]
