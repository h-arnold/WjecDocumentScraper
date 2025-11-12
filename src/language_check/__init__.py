"""Language check package exports.

This package exposes the key helpers used by other parts of the project
so callers can import from ``src.language_check``.
"""

from __future__ import annotations

from .language_check import (
    build_language_tool,
    build_language_tools_for_subject,
    check_document,
    check_single_document,
    derive_subject_from_path,
    get_languages_for_subject,
    iter_markdown_documents,
    run_language_checks,
)
from .report_utils import build_report_csv, build_report_markdown
from .language_check_config import DEFAULT_DISABLED_RULES, DEFAULT_IGNORED_WORDS

__all__ = [
    "build_language_tool",
    "build_language_tools_for_subject",
    "check_document",
    "check_single_document",
    "derive_subject_from_path",
    "get_languages_for_subject",
    "iter_markdown_documents",
    "build_report_markdown",
    "build_report_csv",
    "run_language_checks",
    "DEFAULT_DISABLED_RULES",
    "DEFAULT_IGNORED_WORDS",
]
