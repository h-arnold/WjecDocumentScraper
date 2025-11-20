"""Build prompts for the LLM proofreader using templates.

This module renders the llm_proofreader prompts with batch-specific
context including the issue table and page excerpts.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.language_check.report_utils import build_issue_pages
from src.prompt.render_prompt import PROMPTS_DIR, render_prompts

if TYPE_CHECKING:
    from ..core.batcher import Batch
    from .page_batcher import PageBatch


def build_prompts(batch: Batch) -> list[str]:
    """Build system and user prompts for a batch of issues.

    Args:
        batch: A Batch object containing issues and page context

    Returns:
        A list with two strings: [system_prompt, user_prompt]

    Notes:
        - System prompt uses llm_proofreader.md template
        - User prompt uses user_llm_proofreader.md template
        - The template is rendered with context including subject, filename,
          issue_pages, and page_context
    """
    # Prepare page context for template
    # Convert dict[int, str] to list of dicts for mustache iteration
    page_context_list = [
        {"page_number": page_num, "content": content}
        for page_num, content in sorted(batch.page_context.items())
    ]

    # Build template context
    context = {
        "subject": batch.subject,
        "filename": batch.filename,
        "issue_table": batch.markdown_table,
        "page_context": page_context_list,
        # Structured per-page issues for templates that need both a small table
        # per-page and the full page context (no truncation).
        "issue_pages": build_issue_pages(batch.issues, batch.page_context),
    }

    # Render both prompts
    system_prompt, user_prompt = render_prompts(
        "llm_proofreader.md",
        "user_llm_proofreader.md",
        context,
    )

    return [system_prompt, user_prompt]


def get_system_prompt_text() -> str:
    """Get the rendered system prompt text without batch context.
    
    Used by CLI initialization to configure the LLM service.
    For batch-specific prompts, use build_prompts() instead.
    
    Returns:
        The rendered system prompt as a string
    """
    system_prompt, _ = render_prompts(
        "llm_proofreader.md",
        "user_llm_proofreader.md",
        {},
    )
    return system_prompt


def get_system_prompt() -> Path:
    """Get the path to the system prompt template."""
    return PROMPTS_DIR / "llm_proofreader.md"


def build_page_prompts(batch: "PageBatch") -> list[str]:
    """Build system and user prompts for a page-based batch.
    
    Args:
        batch: A PageBatch object containing page ranges and context
    
    Returns:
        A list with two strings: [system_prompt, user_prompt]
    """
    # Build structured page data with pre-existing issues
    page_data = []
    for page_num in sorted(batch.page_context.keys()):
        page_issues = batch.pre_existing_issues.get(page_num, [])
        
        # Format issues for display
        issue_rows = []
        for issue in page_issues:
            issue_rows.append({
                "issue_id": str(issue.issue_id) if issue.issue_id >= 0 else "—",
                "issue": issue.issue.replace("|", "\\|") if issue.issue else "—",
                "highlighted_context": (issue.highlighted_context or "").replace("|", "\\|"),
            })
        
        page_label = str(page_num) if page_num != 0 else "—"
        
        page_data.append({
            "page_number": page_label,
            "page_content": batch.page_context.get(page_num, ""),
            "has_existing_issues": len(issue_rows) > 0,
            "issues": issue_rows,
            "issue_count": len(issue_rows),
        })
    
    # Build context for template
    context = {
        "subject": batch.subject,
        "filename": batch.filename,
        "page_range_start": batch.page_range[0],
        "page_range_end": batch.page_range[1],
        "issue_pages": page_data,
    }
    
    # Render prompts using existing templates
    # The user_llm_proofreader.md template already handles issue_pages correctly
    system_prompt, user_prompt = render_prompts(
        "llm_proofreader.md",
        "user_llm_proofreader.md",
        context,
    )
    
    return [system_prompt, user_prompt]

