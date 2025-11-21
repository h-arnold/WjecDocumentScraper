"""Tests for CLI .env loading behavior.

These tests verify that the CLI loads .env early enough for LLM_PRIMARY
and other environment variables to be available when create_provider_chain
is called.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path for test imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm_review.llm_categoriser.cli import main


def test_cli_loads_custom_dotenv_path_early(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that CLI loads custom .env path when --dotenv is specified."""
    # Create a custom .env file
    custom_env = tmp_path / "custom.env"
    custom_env.write_text(
        "LLM_PRIMARY=mistral\nMISTRAL_API_KEY=custom_key\n", encoding="utf-8"
    )

    # Create a minimal CSV file
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "Subject,Filename,Page,Rule ID,Type,Issue,Message,Suggestions,Highlighted Context,Pass Code\n"
        "Test,test.md,1,R1,error,word,msg,fix,ctx,LT\n",
        encoding="utf-8",
    )

    # Clear environment
    monkeypatch.delenv("LLM_PRIMARY", raising=False)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    # Mock the provider chain creation
    with patch(
        "src.llm_review.llm_categoriser.cli.create_provider_chain"
    ) as mock_create:
        mock_provider = MagicMock()
        mock_provider.name = "mistral"
        mock_create.return_value = [mock_provider]

        with patch("src.llm_review.llm_categoriser.cli.CategoriserRunner"):
            exit_code = main(
                [
                    "--from-report",
                    str(csv_file),
                    "--dotenv",
                    str(custom_env),
                    "--dry-run",
                ]
            )

            assert exit_code == 0
            assert mock_create.called

            # Environment should be set from custom .env
            assert os.environ.get("LLM_PRIMARY") == "mistral"
            assert os.environ.get("MISTRAL_API_KEY") == "custom_key"


def test_cli_respects_llm_primary_from_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that LLM_PRIMARY from .env is used for provider selection."""
    monkeypatch.chdir(tmp_path)

    # Create .env with LLM_PRIMARY=mistral
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_PRIMARY=mistral\nMISTRAL_API_KEY=test_key\n", encoding="utf-8"
    )

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "Subject,Filename,Page,Rule ID,Type,Issue,Message,Suggestions,Highlighted Context,Pass Code\n"
        "Test,test.md,1,R1,error,word,msg,fix,ctx,LT\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("LLM_PRIMARY", raising=False)

    # Capture what primary is passed to create_provider_chain
    captured_primary = None

    def capture_create_provider_chain(*args, **kwargs):
        nonlocal captured_primary
        captured_primary = kwargs.get("primary")
        mock_provider = MagicMock()
        mock_provider.name = "mistral"
        return [mock_provider]

    with patch(
        "src.llm_review.llm_categoriser.cli.create_provider_chain",
        side_effect=capture_create_provider_chain,
    ):
        with patch("src.llm_review.llm_categoriser.cli.CategoriserRunner"):
            # Pass --dotenv explicitly to ensure it's loaded in the test environment
            exit_code = main(
                ["--from-report", str(csv_file), "--dry-run", "--dotenv", str(env_file)]
            )

            assert exit_code == 0

            # primary parameter should be None (using env var instead)
            assert captured_primary is None

            # But LLM_PRIMARY should be set in environment
            assert os.environ.get("LLM_PRIMARY") == "mistral"


def test_cli_provider_flag_overrides_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that --provider CLI flag overrides LLM_PRIMARY from .env."""
    monkeypatch.chdir(tmp_path)

    # Create .env with LLM_PRIMARY=mistral
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_PRIMARY=mistral\nMISTRAL_API_KEY=test_key\nGEMINI_API_KEY=test_key2\n",
        encoding="utf-8",
    )

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "Subject,Filename,Page,Rule ID,Type,Issue,Message,Suggestions,Highlighted Context,Pass Code\n"
        "Test,test.md,1,R1,error,word,msg,fix,ctx,LT\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("LLM_PRIMARY", raising=False)

    captured_primary = None

    def capture_create_provider_chain(*args, **kwargs):
        nonlocal captured_primary
        captured_primary = kwargs.get("primary")
        mock_provider = MagicMock()
        mock_provider.name = "gemini"
        return [mock_provider]

    with patch(
        "src.llm_review.llm_categoriser.cli.create_provider_chain",
        side_effect=capture_create_provider_chain,
    ):
        with patch("src.llm_review.llm_categoriser.cli.CategoriserRunner"):
            exit_code = main(
                [
                    "--from-report",
                    str(csv_file),
                    "--provider",
                    "gemini",
                    "--dry-run",
                    "--dotenv",
                    str(env_file),
                ]
            )

            assert exit_code == 0

            # primary parameter should be "gemini" (from CLI flag)
            assert captured_primary == "gemini"

            # Environment should still have mistral from .env
            assert os.environ.get("LLM_PRIMARY") == "mistral"
