"""Tests for prompt template rendering with pystache."""

from __future__ import annotations

import sys
import json
from pathlib import Path
from tempfile import TemporaryDirectory

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.prompt.render_prompt import (
    render_template,
    _read_prompt,
    _strip_code_fences,
    render_prompts,
)


class TestStripCodeFences:
    """Tests for _strip_code_fences helper."""

    def test_strip_triple_backticks(self) -> None:
        """Test stripping triple-backtick fences."""
        text = "```\nHello world\n```"
        result = _strip_code_fences(text)
        assert result == "Hello world"

    def test_strip_quad_backticks(self) -> None:
        """Test stripping quad-backtick fences."""
        text = "````\nHello world\n````"
        result = _strip_code_fences(text)
        assert result == "Hello world"

    def test_strip_with_language_tag(self) -> None:
        """Test stripping fences with language tag (e.g. ```markdown)."""
        text = "```markdown\nHello world\n```"
        result = _strip_code_fences(text)
        assert result == "Hello world"

    def test_strip_with_leading_whitespace(self) -> None:
        """Test stripping fences with leading whitespace on fence lines."""
        text = "  ```\nHello world\n  ```"
        result = _strip_code_fences(text)
        assert result == "Hello world"

    def test_no_fences(self) -> None:
        """Test text without fences is unchanged."""
        text = "Hello world"
        result = _strip_code_fences(text)
        assert result == "Hello world"

    def test_only_opening_fence(self) -> None:
        """Test text with only opening fence."""
        text = "```\nHello world"
        result = _strip_code_fences(text)
        assert result == "Hello world"

    def test_only_closing_fence(self) -> None:
        """Test text with only closing fence."""
        text = "Hello world\n```"
        result = _strip_code_fences(text)
        assert result == "Hello world"

    def test_empty_string(self) -> None:
        """Test empty string."""
        result = _strip_code_fences("")
        assert result == ""

    def test_preserve_internal_fences(self) -> None:
        """Test that internal fences are preserved."""
        text = "```\nOuter fence\n```markdown\nInternal\n```\n```"
        result = _strip_code_fences(text)
        # Only outer fences are stripped
        assert "```markdown" in result
        assert result.startswith("Outer fence")
        assert result.endswith("```")


class TestReadPrompt:
    """Tests for _read_prompt helper."""

    def test_read_existing_prompt(self) -> None:
        """Test reading an existing prompt file."""
        # llm_reviewer_system_prompt.md should exist
        content = _read_prompt("llm_reviewer_system_prompt.md")
        assert isinstance(content, str)
        assert len(content) > 0
        assert "WJEC" in content

    def test_read_language_tool_categoriser(self) -> None:
        """Test reading the language_tool_categoriser prompt."""
        # The original combined template has been split; ensure the
        # user prompt exists and is readable.
        content = _read_prompt("user_language_tool_categoriser.md")
        assert isinstance(content, str)
        assert len(content) > 0

    def test_read_system_user_prompts(self) -> None:
        """Test reading the system and user templates if they exist."""
        content_sys = _read_prompt("system_language_tool_categoriser.md")
        content_user = _read_prompt("user_language_tool_categoriser.md")
        assert "Error Categories" in content_sys or "Output Format" in content_sys
        # The document header (Document Under Review) has been moved to the
        # system prompt; the user template should not contain it.
        assert "Document Under Review" in content_sys
        assert "Document Under Review" not in content_user

    def test_read_nonexistent_prompt(self) -> None:
        """Test that reading a nonexistent prompt raises FileNotFoundError."""
        try:
            _read_prompt("nonexistent_prompt.md")
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError as e:
            assert "nonexistent_prompt.md" in str(e)


class TestRenderTemplate:
    """Tests for render_template function."""

    def test_render_language_tool_categoriser(self) -> None:
        """Test rendering the language_tool_categoriser template."""
        result = render_template("user_language_tool_categoriser.md")
        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain the partial content (from llm_reviewer_system_prompt)
        # User template shows the batch table and page context
        assert "Issue Batch" in result or "Page context" in result

    def test_render_with_empty_context(self) -> None:
        """Test rendering with explicit empty context."""
        result1 = render_template("user_language_tool_categoriser.md", {})
        result2 = render_template("user_language_tool_categoriser.md")
        # Both should produce the same output
        assert result1 == result2

    def test_render_contains_system_prompt(self) -> None:
        """Test that rendered output includes the system prompt partial."""
        result = render_template("user_language_tool_categoriser.md")
        # The user template no longer contains the system prompt; it should
        # therefore not include the 'proofreader' guidance.
        assert "proofreader" not in result.lower()
        assert "WJEC" not in result

    def test_render_no_fences_in_partial(self) -> None:
        """Test that code-fence wrappers from the partial are stripped."""
        system_text, user_text = render_prompts(
            "system_language_tool_categoriser.md",
            "user_language_tool_categoriser.md",
        )
        # The llm_reviewer_system_prompt.md is wrapped in ```markdown, but
        # when included as a partial, those fences should be stripped.
        # We check that the content flows naturally without extra fences
        assert "```markdown" not in system_text


class TestRenderPromptIntegration:
    """Integration tests for the render_prompt module."""

    def test_full_render_pipeline(self) -> None:
        """Test the complete render pipeline: read -> strip -> render."""
        # This tests the full flow end-to-end
        result = render_template("user_language_tool_categoriser.md")
        assert isinstance(result, str)
        assert len(result) > 100
        # Should have sections from both files
        lines = result.split("\n")
        assert len(lines) > 10

    def test_render_idempotent(self) -> None:
        """Test that rendering twice produces the same result."""
        result1 = render_template("user_language_tool_categoriser.md")
        result2 = render_template("user_language_tool_categoriser.md")
        assert result1 == result2

    def test_render_with_context_dict(self) -> None:
        """Test rendering with a custom context dictionary."""
        # Create a simple template with a Mustache variable
        # (This test uses the existing template, which doesn't have variables,
        # so we verify that passing context doesn't break rendering)
        result = render_template(
            "user_language_tool_categoriser.md",
            {"unused_key": "unused_value"}
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_render_prompt_pair(self) -> None:
        """Ensure we can render a system+user pair using the new helper."""
        system_text, user_text = render_prompts(
            "system_language_tool_categoriser.md",
            "user_language_tool_categoriser.md",
            {"subject": "Art-and-Design", "filename": "file.md", "issue_table": "|a|b|c|\n", "page_context": []},
        )

        assert isinstance(system_text, str) and isinstance(user_text, str)
        assert len(system_text) > 0
        assert "Error Categories" in system_text
        # Header now lives in system prompt
        assert "Document Under Review" in system_text
        assert "Document Under Review" not in user_text


class TestRenderPromptEdgeCases:
    """Edge case tests for render_prompt."""

    def test_render_handles_special_characters(self) -> None:
        """Test that rendering handles special characters in content."""
        system_text, user_text = render_prompts(
            "system_language_tool_categoriser.md",
            "user_language_tool_categoriser.md",
        )
        # System prompt contains JSON examples with special chars
        assert "{" in system_text or "\"" in system_text

    def test_render_preserves_markdown_formatting(self) -> None:
        """Test that Markdown formatting is preserved in rendered output."""
        result = render_template("user_language_tool_categoriser.md")
        # Check for Markdown elements
        assert "#" in result  # Headers
        assert "**" in result or "##" in result  # Bold or subheaders

    def test_render_long_template(self) -> None:
        """Test that rendering the full categoriser template completes."""
        # language_tool_categoriser is a fairly long template; combine
        system_text, user_text = render_prompts(
            "system_language_tool_categoriser.md",
            "user_language_tool_categoriser.md",
        )
        combined = f"{system_text}\n\n{user_text}"
        assert len(combined) > 500  # Should be substantial

    def test_partial_content_integration(self) -> None:
        """Test that partial content is properly integrated into template."""
        system_text, user_text = render_prompts(
            "system_language_tool_categoriser.md",
            "user_language_tool_categoriser.md",
        )
        # System partial should contain 'WJEC' and 'proofreader'
        assert "WJEC" in system_text
        assert "proofreader" in system_text.lower()
