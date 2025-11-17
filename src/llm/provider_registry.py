from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv
from .gemini_llm import GeminiLLM
from .mistral_llm import MistralLLM
from .provider import LLMProvider, ProviderFactory

def _gemini_factory(
    *,
    system_prompt: str | Path,
    filter_json: bool,
    dotenv_path: str | Path | None,
) -> LLMProvider:
    return GeminiLLM(
        system_prompt=system_prompt,
        filter_json=filter_json,
        dotenv_path=dotenv_path,
    )


def _mistral_factory(
    *,
    system_prompt: str | Path,
    filter_json: bool,
    dotenv_path: str | Path | None,
) -> LLMProvider:
    return MistralLLM(
        system_prompt=system_prompt,
        filter_json=filter_json,
        dotenv_path=dotenv_path,
    )


_PROVIDER_FACTORIES: dict[str, ProviderFactory] = {
    "gemini": _gemini_factory,
    "mistral": _mistral_factory,
}


def _split_names(value: str | None) -> list[str]:
    if not value:
        return []
    return [chunk.strip().lower() for chunk in value.split(",") if chunk.strip()]


def create_provider_chain(
    *,
    system_prompt: str | Path,
    filter_json: bool = False,
    dotenv_path: str | Path | None = None,
    primary: str | None = None,
    fallbacks: Sequence[str] | None = None,
) -> list[LLMProvider]:
    """Return configured providers honoring environment/priority hints."""

    order: list[str] = []
    seen: set[str] = set()

    # If dotenv_path was supplied, load it early so that environment variables
    # such as LLM_PRIMARY/LLM_FALLBACK are available before we read them.
    if dotenv_path is not None:
        # Force .env values to override for provider discovery and ordering
        load_dotenv(dotenv_path=str(dotenv_path), override=True)

    candidates: list[str] = []
    if primary:
        candidates.extend(_split_names(primary))
    else:
        candidates.extend(_split_names(os.environ.get("LLM_PRIMARY")))

    if fallbacks:
        candidates.extend(name.lower() for name in fallbacks)
    else:
        candidates.extend(_split_names(os.environ.get("LLM_FALLBACK")))

    if not candidates:
        candidates = list(_PROVIDER_FACTORIES.keys())

    for name in candidates:
        if name in seen:
            continue
        seen.add(name)
        if name not in _PROVIDER_FACTORIES:
            raise ValueError(f"Unknown LLM provider '{name}'")
        order.append(name)

    return [
        _PROVIDER_FACTORIES[name](
            system_prompt=system_prompt,
            filter_json=filter_json,
            dotenv_path=dotenv_path,
        )
        for name in order
    ]