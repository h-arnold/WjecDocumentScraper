"""Language quality checks for downloaded Markdown documents.

This module scans the generated subject folders, runs spelling and grammar
checks using a British English dictionary, and writes a Markdown report that
summarises the findings per subject and per document.
"""

from __future__ import annotations

import argparse
import csv
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from language_tool_python.utils import LanguageToolError

from src.models import PassCode
from src.utils.report_utils import build_report_csv, build_report_markdown

from .language_check_config import DEFAULT_DISABLED_RULES, DEFAULT_IGNORED_WORDS
from .language_issue import LanguageIssue
from .language_tool_manager import LanguageToolManager
from .language_tool_patch import apply_post_request_patch
from .page_utils import build_page_number_map, find_page_markers

# Apply POST request patch to handle large documents (>300KB)
# The default language_tool_python uses GET requests which fail for large documents
apply_post_request_patch()

LOGGER = logging.getLogger(__name__)

MAX_PAGES_PER_CHUNK = 50


def get_languages_for_subject(subject: str) -> list[str]:
    """Determine which languages to check for a given subject.

    Args:
            subject: Subject name (e.g., "French", "German", "Computer-Science")

    Returns:
            List describing which language(s) to check; currently always en-GB
    """
    return ["en-GB"]


# Transient errors that should trigger a retry
TRANSIENT_ERRORS = (
    ConnectionError,
    ConnectionResetError,
    ConnectionAbortedError,
    ConnectionRefusedError,
    BrokenPipeError,
    TimeoutError,
    OSError,  # Covers socket.error and other OS-level issues
)

# language_tool_python wraps connection-level errors in LanguageToolError
# (see server.py). Treat that as transient so retries are attempted when the
# local LanguageTool server returns network-related failures.
TRANSIENT_ERRORS = TRANSIENT_ERRORS + (LanguageToolError,)


def _retry_with_backoff(
    func: Any,
    func_arg: Any,
    max_retries: int = 3,
    base_delay: float = 5.0,
    max_delay: float = 60.0,
) -> Any:
    """Execute a function with exponential backoff retry logic.

    Args:
            func: The function to call (e.g., tool.check)
            func_arg: The argument to pass to func (e.g., text)
            max_retries: Maximum number of retry attempts (total attempts = max_retries + 1)
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds

    Returns:
            The return value of func

    Raises:
            The last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return func(func_arg)
        except TRANSIENT_ERRORS as exc:
            last_exception = exc

            if attempt >= max_retries:
                # No more retries; re-raise the exception
                LOGGER.error(
                    "Language check failed after %d attempt(s): %s",
                    attempt + 1,
                    exc,
                )
                raise

            # Calculate delay with exponential backoff
            delay = base_delay * (2**attempt)
            # Add a small random jitter to avoid a thundering herd
            jitter = random.uniform(0.75, 1.25)
            delay = min(delay * jitter, max_delay)  # Cap at max_delay
            delay = min(delay, max_delay)  # Cap at max_delay

            LOGGER.warning(
                "Language check attempt %d failed (transient error: %s); "
                "retrying in %.1f second(s)...",
                attempt + 1,
                type(exc).__name__,
                delay,
            )
            time.sleep(delay)

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic completed without returning or raising")


@dataclass
class DocumentReport:
    """Compilation of issues for a specific document."""

    subject: str
    path: Path
    issues: list[LanguageIssue]


@dataclass
class DocumentChunk:
    """Represents a slice of a document bounded by page markers."""

    text: str
    start_page: int | None
    end_page: int | None


def _split_text_by_page_limit(
    text: str, max_pages: int = MAX_PAGES_PER_CHUNK
) -> list[DocumentChunk]:
    """Split ``text`` into chunks that contain at most ``max_pages`` pages."""

    if max_pages <= 0:
        return [DocumentChunk(text=text, start_page=None, end_page=None)]

    markers = find_page_markers(text)
    if not markers:
        return [DocumentChunk(text=text, start_page=None, end_page=None)]

    chunks: list[DocumentChunk] = []
    total_markers = len(markers)
    start_idx = 0

    while start_idx < total_markers:
        chunk_start_marker = markers[start_idx]
        end_marker_idx = min(total_markers - 1, start_idx + max_pages - 1)
        chunk_end_marker = markers[end_marker_idx]

        start_pos = 0 if start_idx == 0 else chunk_start_marker.position
        next_marker_idx = start_idx + max_pages
        end_pos = (
            markers[next_marker_idx].position
            if next_marker_idx < total_markers
            else len(text)
        )

        chunk_text = text[start_pos:end_pos]
        chunks.append(
            DocumentChunk(
                text=chunk_text,
                start_page=chunk_start_marker.page_number,
                end_page=chunk_end_marker.page_number,
            )
        )
        start_idx += max_pages

    # If the document contains leading content before the first marker, it is
    # already included in the first chunk (start_pos defaults to 0).
    return chunks


def _filter_matches(matches: list[Any], words_to_ignore: set[str]) -> list[Any]:
    """Filter matches whose tokens are configured to be ignored."""

    if not words_to_ignore:
        return list(matches)

    filtered_matches: list[Any] = []
    for match in matches:
        if hasattr(match, "matchedText"):
            original_text = str(getattr(match, "matchedText", "")).strip()
            if original_text:
                letters = "".join(ch for ch in original_text if ch.isalpha())
                is_acronym_form = False
                if letters:
                    if letters.isupper() or letters.rstrip("s").isupper():
                        is_acronym_form = True

                if is_acronym_form:
                    if (
                        letters in words_to_ignore
                        or letters.rstrip("s") in words_to_ignore
                    ):
                        continue
                else:
                    if original_text in words_to_ignore:
                        continue
        filtered_matches.append(match)

    return filtered_matches


def _collect_disabled_rules(additional_rules: set[str] | None) -> set[str]:
    """Merge default disabled rules with any additional entries."""
    rules = set(DEFAULT_DISABLED_RULES)
    if additional_rules:
        rules.update(additional_rules)
    return rules


def _collect_ignored_words(extra_words: set[str] | None) -> set[str]:
    """Return the union of default ignored words and any extras."""
    words = set(DEFAULT_IGNORED_WORDS)
    if extra_words:
        words.update(extra_words)
    return words


def _create_language_tool_manager(
    *,
    ignored_words: set[str] | None = None,
    disabled_rules: set[str] | None = None,
) -> LanguageToolManager:
    """Instantiate a shared LanguageToolManager for the current run."""
    return LanguageToolManager(
        ignored_words=_collect_ignored_words(ignored_words),
        disabled_rules=_collect_disabled_rules(disabled_rules),
        logger=LOGGER,
    )


def build_language_tool(
    language: str,
    *,
    disabled_rules: set[str] | None = None,
    ignored_words: set[str] | None = None,
) -> Any:
    """Instantiate a LanguageTool checker for the requested language."""
    manager = _create_language_tool_manager(
        ignored_words=ignored_words,
        disabled_rules=disabled_rules,
    )
    return manager.build_tool(language)


def iter_markdown_documents(
    root: Path, *, subject_path: Path | None = None
) -> list[tuple[str, Path]]:
    """Return a sorted list of (subject, document path) pairs under ``root``."""

    documents: list[tuple[str, Path]] = []
    if not root.exists():
        return documents

    if subject_path is not None:
        subject_dirs: Iterable[Path] = (subject_path,)
    else:
        subject_dirs = (item for item in root.iterdir() if item.is_dir())

    for subject_dir in sorted(subject_dirs, key=lambda path: path.name.lower()):
        if not subject_dir.is_dir():
            continue
        markdown_dir = subject_dir / "markdown"
        if not markdown_dir.is_dir():
            continue
        for document_path in sorted(markdown_dir.glob("*.md")):
            documents.append((subject_dir.name, document_path))
    return documents


def _highlight_context(context: str, context_offset: int, error_length: int) -> str:
    if not context:
        return ""
    start = max(0, min(len(context), context_offset))
    end = max(start, min(len(context), start + max(error_length, 1)))
    return f"{context[:start]}**{context[start:end]}**{context[end:]}"


def _safe_highlight_context(
    context: str,
    context_offset: int,
    error_length: int,
    *,
    filename: str = "",
    rule_id: str = "",
) -> tuple[str, str]:
    """Safely produce a highlighted context string.

    Returns a tuple: (highlighted_context, context_to_use). If highlighting fails
    the function will return the raw context (and log a warning). If the raw
    context is empty or missing then both values will be set to the
    'ERROR FETCHING CONTEXT' placeholder.
    """

    try:
        highlighted = _highlight_context(context, context_offset, error_length)
    except Exception:
        LOGGER.exception(
            "Failed to produce highlighted context for %s (rule=%s)",
            filename,
            rule_id,
        )
        if context:
            # Fallback to the raw context text
            return (context, context)
        # No context available — return a descriptive placeholder
        return ("ERROR FETCHING CONTEXT", "ERROR FETCHING CONTEXT")

    # If highlighting succeeded but returned an empty string, fall back
    if not highlighted:
        if context:
            LOGGER.warning(
                "Highlight helper returned empty string for %s; using raw context instead",
                filename,
            )
            return (context, context)
        LOGGER.warning(
            "No context provided for %s — using ERROR FETCHING CONTEXT placeholder",
            filename,
        )
        return ("ERROR FETCHING CONTEXT", "ERROR FETCHING CONTEXT")

    return (highlighted, context)


def _get_page_number_for_match(
    match: object, text: str, page_map: dict[int, int]
) -> int | None:
    """Determine the page number for a language issue match.

    Args:
            match: The LanguageTool match object
            text: The full document text
            page_map: Map from character position to page number (from page_utils.build_page_number_map)

    Returns:
            The page number where the match occurs, or None if not found
    """
    # Try to get the offset of the match in the text
    offset = getattr(match, "offset", None)

    if offset is None:
        # Try to find the match using context
        context = getattr(match, "context", "")
        if context:
            # Search for the context in the text to find the offset
            context_pos = text.find(context)
            if context_pos >= 0:
                # Add the offset within the context
                context_offset = int(getattr(match, "offsetInContext", 0))
                offset = context_pos + context_offset

    if offset is not None and offset in page_map:
        return page_map[offset]

    return None


def _make_issue(
    match: object, filename: str, text: str = "", page_map: dict[int, int] | None = None
) -> LanguageIssue:
    rule_id = getattr(match, "ruleId", "UNKNOWN") or "UNKNOWN"
    message = str(getattr(match, "message", "")).strip()
    issue_type = getattr(match, "ruleIssueType", "unknown") or "unknown"
    replacements = list(getattr(match, "replacements", []) or [])
    context = getattr(match, "context", "") or ""

    # Safely convert offset/length to integers; LanguageTool or mocks
    # may provide None or unexpected values.
    try:
        context_offset = int(getattr(match, "offsetInContext", 0) or 0)
    except Exception:
        LOGGER.warning(
            "Invalid offsetInContext for %s (rule=%s) — defaulting to 0",
            filename,
            rule_id,
        )
        context_offset = 0

    try:
        error_length = int(getattr(match, "errorLength", 0) or 0)
    except Exception:
        LOGGER.warning(
            "Invalid errorLength for %s (rule=%s) — defaulting to 0",
            filename,
            rule_id,
        )
        error_length = 0

    highlighted_context, context = _safe_highlight_context(
        context, context_offset, error_length, filename=filename, rule_id=rule_id
    )

    # Extract the matched issue text from the context
    issue = (
        context[context_offset : context_offset + error_length]
        if error_length > 0
        else ""
    )

    # Determine page number
    page_number = None
    if page_map is not None and text:
        page_number = _get_page_number_for_match(match, text, page_map)

    return LanguageIssue(
        filename=filename,
        rule_id=rule_id,
        message=message,
        issue_type=issue_type,
        replacements=replacements,
        context=context,
        highlighted_context=highlighted_context,
        issue=issue,
        page_number=page_number,
        pass_code=PassCode.LT,
    )


def check_document(
    document_path: Path,
    subject: str,
    tool: Any | list[Any],
    *,
    ignored_words: set[str] | None = None,
) -> DocumentReport:
    """Run language checks on a single Markdown document.

    Args:
            document_path: Path to the Markdown file
            subject: Subject name for the report
            tool: LanguageTool instance or list of LanguageTool instances
                  When a list is provided, all tools are run and results are merged
            ignored_words: Additional words to filter from results
    """

    text = document_path.read_text(encoding="utf-8")
    filename = document_path.name

    chunks = _split_text_by_page_limit(text, MAX_PAGES_PER_CHUNK)
    if len(chunks) > 1:
        LOGGER.info(
            "Splitting %s into %d chunk(s) (<= %d pages each)",
            filename,
            len(chunks),
            MAX_PAGES_PER_CHUNK,
        )

    # Merge ignored words with defaults.
    # NOTE: matching is case-sensitive — we use the words as provided in the
    # configuration because many entries are case-specific (proper nouns,
    # acronyms, product names, etc.).
    words_to_ignore = _collect_ignored_words(ignored_words)

    # Normalize tool to a list for uniform processing
    tools = [tool] if not isinstance(tool, list) else tool

    issues: list[LanguageIssue] = []
    failure_records: list[tuple[str, Exception, bool]] = []
    successful_check = False

    for chunk_index, chunk in enumerate(chunks, start=1):
        chunk_text = chunk.text
        chunk_page_map = build_page_number_map(chunk_text)
        chunk_matches: list[Any] = []
        chunk_successful = False
        chunk_failure_records: list[tuple[str, Exception, bool]] = []

        for tool_instance in tools:
            language_code = getattr(tool_instance, "language", None)
            language_label = language_code or getattr(tool_instance, "lang", "unknown")
            try:
                matches = _retry_with_backoff(
                    tool_instance.check, chunk_text, max_retries=3, base_delay=3.0
                )
                chunk_successful = True
                chunk_matches.extend(matches or [])
            except TRANSIENT_ERRORS as exc:
                LOGGER.exception(
                    "Language check failed for %s (language: %s) after all retries",
                    document_path,
                    language_label,
                )
                chunk_failure_records.append((str(language_label), exc, True))
                continue
            except Exception as exc:
                LOGGER.exception(
                    "Language check failed for %s (language: %s)",
                    document_path,
                    language_label,
                )
                chunk_failure_records.append((str(language_label), exc, False))
                continue

        failure_records.extend(chunk_failure_records)

        if not chunk_successful:
            continue

        successful_check = True
        filtered_matches = _filter_matches(chunk_matches, words_to_ignore)
        issues.extend(
            _make_issue(match, filename, chunk_text, chunk_page_map)
            for match in filtered_matches
        )

        if len(chunks) > 1:
            LOGGER.debug(
                "Completed chunk %d/%d for %s (pages %s-%s)",
                chunk_index,
                len(chunks),
                filename,
                chunk.start_page if chunk.start_page is not None else "?",
                chunk.end_page if chunk.end_page is not None else "?",
            )

    if not successful_check and failure_records:
        issues = [
            LanguageIssue(
                filename=filename,
                rule_id="CHECK_FAILURE",
                message=(
                    f"Language check failed for language '{language}'"
                    f" due to {'connection error' if is_transient else 'error'}: {exc}"
                ),
                issue_type="error",
                replacements=[],
                context="ERROR FETCHING CONTEXT",
                highlighted_context="ERROR FETCHING CONTEXT",
                issue="",
                pass_code=PassCode.LT,
            )
            for language, exc, is_transient in failure_records
        ]
        return DocumentReport(subject=subject, path=document_path, issues=issues)

    if failure_records:
        for language, exc, is_transient in failure_records:
            issues.append(
                LanguageIssue(
                    filename=filename,
                    rule_id="CHECK_PARTIAL_FAILURE",
                    message=(
                        f"Language check for language '{language}' experienced "
                        f"a {'connection error' if is_transient else 'runtime error'}: {exc}"
                    ),
                    issue_type="warning",
                    replacements=[],
                    context="ERROR FETCHING CONTEXT",
                    highlighted_context="ERROR FETCHING CONTEXT",
                    issue="",
                    pass_code=PassCode.LT,
                )
            )

    return DocumentReport(subject=subject, path=document_path, issues=issues)


def derive_subject_from_path(document_path: Path) -> str:
    """Infer the subject directory name from a Markdown document path."""

    if document_path.parent.name == "markdown" and document_path.parent.parent.name:
        return document_path.parent.parent.name
    return document_path.parent.name


def build_language_tools_for_subject(
    subject: str,
    *,
    disabled_rules: set[str] | None = None,
    ignored_words: set[str] | None = None,
    manager: LanguageToolManager | None = None,
) -> list[Any]:
    """Build LanguageTool instances for a subject.

    Args:
            subject: Subject name (e.g., "French", "German", "Computer-Science")
            disabled_rules: Additional rules to disable
            ignored_words: Additional words to add to the dictionary ignore list
            manager: Optional preconfigured LanguageToolManager (used when provided)

    Returns:
            List of LanguageTool instances
    """
    languages = get_languages_for_subject(subject)
    tool_manager = manager or _create_language_tool_manager(
        ignored_words=ignored_words,
        disabled_rules=disabled_rules,
    )

    # For language subjects, add language-specific extra disabled rules
    morfologik_rule = "MORFOLOGIK_RULE_EN_GB"
    extra_disabled: set[str] | None = None
    if subject in {"French", "German", "Spanish"}:
        extra_disabled = {morfologik_rule}

    tools: list[Any] = []
    for language in languages:
        tool = tool_manager.build_tool(
            language,
            extra_disabled_rules=extra_disabled,
        )
        tools.append(tool)
        LOGGER.info(
            "Created LanguageTool for language: %s (subject: %s)", language, subject
        )
    return tools


def check_single_document(
    document_path: Path,
    *,
    subject: Optional[str] = None,
    language: str = "en-GB",
    tool: Any | None = None,
    disabled_rules: set[str] | None = None,
    ignored_words: set[str] | None = None,
) -> DocumentReport:
    """Convenience wrapper that runs checks for a single document.

    For language subjects (French, German), automatically checks with both
    the subject language and English. The ``language`` parameter is kept for
    backward compatibility but is ignored because language detection is derived
    from ``subject``.

    Args:
            document_path: Markdown document to check.
            subject: Optional subject name. When omitted, derived from the path.
            language: Language code (deprecated; ignored - language now auto-detected).
            tool: Optional pre-configured LanguageTool instance (bypasses auto-detection).
            disabled_rules: Additional LanguageTool rules to disable.
            ignored_words: Additional words to ignore during checking.
    """

    resolved_subject = subject or derive_subject_from_path(document_path)

    # If tool is provided, use it directly (backward compatibility)
    if tool is not None:
        try:
            return check_document(
                document_path, resolved_subject, tool, ignored_words=ignored_words
            )
        finally:
            # Don't close externally provided tools
            pass

    # Otherwise, create tools based on subject using the manager abstraction
    local_manager = _create_language_tool_manager(
        ignored_words=ignored_words,
        disabled_rules=disabled_rules,
    )
    tools = build_language_tools_for_subject(
        resolved_subject,
        disabled_rules=disabled_rules,
        ignored_words=ignored_words,
        manager=local_manager,
    )

    try:
        # If only one tool, pass it directly (not in a list) for backward compatibility
        tool_arg = tools[0] if len(tools) == 1 else tools
        return check_document(
            document_path, resolved_subject, tool_arg, ignored_words=ignored_words
        )
    finally:
        # Close all created tools
        for t in tools:
            if hasattr(t, "close"):
                t.close()


def _run_check_with_logging(
    subject_name: str,
    document_path: Path,
    tool_arg: Any | list[Any],
    ignored_words: set[str] | None,
    running_total: int,
) -> tuple[DocumentReport, int]:
    """Run a check and emit consistent progress logging."""
    LOGGER.info("Checking %s / %s", subject_name, document_path.name)
    report = check_document(
        document_path, subject_name, tool_arg, ignored_words=ignored_words
    )
    running_total += len(report.issues)
    LOGGER.info(
        "Completed %s / %s: %d issue(s) (running total: %d)",
        subject_name,
        document_path.name,
        len(report.issues),
        running_total,
    )
    return report, running_total


def run_language_checks(
    root: Path,
    *,
    report_path: Optional[Path] = None,
    language: str = "en-GB",
    subject: Path | str | None = None,
    document: Path | None = None,
    tool: Any | None = None,
    disabled_rules: set[str] | None = None,
    ignored_words: set[str] | None = None,
) -> Path:
    """Run language checks across all Markdown documents and write a report.

    Args:
            root: Root directory containing subject folders
            report_path: Path to write the Markdown report
            language: Language code (deprecated; retained for backward compatibility and ignored when auto-detecting subjects)
            subject: Subject folder to check
            document: Single document to check
            tool: Pre-configured LanguageTool instance (optional)
            disabled_rules: Set of rule IDs to disable
            ignored_words: Set of words to ignore in spell-checking
    """

    if document is not None:
        document_path = document if document.is_absolute() else (root / document)
        document_path = document_path.resolve()
        if not document_path.is_file():
            raise FileNotFoundError(f"Document not found: {document_path}")
        resolved_subject = subject or derive_subject_from_path(document_path)
        if isinstance(resolved_subject, Path):
            subject_name = resolved_subject.name
        else:
            subject_name = str(resolved_subject)
        documents: list[tuple[str, Path]] = [(subject_name, document_path)]
    else:
        subject_path: Path | None = None
        if subject is not None:
            subject_path = subject if isinstance(subject, Path) else Path(subject)
            if not subject_path.is_absolute():
                subject_path = (root / subject_path).resolve()
            if not subject_path.is_dir():
                raise FileNotFoundError(f"Subject folder not found: {subject_path}")
        documents = iter_markdown_documents(root, subject_path=subject_path)

    if subject is not None and document is not None:
        subject_path = subject if isinstance(subject, Path) else Path(subject)
        if not subject_path.is_absolute():
            subject_path = (root / subject_path).resolve()
        if subject_path not in document_path.parents:
            LOGGER.warning(
                "Document %s is not inside subject folder %s",
                document_path,
                subject_path,
            )

    reports: list[DocumentReport] = []
    running_total = 0
    tool_manager: LanguageToolManager | None = None
    if tool is None:
        tool_manager = _create_language_tool_manager(
            ignored_words=ignored_words,
            disabled_rules=disabled_rules,
        )

    # If tool is provided, use it directly (backward compatibility for single-language checking)
    if tool is not None:
        for subject_name, document_path in documents:
            report, running_total = _run_check_with_logging(
                subject_name,
                document_path,
                tool,
                ignored_words,
                running_total,
            )
            reports.append(report)
    else:
        # Create tools per subject for multi-language support
        current_subject: str | None = None
        current_tools: list[Any] | None = None

        try:
            for subject_name, document_path in documents:
                # Create new tools if subject changed
                if current_subject != subject_name:
                    # Close previous tools
                    if current_tools is not None:
                        for t in current_tools:
                            if hasattr(t, "close"):
                                t.close()

                    # Create tools for new subject
                    current_subject = subject_name
                    current_tools = build_language_tools_for_subject(
                        subject_name,
                        disabled_rules=disabled_rules,
                        ignored_words=ignored_words,
                        manager=tool_manager,
                    )

                # Pass tools as list or single tool depending on count
                assert current_tools is not None  # for type checkers
                tool_arg = (
                    current_tools[0] if len(current_tools) == 1 else current_tools
                )
                report, running_total = _run_check_with_logging(
                    subject_name,
                    document_path,
                    tool_arg,
                    ignored_words,
                    running_total,
                )
                reports.append(report)
        finally:
            # Close final tools
            if current_tools is not None:
                for t in current_tools:
                    if hasattr(t, "close"):
                        t.close()

    if report_path is None:
        report_path = root / "language-check-report.md"

    # Write Markdown report
    report_markdown = build_report_markdown(reports)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_markdown, encoding="utf-8")

    # Write CSV report
    csv_path = report_path.with_suffix(".csv")
    csv_rows = build_report_csv(reports)
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerows(csv_rows)

    return report_path


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run British English language checks on Markdown documents."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("Documents"),
        help="Root directory containing subject folders (default: Documents)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Path to write the Markdown report (default: <root>/language-check-report.md)",
    )
    parser.add_argument(
        "--language",
        default="en-GB",
        help="Language code to use for LanguageTool (default: en-GB)",
    )
    parser.add_argument(
        "--subject",
        type=Path,
        default=None,
        help="Subject folder to check (relative to root unless absolute).",
    )
    parser.add_argument(
        "--document",
        type=Path,
        default=None,
        help="Single Markdown document to check (relative to root unless absolute).",
    )
    parser.add_argument(
        "--ignore-word",
        action="append",
        dest="ignored_words",
        help="Add a word to the spell-check ignore list (case-sensitive, can be specified multiple times). "
        f"Default ignored words: {', '.join(sorted(DEFAULT_IGNORED_WORDS))}",
    )
    # Note: disabled rules are no longer configurable via CLI. They are
    # sourced from `language_check_config.DEFAULT_DISABLED_RULES` and subject-
    # specific additions (e.g. MORFOLOGIK for language subjects).

    parser.add_argument(
        "--no-default-words",
        action="store_true",
        help="Don't apply default ignored words (only use words specified with --ignore-word)",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = parse_args(argv)
    # Disabled rules are controlled by `language_check_config.DEFAULT_DISABLED_RULES`
    # and subject-specific additions inside `build_language_tools_for_subject`.
    disabled_rules: set[str] | None = None

    ignored_words: set[str] | None = None
    if args.no_default_words:
        ignored_words = set(args.ignored_words or [])
    elif args.ignored_words:
        ignored_words = set(DEFAULT_IGNORED_WORDS) | set(args.ignored_words)
    else:
        ignored_words = set(DEFAULT_IGNORED_WORDS)

    try:
        report_path = run_language_checks(
            args.root,
            report_path=args.report,
            language=args.language,
            subject=args.subject,
            document=args.document,
            disabled_rules=disabled_rules,
            ignored_words=ignored_words,
        )
    except FileNotFoundError as exc:
        LOGGER.error("%s", exc)
        return 1
    csv_path = report_path.with_suffix(".csv")
    print(f"Language check report written to {report_path.resolve()}")
    print(f"CSV report written to {csv_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
