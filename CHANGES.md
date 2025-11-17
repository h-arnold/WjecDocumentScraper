# Error Handling Improvements

## Changes in this PR

### LLM Provider Selection Fix

**Problem**: The `llm_categoriser` CLI was not respecting the `LLM_PRIMARY` environment variable from `.env` files. The provider registry was checking `os.environ.get("LLM_PRIMARY")` before the `.env` file was loaded, causing it to always fall back to the default provider order (gemini, mistral) regardless of the setting in `.env`.

**Root Cause**: Order-of-operations bug in `src/llm_review/llm_categoriser/cli.py`. The CLI was passing `dotenv_path` to `create_provider_chain()`, which then passed it to individual provider constructors. However, `create_provider_chain()` reads the `LLM_PRIMARY` environment variable *before* instantiating any providers, so the `.env` file hadn't been loaded yet.

**Fix**: 
- Modified `cli.py` `main()` function to load `.env` early (immediately after argument parsing, before any provider creation)
- Changed `create_provider_chain()` call to pass `dotenv_path=None` since the environment is already loaded
- Added comprehensive tests in `tests/test_provider_registry_env.py` (12 tests)
- Added CLI-specific tests in `tests/llm_categoriser/test_cli_dotenv_loading.py` (4 tests)

**Impact**:
- ✅ `LLM_PRIMARY` from `.env` is now correctly respected
- ✅ `LLM_FALLBACK` from `.env` is now correctly respected  
- ✅ `--provider` CLI flag still overrides environment variables as expected
- ✅ Custom `--dotenv` paths work correctly
- ✅ No breaking changes - all existing tests pass
- ✅ Better architecture: loading `.env` early benefits future environment variables

**Testing**:
- All 16 new tests pass (provider registry + CLI)
- All 15 existing llm_categoriser tests pass
- Manual verification: `uv run python -m src.llm_review.llm_categoriser --subject Computer-Science --dry-run` now correctly shows `Using LLM provider(s): ['mistral']` when `LLM_PRIMARY=mistral` is set in `.env`

### Mistral API Key Authentication Fix

**Problem**: After fixing the provider selection issue, the `llm_categoriser` was failing with 401 Unauthorized errors when using Mistral as the primary provider.

**Root Cause**: The Mistral SDK does not automatically read the `MISTRAL_API_KEY` environment variable. Unlike some SDKs, it requires the API key to be explicitly passed to the `Mistral()` constructor. The `MistralLLM` class was calling `Mistral()` without arguments, which created a client but left it unauthenticated.

**Fix**:
- Modified `src/llm/mistral_llm.py` to explicitly read `MISTRAL_API_KEY` from the environment
- Pass the API key to the `Mistral(api_key=...)` constructor
- Added clear error message if `MISTRAL_API_KEY` is not set
- Preserved existing test functionality (tests use mock clients which bypass this requirement)

**Impact**:
- ✅ Mistral provider now successfully authenticates with the API
- ✅ 401 Unauthorized errors are resolved
- ✅ All existing Mistral tests pass (13 unit tests + 6 integration tests)
- ✅ Helpful error message if API key is missing
- ✅ No changes needed to test suite (tests use dummy clients)

**Testing**:
- All 13 Mistral unit tests pass
- All 6 Mistral integration tests pass
- Manual verification: Successfully categorized issues using Mistral API

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
- Default behaviour changed: `fail_on_quota` now defaults to True to fail-fast on provider quota exhaustion. The CLI and env var `LLM_FAIL_ON_QUOTA` control this behaviour; set to `false` to continue running on quota errors.
- Added `LLM_CATEGORISER_LOG_RESPONSES` / `LLM_CATEGORISER_LOG_DIR` toggles plus helper tests so raw LLM payloads can be captured to disk for debugging when needed.
- Introduced CLI overrides `--log-responses` and `--log-responses-dir`, a console hint when logging is active, and regression tests to confirm the environment toggle works end-to-end.
