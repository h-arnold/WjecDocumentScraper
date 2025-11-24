#!/usr/bin/env bash
set -euo pipefail

echo "[post_start] Starting devcontainer post-start script"

# Allow disabling the post-start behaviour for fast iteration
if [ "${SKIP_POST_START:-0}" != "0" ]; then
  echo "[post_start] SKIP_POST_START is set; skipping post-start tasks"
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "[post_start] 'uv' not found in PATH. Run post-create steps first or install uv manually." >&2
  exit 0
fi

echo "[post_start] Synchronising project environment using 'uv sync'"
if ! uv sync; then
  echo "[post_start] 'uv sync' failed — leaving environment as-is" >&2
  # Don't fail container start; allow developer to inspect
fi

echo "[post_start] Ensuring pre-commit hooks are installed"
uv run pre-commit install --install-hooks || true

echo "[post_start] Running pre-commit hooks across the repository (this may modify files)"
# Don't fail container start if hooks fail; allow developer to inspect
uv run pre-commit run --all-files || true

echo "[post_start] post-start script complete"
