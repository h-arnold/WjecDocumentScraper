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


def build_issue_batch_table(issues: list["LanguageIssue"]) -> str:
    """Build a simplified Markdown table for LLM categoriser prompts.
    
    Returns a 4-column table: issue_id, page_number, issue, highlighted_context.
    This is a reduced version of the full CSV report, designed for token efficiency.
    
    Args:
        issues: List of LanguageIssue objects to include in the table
        
    Returns:
        A Markdown table as a string
    """
    if not issues:
        return ""
    
    lines = [
        "| issue_id | page_number | issue | highlighted_context |",
        "| --- | --- | --- | --- |",
    ]
    
    for issue in issues:
        issue_id_str = str(issue.issue_id) if issue.issue_id >= 0 else "—"
        page_num = str(issue.page_number) if issue.page_number is not None else "—"
        issue_text = issue.issue.replace("|", "\\|")
        context = issue.highlighted_context.replace("|", "\\|")
        
        lines.append(f"| {issue_id_str} | {page_num} | {issue_text} | {context} |")
    
    return "\n".join(lines)


def build_issue_pages(issues: list["LanguageIssue"], page_context: dict[int, str]) -> list[dict]:
    """Group issues by page and prepare structured data for prompt rendering.

    Returns a list of page dicts sorted by page number. Each page dict contains:
        - page_number: str (human-friendly page label or "—")
        - issues: list of dicts with keys: issue_id, issue, highlighted_context
        - page_content: the raw page text from page_context (no truncation)

    This helper is designed for use by LLM prompt templates which iterate over
    `issue_pages` and render both a compact table (one row per issue) followed
    by the full page context. The function escapes pipe characters to avoid
    breaking Markdown tables but otherwise leaves Markdown content intact.
    """

    if not issues:
        return []

    # Group issues by page number. Missing page numbers (None) use 0 to match
    # the behaviour in `iter_batches` (page 0 = whole document).
    pages: dict[int, list["LanguageIssue"]] = {}
    for issue in issues:
        key = issue.page_number if issue.page_number is not None else 0
        pages.setdefault(key, []).append(issue)

    page_list: list[dict] = []
    for page in sorted(pages.keys()):
        page_issues = sorted(pages[page], key=lambda i: i.issue_id)
        issue_rows = []
        for i in page_issues:
            issue_id = str(i.issue_id) if i.issue_id >= 0 else "—"
            issue_text = i.issue.replace("|", "\\|") if i.issue else "—"
            highlighted = (i.highlighted_context or "").replace("|", "\\|")
            issue_rows.append({
                "issue_id": issue_id,
                "issue": issue_text,
                "highlighted_context": highlighted,
            })

        # Page label: use em dash for unknown/0 (same as markdown table behaviour)
        page_label = str(page) if page != 0 else "—"

        page_list.append(
            {
                "page_number": page_label,
                "issues": issue_rows,
                "page_content": page_context.get(page, ""),
                "issue_count": len(issue_rows),
            }
        )

    return page_list


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
        "Highlighted Context",
    ])

    report_list = sorted(
        reports,
        key=lambda item: (item.subject.lower(), item.path.name.lower()),
    )

    for report in report_list:
        for issue in report.issues:
            txt = _format_suggestions(issue.replacements)
            suggestions = "" if txt == "—" else txt
            # Use highlighted_context for the CSV column
            context = issue.highlighted_context if issue.highlighted_context else ""
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
