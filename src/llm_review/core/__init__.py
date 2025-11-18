"""Generic core components for LLM review passes.

This module provides reusable infrastructure for implementing multiple
review passes (categorisation, fact-checking, style validation, etc.).
"""

from .batcher import Batch, iter_batches
from .document_loader import load_issues
from .state_manager import StateManager as StateManager

__all__ = [
    "load_issues",
    "Batch",
    "iter_batches",
    "StateManager",
]
