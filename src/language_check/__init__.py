"""Language check package exports.

This package exposes the key helpers used by other parts of the project
so callers can import from ``src.language_check``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    # These imports are only for type checkers — they are not executed at runtime
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
    from .language_check_config import DEFAULT_DISABLED_RULES, DEFAULT_IGNORED_WORDS
    from .language_tool_manager import LanguageToolManager
    from .report_utils import build_report_csv, build_report_markdown

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
    "LanguageToolManager",
    "DEFAULT_DISABLED_RULES",
    "DEFAULT_IGNORED_WORDS",
]

_LAZY_EXPORTS = {
    # attribute -> (module, attribute)
    "build_language_tool": (".language_check", "build_language_tool"),
    "build_language_tools_for_subject": (
        ".language_check",
        "build_language_tools_for_subject",
    ),
    "check_document": (".language_check", "check_document"),
    "check_single_document": (".language_check", "check_single_document"),
    "derive_subject_from_path": (".language_check", "derive_subject_from_path"),
    "get_languages_for_subject": (".language_check", "get_languages_for_subject"),
    "iter_markdown_documents": (".language_check", "iter_markdown_documents"),
    "run_language_checks": (".language_check", "run_language_checks"),
    "LanguageToolManager": (".language_tool_manager", "LanguageToolManager"),
    "build_report_csv": (".report_utils", "build_report_csv"),
    "build_report_markdown": (".report_utils", "build_report_markdown"),
    "DEFAULT_DISABLED_RULES": (".language_check_config", "DEFAULT_DISABLED_RULES"),
    "DEFAULT_IGNORED_WORDS": (".language_check_config", "DEFAULT_IGNORED_WORDS"),
}


def __getattr__(name: str):
    """Lazily import and return exported attributes.

    This avoids importing submodules until actually used, which stops import
    order problems when multiple components import from ``src.language_check``.
    """

    if name in _LAZY_EXPORTS:
        module_name, attr = _LAZY_EXPORTS[name]
        from importlib import import_module

        mod = import_module(f"src.language_check{module_name}")
        value = getattr(mod, attr)
        globals()[name] = value
        return value
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_EXPORTS.keys()))
