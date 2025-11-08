"""Asynchronous spelling and grammar checks for post-processed Markdown documents."""

from __future__ import annotations

import logging
import re
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from language_tool_python import LanguageTool
from spellchecker import SpellChecker

logger = logging.getLogger(__name__)

_WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_CONTEXT_RADIUS = 40


@dataclass
class GrammarIssue:
    line: int
    column: int
    message: str
    rule_id: str
    replacements: list[str]
    context: str


@dataclass
class SpellingIssue:
    line: int
    column: int
    word: str
    suggestions: list[str]
    context: str


@dataclass
class DocumentIssues:
    path: Path
    grammar_issues: list[GrammarIssue] = field(default_factory=list)
    spelling_issues: list[SpellingIssue] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def total_issues(self) -> int:
        return len(self.grammar_issues) + len(self.spelling_issues)


@dataclass
class SubjectIssues:
    subject_dir: Path
    documents: list[DocumentIssues] = field(default_factory=list)

    def total_documents(self) -> int:
        return len(self.documents)

    def total_grammar(self) -> int:
        return sum(len(doc.grammar_issues) for doc in self.documents)

    def total_spelling(self) -> int:
        return sum(len(doc.spelling_issues) for doc in self.documents)

    def total_issues(self) -> int:
        return sum(doc.total_issues() for doc in self.documents)


@dataclass
class LanguageCheckResults:
    subjects: list[SubjectIssues]
    report_path: Path

    def total_documents(self) -> int:
        return sum(subject.total_documents() for subject in self.subjects)

    def total_issues(self) -> int:
        return sum(subject.total_issues() for subject in self.subjects)

    def total_grammar(self) -> int:
        return sum(subject.total_grammar() for subject in self.subjects)

    def total_spelling(self) -> int:
        return sum(subject.total_spelling() for subject in self.subjects)


class _WorkerResources:
    """Thread-local pool for expensive checker instances."""

    def __init__(self, language: str) -> None:
        self.language = language
        self._local = threading.local()

    def language_tool(self) -> LanguageTool:
        if not hasattr(self._local, "tool"):
            self._local.tool = LanguageTool(self.language)
        return self._local.tool

    def spell_checker(self) -> SpellChecker:
        if not hasattr(self._local, "spell"):
            self._local.spell = SpellChecker()
        return self._local.spell


def _offset_to_position(text: str, offset: int) -> tuple[int, int]:
    """Return a 1-based (line, column) tuple for the character offset."""
    line = text.count("\n", 0, offset) + 1
    last_newline = text.rfind("\n", 0, offset)
    if last_newline == -1:
        column = offset + 1
    else:
        column = offset - last_newline
    return line, column


def _context_snippet(text: str, offset: int, length: int) -> str:
    start = max(0, offset - _CONTEXT_RADIUS)
    end = min(len(text), offset + length + _CONTEXT_RADIUS)
    snippet = text[start:end]
    return snippet.replace("\n", " ")


def _check_document(path: Path, resources: _WorkerResources) -> DocumentIssues:
    issues = DocumentIssues(path=path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        issues.errors.append(f"Failed to read file: {exc}")
        return issues

    tool = resources.language_tool()
    spell = resources.spell_checker()

    try:
        matches = tool.check(text)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Grammar check failed for %s", path)
        issues.errors.append(f"Grammar check failed: {exc}")
        matches = []

    for match in matches:
        offset = match.offset
        length = match.errorLength or len(match.context)
        line, column = _offset_to_position(text, offset)
        replacements = [replacement for replacement in match.replacements][:5]
        issues.grammar_issues.append(
            GrammarIssue(
                line=line,
                column=column,
                message=match.message,
                rule_id=match.ruleId,
                replacements=replacements,
                context=_context_snippet(text, offset, length),
            )
        )

    words = list(_WORD_PATTERN.finditer(text))
    unknown = spell.unknown(word.group().lower() for word in words)

    for match in words:
        word = match.group()
        lower_word = word.lower()
        if any(char.isdigit() for char in word):
            continue
        if "-" in word or "'" in word:
            continue
        if word.isupper():
            continue
        if lower_word not in unknown:
            continue
        offset = match.start()
        line, column = _offset_to_position(text, offset)
        candidates = [candidate for candidate in spell.candidates(lower_word) if candidate != lower_word]
        suggestions = sorted(candidates)[:5]
        issues.spelling_issues.append(
            SpellingIssue(
                line=line,
                column=column,
                word=word,
                suggestions=suggestions,
                context=_context_snippet(text, offset, len(word)),
            )
        )

    return issues


def _find_markdown_files(subject_dir: Path) -> Iterable[Path]:
    markdown_dir = subject_dir / "markdown"
    if not markdown_dir.is_dir():
        return []
    return sorted(markdown_dir.glob("*.md"))


def _collect_subject_directories(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir())


def _build_report_contents(results: LanguageCheckResults) -> str:
    lines: list[str] = []
    lines.append("# Language Quality Report")
    lines.append("")
    lines.append(f"Generated on {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")

    if not results.subjects:
        lines.append("No subject directories were found.")
        return "\n".join(lines)

    overall_docs = results.total_documents()
    lines.append(
        f"Checked {overall_docs} Markdown document(s) across {len(results.subjects)} subject(s)."
    )
    lines.append(
        f"Detected {results.total_grammar()} grammar issue(s) and {results.total_spelling()} spelling issue(s)."
    )
    lines.append("")

    for subject in results.subjects:
        lines.append(f"## {subject.subject_dir.name}")
        lines.append("")
        if not subject.documents:
            lines.append("No Markdown documents found.")
            lines.append("")
            continue
        lines.append(
            f"Checked {subject.total_documents()} file(s); found {subject.total_grammar()} grammar issue(s) and {subject.total_spelling()} spelling issue(s)."
        )
        lines.append("")
        for document in subject.documents:
            relative_path = document.path.relative_to(subject.subject_dir)
            lines.append(f"### {relative_path}")
            lines.append("")
            if document.errors:
                lines.append("- Errors:")
                for error in document.errors:
                    lines.append(f"  - {error}")
                lines.append("")
                continue
            if document.total_issues() == 0:
                lines.append("No issues found.")
                lines.append("")
                continue
            if document.grammar_issues:
                lines.append(
                    f"Grammar issues ({len(document.grammar_issues)}):"
                )
                for issue in document.grammar_issues:
                    replacements = (
                        f" Suggestions: {', '.join(issue.replacements)}."
                        if issue.replacements
                        else ""
                    )
                    lines.append(
                        f"- Line {issue.line}, column {issue.column} [{issue.rule_id}]: {issue.message}.{replacements}"
                    )
                    lines.append(f"  Context: {issue.context}")
                lines.append("")
            if document.spelling_issues:
                lines.append(
                    f"Spelling issues ({len(document.spelling_issues)}):"
                )
                for issue in document.spelling_issues:
                    replacements = (
                        f" Suggestions: {', '.join(issue.suggestions)}."
                        if issue.suggestions
                        else ""
                    )
                    lines.append(
                        f"- Line {issue.line}, column {issue.column}: '{issue.word}'.{replacements}"
                    )
                    lines.append(f"  Context: {issue.context}")
                lines.append("")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def run_language_checks(
    root: Path,
    report_path: Path | None = None,
    max_workers: int | None = None,
    language: str = "en-GB",
) -> LanguageCheckResults:
    """Check all Markdown files under the Documents root and write a Markdown report."""
    subject_dirs = _collect_subject_directories(root)
    if report_path is None:
        report_path = root / "language-report.md"

    executor_kwargs = {"max_workers": max_workers} if max_workers else {}
    resources = _WorkerResources(language)
    subject_map: dict[Path, list[DocumentIssues]] = defaultdict(list)

    markdown_paths = [
        (subject_dir, markdown_path)
        for subject_dir in subject_dirs
        for markdown_path in _find_markdown_files(subject_dir)
    ]

    if not markdown_paths:
        logger.info("No Markdown documents found under %s", root)
        results = LanguageCheckResults(subjects=[], report_path=report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(_build_report_contents(results), encoding="utf-8")
        return results

    with ThreadPoolExecutor(**executor_kwargs) as executor:
        futures = {
            executor.submit(_check_document, markdown_path, resources): (subject_dir, markdown_path)
            for subject_dir, markdown_path in markdown_paths
        }
        for future in as_completed(futures):
            subject_dir, markdown_path = futures[future]
            try:
                document_issues = future.result()
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.exception("Language check failed for %s", markdown_path)
                document_issues = DocumentIssues(path=markdown_path)
                document_issues.errors.append(str(exc))
            subject_map[subject_dir].append(document_issues)

    subjects = [
        SubjectIssues(subject_dir=subject, documents=sorted(docs, key=lambda item: item.path.name))
        for subject, docs in sorted(subject_map.items(), key=lambda item: item[0].name.lower())
    ]

    results = LanguageCheckResults(subjects=subjects, report_path=report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_build_report_contents(results), encoding="utf-8")
    return results


__all__ = [
    "GrammarIssue",
    "SpellingIssue",
    "DocumentIssues",
    "SubjectIssues",
    "LanguageCheckResults",
    "run_language_checks",
]
