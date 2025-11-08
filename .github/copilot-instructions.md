# WjecDocumentScraper — Copilot Instructions (Agent Primer)

Small CLI tool to download GCSE PDF documents from WJEC “Made for Wales” pages.

Read this primer first, then consult the linked focus docs before changing code in those areas.

## Prime Directives (must-follow - non-negotiable)

**Always follow these steps first** - you will fail in your task if you do not.

- Always use `uv` for everything (run, deps, tests). **NEVER** use pip/venv directly.
- Before editing scraping logic or filenames, you must read: docs/ARCHITECTURE.md.
- Before running commands or changing dependencies, you **must** read: docs/UV_GUIDE.md.
- For testing, debugging, or quick checks, you must read: docs/DEV_WORKFLOWS.md.

## Runtime facts

- Language/runtime: Python >= 3.12 (see pyproject.toml)
- Entry points: `main.py` (CLI), `wjec_scraper.py` (reusable API)
- Default output: `Documents/` (created by the CLI unless `--dry-run`)
- Post-processing: optional organiser+Markdown conversion pipeline in `postprocess_documents.py` (invoked via CLI `--post-process*` flags; uses MarkItDown)

## Key contracts and invariants (do not break)

- Subject list: Controlled by `QUALIFICATION_URLS` in `wjec_scraper.py`. CLI matching is case-insensitive.
- Filename/dir normalisation (stable behavior):
   - `subject_directory_name(subject)` → filesystem-safe folder name (non-alphanumerics → `-`).
   - `sanitise_filename(title, url, existing)` → lowercase, hyphenated; appends `-N` to avoid collisions.
- Link discovery: de-duplicate by URL; prefer the longest available title per URL.
- Progress reporting: `download_subject_pdfs(..., reporter=Callable[[label, destination, url], None])` is used by the CLI to surface progress.

If you need details or examples for any of the above, see docs/ARCHITECTURE.md (must consult before edits).

## What to edit for common changes

- Add/remove subjects: Edit `QUALIFICATION_URLS` in `wjec_scraper.py` (keep exact subject strings; CLI matches case-insensitively).
- Adjust parsing or fetching: Update functions in `wjec_scraper.py` (see docs/ARCHITECTURE.md for the data flow and parsing rules, including React-props parsing and the optional key-documents endpoint).
- CLI behavior or options: Modify `main.py` (keep `--subjects`, `--list-subjects`, `--dry-run`, `-o/--output`).
- Post-processing workflow: Edit `postprocess_documents.py` (ThreadPool orchestrator that copies PDFs into `pdfs/`, converts them to Markdown via MarkItDown, and surfaces errors). Keep CLI worker limits and summary messaging consistent with `main.py`.

## Must-consult reference docs

- docs/ARCHITECTURE.md — architecture, API contracts, data flow, parsing rules, invariants. You must read this before changing `wjec_scraper.py` or anything affecting filenames/subjects.
- docs/UV_GUIDE.md — how to run code, manage dependencies, sync/lock the environment. You must use these uv commands for all workflows.
- docs/DEV_WORKFLOWS.md — quick checks, debugging, and testing patterns. Read before adding tests or doing parsing diagnostics.

## Notes on edge cases (already handled)

- Some subjects expose PDFs only via a key-documents endpoint; scraper tries that and continues gracefully on failure.
- Duplicate URLs are coalesced; duplicate filenames get a numeric suffix.
- Network/IO failures are logged without halting other downloads.

For deeper context (function-by-function), see docs/ARCHITECTURE.md.

**IMPORTANT**: Remember your prime directives! Always follow them.
