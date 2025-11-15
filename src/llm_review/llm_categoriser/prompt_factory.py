"""Build prompts for the LLM categoriser using templates.

This module renders the language_tool_categoriser.md template with batch-specific
context including the issue table and page excerpts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.prompt.render_prompt import render_template

if TYPE_CHECKING:
    from .batcher import Batch


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
    }
    
    # Render the full template
    rendered = render_template("language_tool_categoriser.md", context)
    
    # The template uses the system prompt partial, but we return it as a single user prompt
    # The actual system prompt is embedded in the template via {{> llm_reviewer_system_prompt}}
    # For the LLM service, we need to split it properly
    
    # For now, we'll return it as two prompts: system and user
    # The system prompt is the partial content, user prompt is the rest
    # However, the template already combines them, so we'll extract them
    
    # According to the template structure:
    # - First part is the system prompt partial
    # - Rest is the user prompt with document details
    
    # Split on the "Document Under Review" section
    parts = rendered.split("## Document Under Review", 1)
    
    if len(parts) == 2:
        system_prompt = parts[0].strip()
        user_prompt = "## Document Under Review" + parts[1]
    else:
        # Fallback: use entire rendered content as user prompt
        system_prompt = ""
        user_prompt = rendered
    
    return [system_prompt, user_prompt] if system_prompt else [user_prompt]
