# LLM Proofreader

A focused LLM-driven proofreader for final review of spelling and grammatical errors. This module reads verified categorised issues, filters to SPELLING_ERROR and ABSOLUTE_GRAMMATICAL_ERROR categories, and performs final proofreading with full markdown context.

## Purpose
- Read `Documents/verified-llm-categorised-language-check-report.csv`, filter to spelling and grammar errors only
- Present issues grouped by page with full page context to the LLM for final review
- Produce per-document proofreading CSVs with updated error categorisation and confidence scores
- Single-threaded by design to respect free-tier provider limits and simplify rate-limiting

## Key modules / public contracts
- data_loader.load_proofreader_issues(report_path: Path, *, subjects: set[str] | None, documents: set[str] | None) -> dict[DocumentKey, list[LanguageIssue]]
  - Filters CSV to only SPELLING_ERROR and ABSOLUTE_GRAMMATICAL_ERROR categories
- prompt_factory.build_prompts(batch: Batch) -> list[str]  # returns [system_prompt, user_prompt]
  - Uses build_issue_pages() to structure issues by page with full context
- runner.run(*, force: bool, dry_run: bool) -> dict[str, Any]  # orchestrates batches, LLM calls, validation, persistence
- persistence.save_proofreader_results(output_path: Path, results: list[LanguageIssue], *, columns: list[str])
- batch_orchestrator.ProofreaderBatchOrchestrator: Handles async batch job creation and retrieval
- state.* (read/write JSON state file to resume operations)

Model contract:
- LanguageIssue (src/models/language_issue.py) is the unified model
- All results have pass_code set to PassCode.LP (LLM Proofreader)

## CLI usage
- Main entrypoints:
  - uv run python -m src.llm_review.llm_proofreader
  - uv run python -m src.llm_review.llm_proofreader --from-report Documents/verified-llm-categorised-language-check-report.csv --batch-size 10
- Useful flags:
  - --dry-run (skip LLM calls, validate only)
  - --force (ignore state; redo all batches)
  - --subjects / --documents (filter scope)
  - --max-retries (defaults to 2)
  - --batch-size (defaults to 10)
- Examples:
  - Validate and list batches (no LLM call):
    uv run python -m src.llm_review.llm_proofreader --from-report Documents/verified-llm-categorised-language-check-report.csv --dry-run
  - Process specific subject:
    uv run python -m src.llm_review.llm_proofreader --subjects "Art-and-Design"

## Output & logs
- Proofreading output: Documents/<Subject>/llm_proofreader_reports/<filename>.csv
- Columns: issue_id, page_number, issue, highlighted_context, pass_code, error_category, confidence_score, reasoning
- Raw LLM responses (optional): set LLM_PROOFREADER_LOG_RESPONSES=true to dump responses to data/llm_proofreader_responses
- State file (resume): default data/llm_proofreader_state.json (overridable by env var or CLI)

## Environment / config
- Use uv for all runs: uv run ...
- Configurables:
  - LLM_PROOFREADER_BATCH_SIZE (default 10)
  - LLM_PROOFREADER_MAX_RETRIES (default 2)
  - LLM_PROOFREADER_STATE_FILE (default data/llm_proofreader_state.json)
  - LLM_PROOFREADER_LOG_RESPONSES (set to true/1 to enable response logging)
  - LLM_PROOFREADER_LOG_DIR (default data/llm_proofreader_responses)
  - Provider min-request interval (e.g., GEMINI_MIN_REQUEST_INTERVAL)
  - LLM_FAIL_ON_QUOTA (default: true) — Abort the whole run on provider quota/rate-limit exhaustion
- Respect provider min-request intervals; module enforces single-threaded semantics

## Prompt structure
- System prompt: Uses llm_proofreader.md template with llm_reviewer_system_prompt, authoritative_sources, and error descriptions
- User prompt: Groups issues by page with:
  - Per-page issue table (issue_id, issue, highlighted_context)
  - Full page context from markdown below each table
  - No truncation of page content

## Testing
- Manual testing with dry run:
  uv run python -m src.llm_review.llm_proofreader --dry-run --subjects "Art-and-Design"
- Data loader filtering can be tested independently (see tests/test_data_loader.py when added)

## Extending / troubleshooting
- Templates in: src/prompt/promptFiles/ (llm_proofreader.md, user_llm_proofreader.md)
- Partials: llm_reviewer_system_prompt.md, authoritative_sources.md, llm_proofreader_error_descriptions.md, llm_proofreader_output_format.md
- JSON extraction is normalised via llm/json_utils.py; reuse across providers when enabling filter_json
- CSV filenames are automatically converted to .md for markdown path resolution
- If a Markdown file or page marker is missing, that document is skipped and logged
- Incomplete batches are not marked as done in state until persisted successfully

## Batch API support
The module includes batch orchestrator support for async processing:
- Create batch jobs: uv run python -m src.llm_review.llm_proofreader batch-create
- Fetch results: uv run python -m src.llm_review.llm_proofreader batch-fetch --check-all-pending
- List jobs: uv run python -m src.llm_review.llm_proofreader batch-list

For expanded developer guide or specific troubleshooting, consult docs/LLM_REVIEW_MODULE_GUIDE.md.
