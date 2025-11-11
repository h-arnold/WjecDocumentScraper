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

from pathlib import Path
import json
import sys

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


def render_template(template_name: str = "language_tool_categoriser.md", context: dict | None = None) -> str:
    template = _read_prompt(template_name)
    # load required partials (currently only llm_reviewer_system_prompt.md)
    partial_name = "llm_reviewer_system_prompt"
    partial_filename = partial_name + ".md"
    partial_content = _read_prompt(partial_filename)
    partial_content = _strip_code_fences(partial_content)

    renderer = pystache.Renderer(partials={partial_name: partial_content})
    return renderer.render(template, context or {})


def _load_context(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    tpl = sys.argv[1] if len(sys.argv) > 1 else "language_tool_categoriser.md"
    ctx = None
    if len(sys.argv) > 2:
        ctx = _load_context(sys.argv[2])
    print(render_template(tpl, ctx))
