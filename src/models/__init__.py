"""Public model exports for the project.

Keep the :mod:`src` namespace clean — tests and other modules should import
``from src.models import LlmLanguageIssue, ErrorCategory``.
"""
from __future__ import annotations

from .issue import LlmLanguageIssue
from .enums import ErrorCategory

__all__ = ["LlmLanguageIssue", "ErrorCategory"]
