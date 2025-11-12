"""Language quality checks for downloaded Markdown documents.

This module scans the generated subject folders, runs spelling and grammar
checks using a British English dictionary, and writes a Markdown report that
summarises the findings per subject and per document.
"""

from __future__ import annotations

import argparse
import csv
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import language_tool_python

from .language_check_config import DEFAULT_DISABLED_RULES, DEFAULT_IGNORED_WORDS
from .page_utils import build_page_number_map
from .report_utils import build_report_csv, build_report_markdown


LOGGER = logging.getLogger(__name__)


# Subject-to-language mapping for multi-language support
# Maps subject names to additional language codes to check
SUBJECT_LANGUAGE_MAP = {
	"French": "fr",
	"German": "de",
}


def get_languages_for_subject(subject: str) -> list[str]:
	"""Determine which languages to check for a given subject.
	
	**Important**: LanguageTool does not support checking mixed-language documents
	by running multiple language checkers. Running both English and French checkers
	on a mixed-language document will generate hundreds of false positives because:
	- The English checker will flag all French words as spelling errors
	- The French checker will flag all English words as spelling errors
	
	The correct approach is to use **language auto-detection** with a preferred
	variant (en-GB for British English). This allows LanguageTool to detect the
	primary language of the document while preferring British English when English
	is detected. Foreign language words in embedded examples should be added to
	the ignore list.
	
	Args:
		subject: Subject name (e.g., "French", "German", "Computer-Science")
		
	Returns:
		List containing 'auto' for automatic language detection
	"""
	# Use auto-detection - it will detect the primary language of the document
	# The preferred variant (en-GB) is set in build_language_tool()
	return ["auto"]


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



def _retry_with_backoff(
	func: Any,
	func_arg: Any,
	max_retries: int = 3,
	base_delay: float = 1.0,
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
			delay = base_delay * (2 ** attempt)
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
class LanguageIssue:
	"""Represents a single language issue detected in a document."""

	filename: str
	rule_id: str
	message: str
	issue_type: str
	replacements: list[str]
	context: str
	highlighted_context: str
	issue: str
	page_number: int | None = None


@dataclass
class DocumentReport:
	"""Compilation of issues for a specific document."""

	subject: str
	path: Path
	issues: list[LanguageIssue]


def build_language_tool(
	language: str,
	*,
	disabled_rules: set[str] | None = None,
	ignored_words: set[str] | None = None,
) -> Any:
	"""Instantiate a LanguageTool checker for the requested language.

	Falls back to the public API when the local Java runtime is unavailable.
	
	Args:
		language: Language code (e.g., "en-GB", "auto" for auto-detection)
		disabled_rules: Set of rule IDs to disable
		ignored_words: Set of words to add to the spell-check whitelist (case-sensitive)
	"""
	
	# Merge with defaults
	rules_to_disable = set(DEFAULT_DISABLED_RULES)
	if disabled_rules:
		rules_to_disable.update(disabled_rules)
	
	words_to_ignore = set(DEFAULT_IGNORED_WORDS)
	if ignored_words:
		words_to_ignore.update(ignored_words)

	try:
		# When using auto-detection, we'll set preferred variants after creation
		tool = language_tool_python.LanguageTool(language)
		
		# For auto-detection, set preferred variant to British English
		# This ensures spell-checking works correctly for English documents
		if language == "auto":
			tool.preferred_variants = {'en-GB'}
			LOGGER.info("Using automatic language detection with preferred variant: en-GB")
	except Exception as exc:
		# Do not silently fall back to the public API. If a local Java runtime
		# isn't available or another error occurs, surface the original
		# exception so the caller can decide how to proceed. This prevents
		# unexpected use of the public LanguageTool API in environments where
		# network access or rate limits are undesired.
		LOGGER.exception("Failed to create local LanguageTool for %s: %s", language, exc)
		raise
	
	# Disable specified rules
	if rules_to_disable:
		# LanguageTool implementations commonly expect a set for disabled_rules
		try:
			tool.disabled_rules = set(rules_to_disable)
		except Exception:
			tool.disabled_rules = set(rules_to_disable)
		LOGGER.info("Disabled rules: %s", ", ".join(sorted(rules_to_disable)))
	
	# Add words to ignore list
	if words_to_ignore:
		# Try to update an internal ignore set if present, otherwise try a
		# public method (addIgnoreTokens) or fall back to post-processing.
		try:
			_internal = getattr(tool, "_ignore_words", None)
			if _internal is not None and hasattr(_internal, "update"):
				_internal.update(words_to_ignore)
			else:
				# Prefer calling a public API if present. Use getattr to avoid
				# static-analysis errors when the upstream stubs don't include
				# this method name or when different implementations expose
				# different method names.
				_add = getattr(tool, "addIgnoreTokens", None)
				if callable(_add):
					try:
						_add(list(words_to_ignore))
					except Exception:
						pass
			LOGGER.info("Ignoring words: %s", ", ".join(sorted(words_to_ignore)))
		except Exception:
			LOGGER.info("Will filter ignored words in post-processing: %s", ", ".join(sorted(words_to_ignore)))
	
	return tool


def iter_markdown_documents(root: Path, *, subject_path: Path | None = None) -> list[tuple[str, Path]]:
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


def _get_page_number_for_match(match: object, text: str, page_map: dict[int, int]) -> int | None:
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


def _make_issue(match: object, filename: str, text: str = "", page_map: dict[int, int] | None = None) -> LanguageIssue:
	rule_id = getattr(match, "ruleId", "UNKNOWN") or "UNKNOWN"
	message = str(getattr(match, "message", "")).strip()
	issue_type = getattr(match, "ruleIssueType", "unknown") or "unknown"
	replacements = list(getattr(match, "replacements", []) or [])
	context = getattr(match, "context", "")
	context_offset = int(getattr(match, "offsetInContext", 0))
	error_length = int(getattr(match, "errorLength", 0))
	highlighted_context = _highlight_context(context, context_offset, error_length)
	
	# Extract the matched issue text from the context
	issue = context[context_offset:context_offset + error_length] if error_length > 0 else ""
	
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
	
	# Build page number map from the document text
	page_map = build_page_number_map(text)
	
	# Merge ignored words with defaults.
	# NOTE: matching is case-sensitive — we use the words as provided in the
	# configuration because many entries are case-specific (proper nouns,
	# acronyms, product names, etc.).
	words_to_ignore = set(DEFAULT_IGNORED_WORDS)
	if ignored_words:
		words_to_ignore.update(ignored_words)
	
	# Normalize tool to a list for uniform processing
	tools = [tool] if not isinstance(tool, list) else tool
	
	# Collect matches from all tools
	all_matches = []
	failure_records: list[tuple[str, Exception, bool]] = []
	successful_check = False
	for tool_instance in tools:
		language_code = getattr(tool_instance, "language", None)
		language_label = language_code or getattr(tool_instance, "lang", "unknown")
		try:
			# Retry with exponential backoff for transient connection errors
			matches = _retry_with_backoff(tool_instance.check, text, max_retries=3, base_delay=1.0)
			successful_check = True
			all_matches.extend(matches or [])
		except TRANSIENT_ERRORS as exc:
			LOGGER.exception(
				"Language check failed for %s (language: %s) after all retries",
				document_path,
				language_label,
			)
			failure_records.append((str(language_label), exc, True))
			continue
		except Exception as exc:  # Other unexpected errors
			LOGGER.exception(
				"Language check failed for %s (language: %s)",
				document_path,
				language_label,
			)
			failure_records.append((str(language_label), exc, False))
			continue

	# If every tool failed, surface the failures as before
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
				context="",
				highlighted_context="",
				issue="",
			)
			for language, exc, is_transient in failure_records
		]
		return DocumentReport(subject=subject, path=document_path, issues=issues)

	# Use all_matches instead of matches for the rest of the function
	matches = all_matches

	# Filter out issues for ignored words using case-sensitive matching.
	# Behaviour:
	# - If the token in the document appears to be an acronym (uppercase
	#   letters, possibly with a trailing 's' for plural or punctuation), we
	#   only ignore it when the exact form (case-sensitive) is in the ignore list.
	#   This prevents ignoring Titlecase names like "Nic" while still ignoring
	#   "NIC" and "NICs" when those exact forms are in the list.
	# - For non-acronym tokens, we ignore them only when the exact (case-sensitive)
	#   form is in the ignore list. This preserves case-specific entries like
	#   "Ethernet" while not suppressing "ethernet" unless explicitly listed.
	filtered_matches = []
	for match in matches:
		if hasattr(match, "matchedText"):
			original_text = str(getattr(match, "matchedText", "")).strip()
			if original_text:
				# letters-only projection to detect acronyms like "NIC" or "S/PDIF"
				letters = "".join(ch for ch in original_text if ch.isalpha())
				is_acronym_form = False
				if letters:
					# treat uppercased letters (or uppercased letters with trailing 's') as acronym form
					if letters.isupper() or letters.rstrip("s").isupper():
						is_acronym_form = True

				if is_acronym_form:
					# Only ignore if the exact form (case-sensitive) is present in the
					# ignore list. Also allow singular form (strip trailing 's') if
					# that exact string is in the list.
					if letters in words_to_ignore or letters.rstrip("s") in words_to_ignore:
						continue
				else:
					# For non-acronym tokens, ignore only on an exact (case-sensitive)
					# match with the configured ignore words. This avoids suppressing
					# Titlecase names unless the Titlecase form is explicitly listed.
					if original_text in words_to_ignore:
						continue
		filtered_matches.append(match)
	
	issues = [_make_issue(match, filename, text, page_map) for match in filtered_matches]
	
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
					context="",
					highlighted_context="",
					issue="",
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
) -> list[Any]:
	"""Build LanguageTool instances for a subject.
	
	For language subjects (French, German), creates tools for both the subject
	language and English. For other subjects, creates only an English tool.
	
	Args:
		subject: Subject name (e.g., "French", "German", "Computer-Science")
		disabled_rules: Set of rule IDs to disable
		ignored_words: Set of words to ignore
		
	Returns:
		List of LanguageTool instances (may contain one or more tools)
	"""
	languages = get_languages_for_subject(subject)
	tools = []
	
	for language in languages:
		tool = build_language_tool(
			language,
			disabled_rules=disabled_rules,
			ignored_words=ignored_words
		)
		tools.append(tool)
		LOGGER.info("Created LanguageTool for language: %s (subject: %s)", language, subject)
	
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
			return check_document(document_path, resolved_subject, tool, ignored_words=ignored_words)
		finally:
			# Don't close externally provided tools
			pass
	
	# Otherwise, create tools based on subject
	tools = build_language_tools_for_subject(
		resolved_subject,
		disabled_rules=disabled_rules,
		ignored_words=ignored_words
	)
	
	try:
		# If only one tool, pass it directly (not in a list) for backward compatibility
		tool_arg = tools[0] if len(tools) == 1 else tools
		return check_document(document_path, resolved_subject, tool_arg, ignored_words=ignored_words)
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
	report = check_document(document_path, subject_name, tool_arg, ignored_words=ignored_words)
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
			LOGGER.warning("Document %s is not inside subject folder %s", document_path, subject_path)

	reports: list[DocumentReport] = []
	running_total = 0

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
						ignored_words=ignored_words
					)
				
				# Pass tools as list or single tool depending on count
				assert current_tools is not None  # for type checkers
				tool_arg = current_tools[0] if len(current_tools) == 1 else current_tools
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
	parser = argparse.ArgumentParser(description="Run British English language checks on Markdown documents.")
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
		"--disable-rule",
		action="append",
		dest="disabled_rules",
		help="Disable a specific LanguageTool rule (can be specified multiple times). "
		     f"Default disabled rules: {', '.join(sorted(DEFAULT_DISABLED_RULES))}",
	)
	parser.add_argument(
		"--ignore-word",
		action="append",
		dest="ignored_words",
		help="Add a word to the spell-check ignore list (case-sensitive, can be specified multiple times). "
		     f"Default ignored words: {', '.join(sorted(DEFAULT_IGNORED_WORDS))}",
	)
	parser.add_argument(
		"--no-default-rules",
		action="store_true",
		help="Don't apply default disabled rules (only use rules specified with --disable-rule)",
	)
	parser.add_argument(
		"--no-default-words",
		action="store_true",
		help="Don't apply default ignored words (only use words specified with --ignore-word)",
	)
	return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
	logging.basicConfig(level=logging.INFO)
	args = parse_args(argv)
	
	# Build sets of disabled rules and ignored words
	disabled_rules: set[str] | None = None
	if args.no_default_rules:
		disabled_rules = set(args.disabled_rules or [])
	elif args.disabled_rules:
		disabled_rules = set(DEFAULT_DISABLED_RULES) | set(args.disabled_rules)
	else:
		disabled_rules = set(DEFAULT_DISABLED_RULES)
	
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
