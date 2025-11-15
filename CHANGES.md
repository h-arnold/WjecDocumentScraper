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
