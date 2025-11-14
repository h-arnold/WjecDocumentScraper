# Manual Testing for Multi-Language Support

This directory contains a manual test script for verifying the multi-language language checking functionality.

## Prerequisites

- Network access to download LanguageTool components
- Python 3.12+
- All project dependencies installed

## Running the Manual Test

```bash
# From the project root
uv run python scripts/test_multilang_manual.py
```

## What It Tests

The manual test script verifies:

1. **Language Detection**: Tests that subject names correctly map to language codes
   - French → en-GB + fr
   - German → en-GB + de
   - Other subjects → en-GB only

2. **French Document Checking**: Creates a test document with French and English content,
   then checks it with both French and English language tools.

3. **Subject-Specific Handling**: Verifies that German and English subjects use
   different language tool combinations.

## Expected Behavior

When run with network access:
- The script will download LanguageTool components (may take a minute on first run)
- Each test section will show ✓ for success or ✗ for failure
- French documents will be checked with English and French dictionaries
- German documents will be checked with English and German dictionaries
- Other subjects will only use English

## Without Network Access

If you don't have network access, the automated unit tests provide coverage:

```bash
# Run all language check tests
uv run pytest tests/test_language_check.py tests/test_language_check_multilang.py -v

# Tests will skip integration tests that require network
# All unit tests should pass
```

## Troubleshooting

If the manual test fails:
- Check your network connection
- Ensure you can reach `internal1.languagetool.org`
- The first run may take longer as it downloads LanguageTool (~200MB)
- Subsequent runs will use the cached download

## Automated Testing

The project includes comprehensive automated tests that don't require network access:

- `tests/test_language_check.py` - Core language checking tests
- `tests/test_language_check_multilang.py` - Multi-language support tests