"""Language quality checks for downloaded Markdown documents.

This module scans the generated subject folders, runs spelling and grammar
checks using a British English dictionary, and writes a Markdown report that
summarises the findings per subject and per document.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import language_tool_python


LOGGER = logging.getLogger(__name__)


@dataclass
class LanguageIssue:
	"""Represents a single language issue detected in a document."""

	line: int
	column: int
	rule_id: str
	message: str
	issue_type: str
	replacements: list[str]
	context: str
	highlighted_context: str


@dataclass
class DocumentReport:
	"""Compilation of issues for a specific document."""

	subject: str
	path: Path
	issues: list[LanguageIssue]


def build_language_tool(language: str) -> language_tool_python.LanguageTool | language_tool_python.LanguageToolPublicAPI:
	"""Instantiate a LanguageTool checker for the requested language.

	Falls back to the public API when the local Java runtime is unavailable.
	"""

	try:
		return language_tool_python.LanguageTool(language)
	except language_tool_python.JavaError:
		LOGGER.warning("Falling back to LanguageTool public API for %s", language)
		return language_tool_python.LanguageToolPublicAPI(language)


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


def _make_issue(match: object) -> LanguageIssue:
	line = int(getattr(match, "line", 0)) + 1
	column = int(getattr(match, "column", 0)) + 1
	rule_id = getattr(match, "ruleId", "UNKNOWN") or "UNKNOWN"
	message = str(getattr(match, "message", "")).strip()
	issue_type = getattr(match, "ruleIssueType", "unknown") or "unknown"
	replacements = list(getattr(match, "replacements", []) or [])
	context = getattr(match, "context", "")
	context_offset = int(getattr(match, "contextoffset", 0))
	error_length = int(getattr(match, "errorLength", 0))
	highlighted_context = _highlight_context(context, context_offset, error_length)
	return LanguageIssue(
		line=line,
		column=column,
		rule_id=rule_id,
		message=message,
		issue_type=issue_type,
		replacements=replacements,
		context=context,
		highlighted_context=highlighted_context,
	)


def check_document(document_path: Path, subject: str, tool: object) -> DocumentReport:
	"""Run language checks on a single Markdown document."""

	text = document_path.read_text(encoding="utf-8")
	try:
		matches = tool.check(text)
	except Exception as exc:  # LanguageTool can raise generic RuntimeError/IOError
		LOGGER.exception("Language check failed for %s", document_path)
		failure = LanguageIssue(
			line=1,
			column=1,
			rule_id="CHECK_FAILURE",
			message=f"Language check failed: {exc}",
			issue_type="error",
			replacements=[],
			context="",
			highlighted_context="",
		)
		return DocumentReport(subject=subject, path=document_path, issues=[failure])

	issues = [_make_issue(match) for match in matches]
	return DocumentReport(subject=subject, path=document_path, issues=issues)


def derive_subject_from_path(document_path: Path) -> str:
	"""Infer the subject directory name from a Markdown document path."""

	if document_path.parent.name == "markdown" and document_path.parent.parent.name:
		return document_path.parent.parent.name
	return document_path.parent.name


def check_single_document(
	document_path: Path,
	*,
	subject: Optional[str] = None,
	language: str = "en-GB",
	tool: object | None = None,
) -> DocumentReport:
	"""Convenience wrapper that runs checks for a single document."""

	resolved_subject = subject or derive_subject_from_path(document_path)
	created_tool = tool is None
	tool_instance = tool or build_language_tool(language)
	try:
		return check_document(document_path, resolved_subject, tool_instance)
	finally:
		if created_tool and hasattr(tool_instance, "close"):
			tool_instance.close()


def build_report_markdown(reports: Iterable[DocumentReport]) -> str:
	"""Convert the collected document reports into Markdown output."""

	report_list = list(reports)
	total_documents = len(report_list)
	total_issues = sum(len(report.issues) for report in report_list)

	subject_totals: dict[str, int] = {}
	subject_documents: dict[str, int] = {}
	for report in report_list:
		subject_totals[report.subject] = subject_totals.get(report.subject, 0) + len(report.issues)
		subject_documents[report.subject] = subject_documents.get(report.subject, 0) + 1

	lines: list[str] = []
	lines.append("# Language Check Report")
	lines.append("")
	lines.append(f"- Checked {total_documents} document(s)")
	lines.append(f"- Total issues found: {total_issues}")

	lines.append("")
	lines.append("## Totals by Subject")
	if subject_totals:
		running_total = 0
		for subject in sorted(subject_totals):
			running_total += subject_totals[subject]
			doc_count = subject_documents[subject]
			lines.append(
				f"- {subject}: {subject_totals[subject]} issue(s) across {doc_count} document(s) "
				f"(running total: {running_total})"
			)
	else:
		lines.append("- No subject folders found.")

	lines.append("")
	lines.append("---")
	lines.append("")
	lines.append("## Document Details")
	if not report_list:
		lines.append("")
		lines.append("_No documents found for checking._")
		return "\n".join(lines)

	for report in sorted(report_list, key=lambda item: (item.subject.lower(), item.path.name.lower())):
		lines.append("")
		lines.append(f"### {report.subject} / {report.path.name}")
		lines.append("")
		if not report.issues:
			lines.append("_No issues found._")
			continue

		lines.append(f"Found {len(report.issues)} issue(s).")
		lines.append("")
		lines.append("| Line | Column | Rule | Type | Message | Suggestions | Context |")
		lines.append("| --- | --- | --- | --- | --- | --- | --- |")
		for issue in report.issues:
			message = issue.message.replace("|", "\\|")
			suggestions = ", ".join(issue.replacements) if issue.replacements else "—"
			suggestions = suggestions.replace("|", "\\|")
			context = issue.highlighted_context.replace("|", "\\|") if issue.highlighted_context else "—"
			lines.append(
				f"| {issue.line} | {issue.column} | `{issue.rule_id}` | {issue.issue_type} | {message} | {suggestions} | {context} |"
			)

	return "\n".join(lines)


def run_language_checks(
	root: Path,
	*,
	report_path: Optional[Path] = None,
	language: str = "en-GB",
	subject: Path | str | None = None,
	document: Path | None = None,
	tool: object | None = None,
) -> Path:
	"""Run language checks across all Markdown documents and write a report."""

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

	created_tool = tool is None
	tool_instance = tool or build_language_tool(language)
	try:
		reports: list[DocumentReport] = []
		running_total = 0
		for subject_name, document_path in documents:
			LOGGER.info("Checking %s / %s", subject_name, document_path.name)
			report = check_document(document_path, subject_name, tool_instance)
			running_total += len(report.issues)
			LOGGER.info(
				"Completed %s / %s: %d issue(s) (running total: %d)",
				subject_name,
				document_path.name,
				len(report.issues),
				running_total,
			)
			reports.append(report)
	finally:
		if created_tool and hasattr(tool_instance, "close"):
			tool_instance.close()

	if report_path is None:
		report_path = root / "language-check-report.md"

	report_markdown = build_report_markdown(reports)
	report_path.parent.mkdir(parents=True, exist_ok=True)
	report_path.write_text(report_markdown, encoding="utf-8")
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
	return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
	logging.basicConfig(level=logging.INFO)
	args = parse_args(argv)
	try:
		report_path = run_language_checks(
			args.root,
			report_path=args.report,
			language=args.language,
			subject=args.subject,
			document=args.document,
		)
	except FileNotFoundError as exc:
		LOGGER.error("%s", exc)
		return 1
	print(f"Language check report written to {report_path.resolve()}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
