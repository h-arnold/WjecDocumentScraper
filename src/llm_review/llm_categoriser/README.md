# LLM Categoriser

A concise overview of the LLM-driven categoriser for LanguageTool issues. This module converts LanguageTool CSV outputs into per-document categorisation using a configured LLM, validates the categorisation, and persists results.

## Purpose
- Read `Documents/language-check-report.csv`, group issues by document, and produce per-document categorisation CSVs (one row per issue).
- Keep prompts focused: include per-batch issue tables and page snippets to limit token usage.
- Single-threaded by design to respect free-tier provider limits and simplify rate-limiting.

## Key modules / public contracts
- data_loader.load_issues(report_path: Path, *, subjects: set[str] | None, documents: set[str] | None) -> dict[DocumentKey, list[LanguageIssue]]
- batcher.iter_batches(issues: list[LanguageIssue], batch_size: int, markdown_path: Path) -> Iterable[Batch]
- prompt_factory.build_prompts(batch: Batch) -> list[str]  # returns [system_prompt, user_prompt] or [user_prompt]
- runner.run(..., reporter=Callable[[label, destination, url], None])  # orchestrates batches, LLM calls, validation, persistence
- persistence.save_batch_results(subject: str, filename: str, rows: list[dict])
- state.* (read/write JSON state file to resume operations)

Model contract:
- LanguageIssue (src/models/language_issue.py) is the unified model for CSV input + LLM output; use LanguageIssue.from_llm_response() for validation.

## CLI usage
- Main entrypoints:
  - uv run python -m src.llm_review.llm_categoriser
  - uv run python -m src.llm_review.llm_categoriser --from-report Documents/language-check-report.csv --batch-size 10
- Useful flags:
  - --dry-run (skip LLM calls, validate only)
  - --emit-batch-payload (write prompts to `data/batch_payloads` for manual testing)
  - --force (ignore state; redo all batches)
  - --subjects / --documents (filter scope)
  - --max-retries (defaults to 2)
- Examples:
  - Validate and list batches (no LLM call):
    uv run python -m src.llm_review.llm_categoriser --from-report Documents/language-check-report.csv --dry-run
  - Emit prompts for manual testing:
    uv run python -m src.llm_review.llm_categoriser --emit-batch-payload

## Output & logs
- Categorised output: Documents/<Subject>/document_reports/<filename>.csv
- Failed/errored batches: data/llm_categoriser_errors/<subject>/<filename>.batch-<index>.errors.json
- Raw LLM responses (optional): set LLM_CATEGORISER_LOG_RESPONSES=true to dump responses to data/llm_categoriser_responses
- State file (resume): default data/llm_categoriser_state.json (overridable by env var or CLI)

## Environment / config
- Use uv for all runs: uv run ...
- Configurables:
  - LLM_CATEGORISER_BATCH_SIZE (default 10)
  - LLM_CATEGORISER_MAX_RETRIES (default 2)
  - LLM_CATEGORISER_STATE_FILE
  - Provider min-request interval (e.g., GEMINI_MIN_REQUEST_INTERVAL)
- Respect provider min-request intervals; module enforces single-threaded semantics.

## Testing
- Unit tests are under tests/llm_categoriser/
- Run:
  uv run pytest tests/llm_categoriser -q

## Extending / troubleshooting
- Templates in: src/prompt/promptFiles/ (partials: llm_reviewer_system_prompt.md, authoritative_sources.md)
- JSON extraction is normalised via llm/json_utils.py; reuse across providers when enabling filter_json.
- For changes to scraping, filenames, or subject list consult docs/ARCHITECTURE.md before editing.
- If a Markdown file or page marker is missing, that document is skipped and logged; incomplete batches are not marked as done in state until persisted successfully.

If you want an expanded developer guide (prompt examples, test recipes, or CLI debug flow), ask which section to expand.
