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

## Impact
- No breaking changes
- All 57 tests pass
- Better debugging capability for production issues
