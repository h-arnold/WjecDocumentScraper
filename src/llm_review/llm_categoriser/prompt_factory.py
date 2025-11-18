"""Build prompts for the LLM categoriser using templates.

This module renders the language_tool_categoriser.md template with batch-specific
context including the issue table and page excerpts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.prompt.render_prompt import render_template, render_prompts
from src.language_check.report_utils import build_issue_pages

if TYPE_CHECKING:
    from ..core.batcher import Batch
import re


def build_prompts(batch: Batch) -> list[str]:
    """Build system and user prompts for a batch of issues.
    
    Args:
        batch: A Batch object containing issues and page context
        
    Returns:
        A list with one or two strings: [system_prompt, user_prompt] if both are present,
        or [user_prompt] if no system prompt is found
        
    Notes:
        - The template is rendered with context including subject, filename,
          issue_table, and page_context
        - The template structure uses partials for system prompt and authoritative sources
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
    
    # Attempt to render two separate templates if available
    try:
        system_prompt, user_prompt = render_prompts(
            "system_language_tool_categoriser.md",
            "user_language_tool_categoriser.md",
            context,
        )
        # Return as list per existing contract
        return [system_prompt, user_prompt]
    except FileNotFoundError:
        # Fall back to the single-template render + split logic for backward compatibility
        rendered = render_template("language_tool_categoriser.md", context)

        # Maintain prior behaviour: split on the "Document Under Review" header
        header_re = re.compile(r"(?mi)^\s*##\s+Document Under Review\s*$", re.MULTILINE)
        match = header_re.search(rendered)
        if match:
            split_idx = match.start()
            system_prompt = rendered[:split_idx].strip()
            user_prompt = rendered[split_idx:].lstrip()
        else:
            parts = re.split(r"(?mi)\n##\s+Document Under Review\n", rendered, maxsplit=1)
            if len(parts) == 2:
                system_prompt = parts[0].strip()
                user_prompt = "## Document Under Review" + parts[1].lstrip()
            else:
                system_prompt = ""
                user_prompt = rendered

        return [system_prompt, user_prompt] if system_prompt else [user_prompt]
