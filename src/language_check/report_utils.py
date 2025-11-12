"""Utilities for generating language check reports.

This module centralises the Markdown and CSV report builders used by the
language check workflow. Keeping this logic separate makes it easier to
reuse and test independently from the document scanning routines.
"""

from __future__ import annotations

from typing import Iterable, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .language_check import DocumentReport
    from .language_issue import LanguageIssue


def _format_suggestions(replacements: list[str] | None, max_suggestions: int = 3) -> str:
    """Return a human-friendly, truncated suggestions string.

    If there are no replacements returns the em-dash used in the Markdown output.
    If there are more than ``max_suggestions`` replacements, the first
    ``max_suggestions`` are shown followed by "(+N more)".
    """
    if not replacements:
        return "—"
    if len(replacements) <= max_suggestions:
        return ", ".join(replacements)
    visible = ", ".join(replacements[:max_suggestions])
    remaining = len(replacements) - max_suggestions
    return f"{visible} (+{remaining} more)"


def build_report_markdown(reports: Iterable["DocumentReport"]) -> str:
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
        lines.append("| Filename | Page | Rule | Type | Issue | Message | Suggestions | Context |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for issue in report.issues:
            message = issue.message.replace("|", "\\|")
            suggestions = _format_suggestions(issue.replacements).replace("|", "\\|")
            context = issue.highlighted_context.replace("|", "\\|") if issue.highlighted_context else "—"
            page_num = str(issue.page_number) if issue.page_number is not None else "—"
            issue_text = issue.issue.replace("|", "\\|") if issue.issue else "—"
            lines.append(
                f"| {issue.filename} | {page_num} | `{issue.rule_id}` | {issue.issue_type} | {issue_text} | {message} | {suggestions} | {context} |"
            )

    return "\n".join(lines)


def build_report_csv(reports: Iterable["DocumentReport"]) -> list[list[str]]:
    """Convert the collected document reports into CSV data.

    Returns a list of rows, where each row is a list of string values.
    The first row contains the column headers.
    """

    rows: list[list[str]] = []

    rows.append([
        "Subject",
        "Filename",
        "Page",
        "Rule ID",
        "Type",
        "Issue",
        "Message",
        "Suggestions",
        "Context",
    ])

    report_list = sorted(
        reports,
        key=lambda item: (item.subject.lower(), item.path.name.lower()),
    )

    for report in report_list:
        for issue in report.issues:
            txt = _format_suggestions(issue.replacements)
            suggestions = "" if txt == "—" else txt
            context = issue.context if issue.context else ""
            page_num = str(issue.page_number) if issue.page_number is not None else ""

            rows.append([
                report.subject,
                issue.filename,
                page_num,
                issue.rule_id,
                issue.issue_type,
                issue.issue if issue.issue else "",
                issue.message,
                suggestions,
                context,
            ])

    return rows
