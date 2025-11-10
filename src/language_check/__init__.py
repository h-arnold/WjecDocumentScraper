"""Language check package exports.

This package exposes the key helpers used by other parts of the project
so callers can import from ``src.language_check``.
"""

from __future__ import annotations

from .language_check import (
    build_language_tool,
    check_document,
    check_single_document,
    derive_subject_from_path,
    iter_markdown_documents,
    build_report_markdown,
    build_report_csv,
    run_language_checks,
)
from .language_check_config import DEFAULT_DISABLED_RULES, DEFAULT_IGNORED_WORDS

__all__ = [
    "build_language_tool",
    "check_document",
    "check_single_document",
    "derive_subject_from_path",
    "iter_markdown_documents",
    "build_report_markdown",
    "build_report_csv",
    "run_language_checks",
    "DEFAULT_DISABLED_RULES",
    "DEFAULT_IGNORED_WORDS",
]
