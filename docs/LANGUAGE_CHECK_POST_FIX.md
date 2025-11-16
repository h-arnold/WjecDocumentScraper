# Language Check POST Request Fix

## Problem Identified

**Date**: November 16, 2025  
**Issue**: Connection resets when checking large documents (e.g., Spanish specification, 361KB)

### Root Cause

The `language-tool-python` library (version 2.9.5) uses HTTP GET requests to send text to the LanguageTool Java server. GET requests encode all parameters (including the full document text) in the URL query string, which has size limitations:

1. **URL Length Limits**: Most HTTP servers limit URLs to 8KB-64KB
2. **Large Documents**: Some specification files exceed 350KB (360,000+ characters)
3. **Combined Payload**: Document text + disabled rules list exceeds URL limits
4. **Server Behavior**: The LanguageTool Java server resets the connection when the request is too large

### Investigation Process

1. Enabled `DEBUG_MODE` in `language_tool_python.server` to see error details
2. Observed that requests were being sent via GET with full document in query string
3. Confirmed that LanguageTool Java server supports POST requests
4. Identified that `language-tool-python` v2.9.5 (latest) doesn't support POST

## Solution

Created a monkey-patch to replace the `_query_server` method in `language_tool_python.LanguageTool` to use POST requests instead of GET requests.

### Implementation

**File**: `src/language_check/language_tool_patch.py`

The patch:
1. Replaces `requests.get(url, params=params)` with `requests.post(url, data=params)`
2. Sends parameters in the request body instead of the URL query string
3. Maintains all other functionality (retries, error handling, timeout)
4. Applied automatically when the language_check module is imported

### Configuration Updates

**File**: `src/language_check/language_tool_manager.py`

Updated server configuration to handle large documents:
- `maxTextLength`: 500,000 characters (increased from default ~50,000)
- `maxTextHardLength`: 1,000,000 characters (increased from default ~100,000)
- `maxCheckTimeMillis`: 120,000ms (2 minutes, already configured)

## Testing

### Before Fix
```bash
$ uv run python -m src.language_check.language_check --document Spanish/markdown/wjec-gcse-spanish-specification.md
ERROR: Language check failed after 4 attempt(s): http://127.0.0.1:8081/v2/: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
```

### After Fix
```bash
$ uv run python -m src.language_check.language_check --document Spanish/markdown/wjec-gcse-spanish-specification.md
INFO: Checking Spanish / wjec-gcse-spanish-specification.md
INFO: Completed Spanish / wjec-gcse-spanish-specification.md: 166 issue(s)
✓ Success!
```

## Files Modified

1. **src/language_check/language_tool_patch.py** (NEW)
   - Monkey-patch to use POST requests
   - Functions: `_query_server_post`, `apply_post_request_patch`, `revert_post_request_patch`

2. **src/language_check/language_check.py**
   - Import and apply the POST request patch on module load
   - Comment explaining why the patch is necessary

3. **src/language_check/language_tool_manager.py**
   - Updated `_DEFAULT_CONFIG` with higher text length limits
   - Added documentation about limits

## Future Considerations

### Upstream Fix
Consider submitting a pull request to `language-tool-python` to add native POST support for large documents. This would eliminate the need for the monkey-patch.

### Monitoring
If connection reset errors occur on other documents:
1. Check document size (`wc -c document.md`)
2. Enable DEBUG_MODE to see request details
3. Verify POST requests are being used (check logs)
4. Consider increasing `maxTextLength` and `maxTextHardLength` further if needed

### Alternative Approaches Considered
1. **Document Chunking**: Split large documents into smaller chunks
   - Rejected: Would lose context for grammar checking
2. **Upgrade library**: Check for newer version of language-tool-python
   - Not available: v2.9.5 is the latest as of Nov 2025
3. **Switch library**: Use different LanguageTool wrapper
   - Rejected: Current library is well-maintained and feature-rich

## Technical Details

### HTTP GET vs POST
- **GET**: Parameters in URL query string (limited to ~8-64KB depending on server)
- **POST**: Parameters in request body (virtually unlimited, typically up to 2GB)

### LanguageTool Server
The LanguageTool Java server supports both GET and POST for the `/check` endpoint. The POST endpoint expects form-encoded data (`application/x-www-form-urlencoded`).

### Request Format
```python
# Original (GET)
requests.get('http://localhost:8081/v2/check', params={'text': document, 'language': 'en-GB', ...})

# Patched (POST)
requests.post('http://localhost:8081/v2/check', data={'text': document, 'language': 'en-GB', ...})
```

The `data` parameter in requests.post automatically form-encodes the dictionary and sends it in the request body.
