# UV Guide (MUST CONSULT BEFORE RUNNING OR MODIFYING DEPENDENCIES)

All development, execution, and dependency management for this project uses **uv**. Do not use `pip`, `venv`, `poetry`, or `python -m` workflows directly.

## Core Principles

- Reproducibility: `uv.lock` pins resolved versions; commit it.
- Single tool: Use `uv run`, `uv add`, `uv remove`, `uv sync`, `uv lock`.
- No manual virtualenv activation: `uv run` creates/syncs `.venv` automatically.

## Frequent Tasks

| Task | Command |
|------|---------|
| List subjects | `uv run python main.py --list-subjects` |
| Dry-run Geography | `uv run python main.py --subjects Geography --dry-run` |
| Download two subjects | `uv run python main.py --subjects "Art and Design" French` |
| Post-process existing downloads | `uv run python main.py --post-process-only --post-process-workers 4` |
| Open REPL | `uv run python` |
| Inline check | `uv run python -c "from src.scraper import QUALIFICATION_URLS; print(len(QUALIFICATION_URLS))"` |

## Running Code

Always prefix with `uv run`:
```bash
uv run python main.py --list-subjects
uv run python -c "from src.scraper import subject_directory_name; print(subject_directory_name('Cymraeg Language and Literature'))"
uv run python main.py --subjects Geography --post-process
```

## Adding Dependencies

```bash
# Runtime dependency
uv add httpx

# Dev/test dependency
uv add --dev pytest
```

Avoid manual edits to `[project.dependencies]`; let uv manage them.

## Removing Dependencies

```bash
uv remove beautifulsoup4
```

## Synchronizing Environment

```bash
uv sync               # Ensure environment matches lockfile
uv sync --only-group dev  # Only dev dependencies
uv sync --no-inexact  # Clean extraneous packages
```

## Updating Dependencies

```bash
uv lock --upgrade                  # Refresh all compatible versions
uv lock --upgrade-package requests # Upgrade single package
uv lock --upgrade-package bs4==4.13.0  # Pin specific version
uv sync                             # (optional explicit sync)
```

Always re-run a dry CLI check after upgrades:
```bash
uv run python main.py --dry-run --subjects Geography
```

## Testing (when tests exist)

Add pytest first:
```bash
uv add --dev pytest
```
Run tests:
```bash
uv run pytest
uv run pytest -k filename
uv run pytest tests/test_scraper.py::test_sanitise_filename
```

## Debugging & Inspection

```bash
uv run python              # REPL
uv run python -c "..."     # One-off diagnostics
uv tree                    # Show dependency graph
uv pip list                # List installed packages
uv pip show requests       # Inspect a package
```

## Advanced Run Flags

```bash
uv run --frozen python main.py --list-subjects    # Fail if lockfile mismatch
uv run --no-sync python main.py --dry-run         # Skip sync (use only if certain)
uv run --with httpx==0.27.0 python -c "import httpx; print(httpx.__version__)"  # Temp extra dep
```

## Common Mistakes (Avoid)

| Mistake | Correct |
|---------|---------|
| `python main.py` | `uv run python main.py` |
| `pip install ...` | `uv add ...` |
| Editing `pyproject.toml` versions manually | `uv add pkg==ver` or `uv lock --upgrade-package pkg==ver` |
| Activating `.venv` manually | Just use `uv run` |

## Troubleshooting Steps

1. `uv sync`
2. `uv lock --check`
3. `uv lock --upgrade`
4. `uv tree`
5. If stuck: remove `.venv` and `uv sync` again.

## When to Update This Document

- New dependency workflow introduced.
- Testing framework or tooling changes.
- Additional mandatory commands for CI added.
