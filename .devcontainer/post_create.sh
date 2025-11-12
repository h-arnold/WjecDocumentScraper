#!/usr/bin/env bash
set -euo pipefail

# Post-create actions for the devcontainer: install `uv` and build project dependencies
# This script is idempotent: it will skip steps if `uv` is already available.

echo "[post_create] Starting devcontainer post-create script"

# Ensure python3 and pip are available
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found in PATH. Aborting."
  exit 1
fi

# Make sure local user bin is on PATH (where pipx/pip --user installs go)
export PATH="$HOME/.local/bin:$PATH"

# Install pipx (preferred) and then use it to install uv; fallback to --user pip
if ! command -v uv >/dev/null 2>&1; then
  echo "[post_create] 'uv' not found. Installing..."

  # Upgrade pip
  python3 -m pip install --upgrade pip setuptools wheel || true

  # Try pipx install path
  if ! command -v pipx >/dev/null 2>&1; then
    echo "[post_create] Installing pipx into --user"
    python3 -m pip install --user pipx || true
    # ensure pipx binaries are available
    if command -v pipx >/dev/null 2>&1; then
      pipx ensurepath || true
    fi
  fi

  export PATH="$HOME/.local/bin:$PATH"

  if command -v pipx >/dev/null 2>&1; then
    echo "[post_create] Installing uv via pipx"
    pipx install --force --skip-existing uv || python3 -m pip install --user uv
  else
    echo "[post_create] pipx not available; installing uv via pip --user"
    python3 -m pip install --user uv
  fi
fi

export PATH="$HOME/.local/bin:$PATH"

if command -v uv >/dev/null 2>&1; then
  echo "[post_create] uv installed at: $(command -v uv)"
else
  echo "[post_create] WARNING: uv command still not found after install attempts"
fi

echo "[post_create] Running 'uv sync' to install project dependencies (this may take a while)"
# Run uv sync to ensure the project's .venv and dependencies are installed. Allow failures to be surfaced
# but continue so the devcontainer creation doesn't entirely fail on transient network issues.
export PATH="$HOME/.local/bin:$PATH"

if command -v uv >/dev/null 2>&1; then
  # Prefer a non-failing sync on first attempt but surface output
  set +e
  uv sync
  SYNC_EXIT=$?
  set -e
  if [ "$SYNC_EXIT" -ne 0 ]; then
    echo "[post_create] uv sync exited with status $SYNC_EXIT (non-zero). See output above."
  else
    echo "[post_create] uv sync completed successfully"
  fi
else
  echo "[post_create] Skipping uv sync because 'uv' is not available"
fi

echo "[post_create] Post-create script finished"
