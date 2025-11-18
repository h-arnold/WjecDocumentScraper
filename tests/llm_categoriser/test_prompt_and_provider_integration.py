"""Integration tests for system+user prompt rendering and provider wiring.

This test ensures that the system prompt is rendered, passed to the provider
chain at creation time, and that only the user prompt is sent to the provider
via `LLMService.generate()`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import pytest

import sys
from pathlib import Path

# Ensure project root is on sys.path for test imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.prompt.render_prompt import render_prompts
from src.llm.provider_registry import create_provider_chain, _PROVIDER_FACTORIES
from src.llm.service import LLMService
from src.language_check.language_issue import LanguageIssue
from src.llm_review.llm_categoriser.prompt_factory import build_prompts
from src.llm_review.core.batcher import Batch


class DummyProvider:
    name = "dummy"

    def __init__(self, system_prompt: str, filter_json: bool, dotenv_path: str | Path | None):
        # Capture inputs for assertions
        self.system_prompt = system_prompt
        self.filter_json = filter_json
        self.dotenv_path = dotenv_path

        self.last_user_prompts: Sequence[str] | None = None
        self.last_filter_json = None

    def generate(self, user_prompts: Sequence[str], *, filter_json: bool = False) -> Any:
        # Capture the call
        self.last_user_prompts = list(user_prompts)
        self.last_filter_json = filter_json
        # Return a valid empty categoriser response structure
        return {"page_1": []}

    def batch_generate(self, batch_payload: Sequence[Sequence[str]], *, filter_json: bool = False) -> Sequence[Any]:
        raise NotImplementedError()

    def health_check(self) -> bool:
        return True


def dummy_factory(*, system_prompt: str | Path, filter_json: bool, dotenv_path: str | Path | None):
    return DummyProvider(system_prompt=system_prompt, filter_json=filter_json, dotenv_path=dotenv_path)


def test_system_and_user_prompt_are_used_and_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end check for system+user prompt rendering and LLMService usage.

    Replaces provider registry with a dummy provider that captures calls.
    """

    # Register dummy provider in the registry for the test
    monkeypatch.setitem(_PROVIDER_FACTORIES, "dummy", dummy_factory)

    # Render the system/user prompts with small context
    system_text, user_text = render_prompts(
        "system_language_tool_categoriser.md",
        "user_language_tool_categoriser.md",
        {
            "subject": "Art-and-Design",
            "filename": "gcse-art-and-design.md",
            "issue_table": "|issue_id|page|rule|message|\n|0|1|R1|Sample|\n",
            "page_context": [{"page_number": 1, "content": "Some page content"}],
        },
    )

    # Create provider chain with the system prompt
    providers = create_provider_chain(system_prompt=system_text, filter_json=True, primary="dummy")
    assert providers, "Provider chain must not be empty"

    provider = providers[0]
    # System prompt text must be passed to the provider
    assert provider.system_prompt == system_text

    # Create a minimal batch with one dummy LanguageIssue
    issue = LanguageIssue(
        filename="gcse-art-and-design.md",
        rule_id="R1",
        message="Sample",
        issue_type="misspelling",
        replacements=[],
        highlighted_context="Sample",
        issue="Sample",
        page_number=1,
        issue_id=0,
    )

    batch = Batch(
        subject="Art-and-Design",
        filename="gcse-art-and-design.md",
        index=0,
        issues=[issue],
        page_context={1: "Some page content"},
        markdown_table="|issue_id|page|rule|message|\n|0|1|R1|Sample|\n",
    )

    prompts = build_prompts(batch)
    # Should return [system_prompt, user_prompt]
    assert len(prompts) >= 2

    user_prompts = prompts[1:]

    llm_service = LLMService(providers)

    # Call generate - this should call provider.generate with only user prompts
    _ = llm_service.generate(user_prompts, filter_json=True)

    assert provider.last_user_prompts is not None
    # The provider should have received exactly the user prompt(s)
    assert provider.last_user_prompts == list(user_prompts)
    # The filter_json flag should be passed to provider
    assert provider.last_filter_json is True