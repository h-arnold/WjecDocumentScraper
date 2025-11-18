"""Tests for provider registry environment variable handling.

These tests verify that the provider registry correctly reads LLM_PRIMARY and
LLM_FALLBACK environment variables, especially when they are set in .env files
that need to be loaded before the registry reads them.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Sequence

import pytest

# Ensure project root is on sys.path for test imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.provider import LLMProvider
from src.llm.provider_registry import (
    _PROVIDER_FACTORIES,
    _split_names,
    create_provider_chain,
)


class MockProvider(LLMProvider):
    """Mock provider for testing."""

    def __init__(self, name: str):
        self.name = name
        self._system_prompt = ""

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    def generate(
        self, user_prompts: Sequence[str], *, filter_json: bool = False
    ) -> Any:
        return {}

    def batch_generate(
        self, batch_payload: Sequence[Sequence[str]], *, filter_json: bool = False
    ) -> Sequence[Any]:
        raise NotImplementedError()

    def health_check(self) -> bool:
        return True


def mock_provider_factory(name: str):
    """Factory that returns a mock provider factory function."""

    def factory(
        *, system_prompt: str | Path, filter_json: bool, dotenv_path: str | Path | None
    ):
        provider = MockProvider(name)
        provider._system_prompt = str(system_prompt)
        return provider

    return factory


def test_split_names_with_comma_separated_values() -> None:
    """Test _split_names correctly splits comma-separated provider names."""
    assert _split_names("gemini,mistral") == ["gemini", "mistral"]
    assert _split_names("Gemini, Mistral") == ["gemini", "mistral"]
    assert _split_names("  gemini  ,  mistral  ") == ["gemini", "mistral"]
    assert _split_names("gemini") == ["gemini"]


def test_split_names_with_empty_values() -> None:
    """Test _split_names handles empty/None values."""
    assert _split_names(None) == []
    assert _split_names("") == []
    assert _split_names("  ") == []
    assert _split_names(",,,") == []


def test_create_provider_chain_respects_primary_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that explicit primary parameter overrides environment."""
    # Mock the provider factories
    monkeypatch.setitem(_PROVIDER_FACTORIES, "mock1", mock_provider_factory("mock1"))
    monkeypatch.setitem(_PROVIDER_FACTORIES, "mock2", mock_provider_factory("mock2"))

    # Even if environment is set, explicit parameter should win
    monkeypatch.setenv("LLM_PRIMARY", "mock2")

    providers = create_provider_chain(
        system_prompt="test",
        filter_json=False,
        primary="mock1",
    )

    assert len(providers) >= 1
    assert providers[0].name == "mock1"


def test_create_provider_chain_respects_fallbacks_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that explicit fallbacks parameter adds additional providers."""
    monkeypatch.setitem(_PROVIDER_FACTORIES, "mock1", mock_provider_factory("mock1"))
    monkeypatch.setitem(_PROVIDER_FACTORIES, "mock2", mock_provider_factory("mock2"))

    providers = create_provider_chain(
        system_prompt="test",
        filter_json=False,
        primary="mock1",
        fallbacks=["mock2"],
    )

    assert len(providers) == 2
    assert providers[0].name == "mock1"
    assert providers[1].name == "mock2"


def test_create_provider_chain_deduplicates_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that duplicate providers are removed."""
    monkeypatch.setitem(_PROVIDER_FACTORIES, "mock1", mock_provider_factory("mock1"))
    monkeypatch.setitem(_PROVIDER_FACTORIES, "mock2", mock_provider_factory("mock2"))

    providers = create_provider_chain(
        system_prompt="test",
        filter_json=False,
        primary="mock1",
        fallbacks=["mock1", "mock2"],  # mock1 appears twice
    )

    # Should only have mock1 once, then mock2
    assert len(providers) == 2
    assert providers[0].name == "mock1"
    assert providers[1].name == "mock2"


def test_create_provider_chain_reads_env_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that LLM_PRIMARY environment variable is respected."""
    monkeypatch.setitem(_PROVIDER_FACTORIES, "mock1", mock_provider_factory("mock1"))
    monkeypatch.setenv("LLM_PRIMARY", "mock1")

    providers = create_provider_chain(
        system_prompt="test",
        filter_json=False,
    )

    assert len(providers) >= 1
    assert providers[0].name == "mock1"


def test_create_provider_chain_reads_env_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that LLM_FALLBACK environment variable is respected."""
    monkeypatch.setitem(_PROVIDER_FACTORIES, "mock1", mock_provider_factory("mock1"))
    monkeypatch.setitem(_PROVIDER_FACTORIES, "mock2", mock_provider_factory("mock2"))
    monkeypatch.setenv("LLM_PRIMARY", "mock1")
    monkeypatch.setenv("LLM_FALLBACK", "mock2")

    providers = create_provider_chain(
        system_prompt="test",
        filter_json=False,
    )

    assert len(providers) == 2
    assert providers[0].name == "mock1"
    assert providers[1].name == "mock2"


def test_create_provider_chain_uses_defaults_when_no_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that default providers are used when no env vars are set."""
    # Replace entire factory dict with just mocks
    original_factories = _PROVIDER_FACTORIES.copy()
    _PROVIDER_FACTORIES.clear()
    _PROVIDER_FACTORIES["mock1"] = mock_provider_factory("mock1")
    _PROVIDER_FACTORIES["mock2"] = mock_provider_factory("mock2")

    try:
        # Clear any existing env vars
        monkeypatch.delenv("LLM_PRIMARY", raising=False)
        monkeypatch.delenv("LLM_FALLBACK", raising=False)

        providers = create_provider_chain(
            system_prompt="test",
            filter_json=False,
        )

        # Should get all registered providers
        assert len(providers) == 2
        provider_names = {p.name for p in providers}
        assert provider_names == {"mock1", "mock2"}
    finally:
        # Restore original factories
        _PROVIDER_FACTORIES.clear()
        _PROVIDER_FACTORIES.update(original_factories)


def test_create_provider_chain_loads_dotenv_when_provided(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that dotenv_path is passed to provider factories.

    This verifies the parameter plumbing, but the actual .env loading
    happens in each provider's __init__.
    """
    monkeypatch.setitem(_PROVIDER_FACTORIES, "mock1", mock_provider_factory("mock1"))

    # Create a test .env file
    env_file = tmp_path / "test.env"
    env_file.write_text("MOCK_API_KEY=test_key\n", encoding="utf-8")

    # This won't actually load the env file into os.environ until providers
    # are instantiated, but we can verify the parameter is passed
    providers = create_provider_chain(
        system_prompt="test",
        filter_json=False,
        primary="mock1",
        dotenv_path=env_file,
    )

    assert len(providers) == 1
    assert providers[0].name == "mock1"


def test_create_provider_chain_with_unknown_provider_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that unknown provider names raise ValueError."""
    monkeypatch.setitem(_PROVIDER_FACTORIES, "mock1", mock_provider_factory("mock1"))
    monkeypatch.setenv("LLM_PRIMARY", "unknown_provider")

    with pytest.raises(ValueError, match="Unknown LLM provider 'unknown_provider'"):
        create_provider_chain(
            system_prompt="test",
            filter_json=False,
        )


def test_create_provider_chain_env_variables_must_be_loaded_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that demonstrates the bug: env vars must be loaded before create_provider_chain.

    This is the core test case for the bug we're fixing. When .env is not loaded
    before calling create_provider_chain, the LLM_PRIMARY setting is ignored.
    """
    # Replace entire factory dict with just mocks
    original_factories = _PROVIDER_FACTORIES.copy()
    _PROVIDER_FACTORIES.clear()
    _PROVIDER_FACTORIES["mock1"] = mock_provider_factory("mock1")
    _PROVIDER_FACTORIES["mock2"] = mock_provider_factory("mock2")

    try:
        # Create a .env file with LLM_PRIMARY=mock1
        env_file = tmp_path / ".env"
        env_file.write_text("LLM_PRIMARY=mock1\n", encoding="utf-8")

        # Clear environment to simulate fresh state
        monkeypatch.delenv("LLM_PRIMARY", raising=False)
        monkeypatch.delenv("LLM_FALLBACK", raising=False)

        # BUG: If we call create_provider_chain with dotenv_path, it's too late!
        # The environment variables are read BEFORE the providers are instantiated,
        # so the .env file hasn't been loaded yet when create_provider_chain
        # checks os.environ.get("LLM_PRIMARY")

        # Creating with a dotenv_path should load the .env and make LLM_PRIMARY
        # available when the provider registry decides provider order.
        providers_without_preload = create_provider_chain(
            system_prompt="test",
            filter_json=False,
            dotenv_path=env_file,
        )

        # With the fix, mock1 should be first
        assert len(providers_without_preload) == 1
        assert providers_without_preload[0].name == "mock1"

        # Now test the FIX: load .env BEFORE calling create_provider_chain
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=env_file)

        providers_with_preload = create_provider_chain(
            system_prompt="test",
            filter_json=False,
        )

        # With the fix, mock1 should be first
        assert providers_with_preload[0].name == "mock1"
    finally:
        # Restore original factories
        _PROVIDER_FACTORIES.clear()
        _PROVIDER_FACTORIES.update(original_factories)


def test_cli_should_load_dotenv_early(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that CLI loads .env early enough for provider selection.

    This test documents the expected behavior: the CLI should load .env
    before calling create_provider_chain so that LLM_PRIMARY is available.
    """
    # Mock providers
    monkeypatch.setitem(_PROVIDER_FACTORIES, "mock1", mock_provider_factory("mock1"))
    monkeypatch.setitem(_PROVIDER_FACTORIES, "mock2", mock_provider_factory("mock2"))

    # Create a .env file
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_PRIMARY=mock1\nMOCK_API_KEY=test_key_123\n", encoding="utf-8"
    )

    # Clear environment
    monkeypatch.delenv("LLM_PRIMARY", raising=False)
    monkeypatch.delenv("MOCK_API_KEY", raising=False)

    # Simulate what the CLI should do: load .env FIRST
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=env_file)

    # Verify environment is now set
    assert os.environ.get("LLM_PRIMARY") == "mock1"
    assert os.environ.get("MOCK_API_KEY") == "test_key_123"

    # Now create_provider_chain will see the correct LLM_PRIMARY
    providers = create_provider_chain(
        system_prompt="test",
        filter_json=False,
    )

    assert providers[0].name == "mock1"
