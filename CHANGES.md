# Error Handling Improvements

## Changes in this PR

### scripts/process_all_subjects.py
- Added full stack trace logging to exception handlers
- Fixed subprocess output visibility (was being discarded)
- Improved error messages with context

### src/postprocessing/__init__.py  
- Changed logger.warning to logger.exception for better debugging
- Added exc_info=True to logger.warning calls
- Ensured all error paths include stack traces

### tests/test_error_logging.py
- Added 7 comprehensive tests for error logging
- Verified stack traces are captured in all error scenarios

### src/llm_review/llm_categoriser/persistence.py
- Added `save_failed_issues(..., error_messages=...)` to persist LLM validation error messages to
	`data/llm_categoriser_errors/<subject>/<filename>.batch-<index>.errors.json` for offline debugging.

### src/llm_review/llm_categoriser/runner.py
- Collects validation error messages from LLM responses and passes them into `save_failed_issues`
	so the saved JSON includes both failed issues and the LLM/validation error messages that explain why
	they failed.

## Impact
- No breaking changes
- All 57 tests pass
- Better debugging capability for production issues

## LLM categoriser output refresh

- Updated `system_language_tool_categoriser.md` to request a flat JSON array (no per-page grouping) so the LLM no longer repeats page metadata.
- Simplified the runner validation path to consume the flat array and deduplicate retries by `issue_id`.
- Switched `persistence.save_batch_results()` to emit per-document CSV files (`Documents/<Subject>/document_reports/<filename>.csv`) with one row per issue, plus matching tests and docs.
- Refreshed `LLM_CATEGORISER_SPEC.md` and `src/llm_review/llm_categoriser/README.md` to describe the new workflow and persisted artifact.
- Added `LLM_CATEGORISER_LOG_RESPONSES` / `LLM_CATEGORISER_LOG_DIR` toggles plus helper tests so raw LLM payloads can be captured to disk for debugging when needed.
- Introduced CLI overrides `--log-responses` and `--log-responses-dir`, a console hint when logging is active, and regression tests to confirm the environment toggle works end-to-end.
