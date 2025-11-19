"""Render prompt templates in src/prompt/promptFiles using pystache.

This small helper loads a template file (default: language_tool_categoriser.md),
loads the `llm_reviewer_system_prompt.md` partial, strips any leading/trailing
code-fence wrappers (so files that include ```markdown blocks work as partials),
and renders the template with optional JSON context passed via a file.

Usage:
    python -m src.prompt.render_prompt [template_filename] [context.json]

If no arguments are given, it renders `language_tool_categoriser.md` with an
empty context and prints to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import pystache
except Exception as exc:
    raise SystemExit(
        "pystache is required to run this script; please install it (e.g. `uv add pystache` or `pip install pystache`)."
    ) from exc

PROMPTS_DIR = Path(__file__).parent / "promptFiles"


def _read_prompt(name: str) -> str:
    p = PROMPTS_DIR / name
    if not p.exists():
        raise FileNotFoundError(f"Prompt file not found: {p}")
    return p.read_text(encoding="utf-8")


def _strip_code_fences(s: str) -> str:
    """Strip a single leading and trailing code-fence block if present.

    Handles fences like ``` or ```` optionally followed by a language tag.
    """
    lines = s.splitlines()
    if not lines:
        return s
    # detect leading fence
    first = lines[0].lstrip()
    last = lines[-1].lstrip()
    if first.startswith("```") or first.startswith("````"):
        # drop first line
        lines = lines[1:]
    if last.startswith("```") or last.startswith("````"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def render_template(
    template_name: str = "language_tool_categoriser.md", context: dict | None = None
) -> str:
    template = _read_prompt(template_name)

    # Load required partials
    partials = {}

    for partial_name in [
        "llm_reviewer_system_prompt",
        "authoritative_sources",
        "error_descriptions",
        "output_format",
    ]:
        partial_content = _read_prompt(f"{partial_name}.md")
        partials[partial_name] = _strip_code_fences(partial_content)

    renderer = pystache.Renderer(partials=partials)
    return renderer.render(template, context or {})


def render_prompts(
    system_template: str = "system_language_tool_categoriser.md",
    user_template: str = "user_language_tool_categoriser.md",
    context: dict | None = None,
) -> tuple[str, str]:
    """Render a system and user prompt pair from two separate templates.

    The function is a convenience for LLM callers that need a two-part chat
    prompt (system + user). It uses the same partials as `render_template`.

    Returns:
        (system_prompt, user_prompt)
    """

    # Load partials (shared by both templates)
    partials = {}

    for partial_name in [
        "llm_reviewer_system_prompt",
        "authoritative_sources",
        "error_descriptions",
        "output_format",
    ]:
        partial_content = _read_prompt(f"{partial_name}.md")
        partials[partial_name] = _strip_code_fences(partial_content)

    renderer = pystache.Renderer(partials=partials)

    # Render each template independently
    system_tpl = _read_prompt(system_template)
    user_tpl = _read_prompt(user_template)

    rendered_system = renderer.render(system_tpl, context or {})
    rendered_user = renderer.render(user_tpl, context or {})
    return rendered_system.strip(), rendered_user.strip()


def _load_context(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    tpl = sys.argv[1] if len(sys.argv) > 1 else "language_tool_categoriser.md"
    ctx = None
    if len(sys.argv) > 2:
        ctx = _load_context(sys.argv[2])
    print(render_template(tpl, ctx))
