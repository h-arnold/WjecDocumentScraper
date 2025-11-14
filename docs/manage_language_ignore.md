# Managing the language-check ignore list

`manage_language_ignore.py` is the canonical way to append new words to `DEFAULT_IGNORED_WORDS` without duplications, grouping entries by subject and category.

## Validation steps

1. **Subject sanity**: The JSON `subject` field must match one of the keys defined in `src/scraper/__init__.py` (`QUALIFICATION_URLS`). Partial or misspelled names will be rejected, but case-insensitive matching allows `"history"` to resolve to `"History"`.
2. **Word hygiene**: Words are trimmed, must be shorter than or equal to the longest existing entry, and can only contain letters, digits, spaces, hyphens, periods, and apostrophes. Proper nouns must begin with an uppercase character.
3. **Duplicates**: Entries already present in the config are skipped automatically.

## Usage

Prepare a JSON manifest (e.g., `data/language-ignore/<subject>.json`) that follows this structure:

```json
[{
  "subject": "History",
  "words": [
    {"word": "Cynan", "category": "Proper Noun"}, #Note - must be capitalised.
    {"word": "ferch", "category": "other"},
    {"word": "motte", "category": "Technical Term"}
  ]
}]
```

Run the script via `uv`:

```bash
uv run python scripts/manage_language_ignore.py data/language-ignore/history.json
```

Use `--dry-run` to preview the inserted block:

```bash
uv run python scripts/manage_language_ignore.py data/language-ignore/history.json --dry-run
```

## Distribution tips

- Maintain per-subject JSON files under `data/language-ignore/` for easier auditing.
- Aggregate them before applying or run the script repeatedly with different files.
- If you genuinely need longer entries than current warnings allow, update the existing config first so the length ceiling rises naturally.
