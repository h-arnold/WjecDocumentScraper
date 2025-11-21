# Scripts reference

This file summarises the helper scripts in the `scripts/` folder, how they are used, and where to find related docs.

Each script section includes a short description, recommended command-line usage (use `uv` for runtime commands where shown elsewhere in the project), and references to unit tests or documentation where they exist.

## scripts/process_all_subjects.py

Purpose: Post-process PDF files into Markdown in an incremental, resumable manner. Designed for long-running processing (hours to days) with git-based checkpointing.

Usage examples (from `README.md` and script docstring):

  - Start or resume processing all subjects:

    uv run python scripts/process_all_subjects.py

  - Preview processing without making any changes:

    uv run python scripts/process_all_subjects.py --dry-run

  - Reset state and start from scratch:

    uv run python scripts/process_all_subjects.py --reset

  - Use a different branch for processed documents:

    uv run python scripts/process_all_subjects.py --branch myBranch

  - Converter backend is `marker` (MarkItDown support removed).

Notes and behaviour:
  - Creates or checks out a branch (default: `processedDocuments`) to commit progress.
  - Maintains a state file (default `unprocessedFiles.txt`) so the run can be resumed.
  - Converts PDFs in each subject folder to Markdown one file at a time using the project's postprocessing logic.
  - Commits after each subject or conversion step, to keep progress incremental and resilient to interruptions.

Related tests: `tests/test_process_all_subjects.py`, `tests/test_error_logging.py`

## scripts/deduplicate_language_issues.py

Purpose: Read a CSV language-check report (as produced by the language-check tooling), remove duplicates based on configurable key columns, and write a deduplicated CSV.

Usage example (from script docstring):

  python scripts/deduplicate_language_issues.py input.csv -o output.csv

Flags of note:
  - `--keys` — comma-separated list of header names to use as the dedupe key. When omitted the script uses a narrow default: `Issue` (this collapses identical spelling suggestions by token).  Specify other columns with `--keys` when different behaviour is desired.
  - `--ignore-case` — ignore case when comparing keys.
  - `--keep` — `first` or `last`, to choose which row is kept.
  - `--count` — add an `Occurrences` column showing how many rows were collapsed for the dedupe key.

Behaviour:
  - By default only rows for the MORFOLOGIK spelling rule are included (script filters by `Rule ID == 'MORFOLOGIK_RULE_EN_GB'`).
  - Outputs a new CSV by default to `input-deduped.csv` unless `-o`/`--output` is provided.

Related tests: `tests/test_deduplicate_language_issues.py`

## scripts/manage_language_ignore.py

Purpose: Add new words to the `DEFAULT_IGNORED_WORDS` mapping in `src/language_check/language_check_config.py` using a structured JSON manifest. Validates roots, canonicalises categories, enforces word hygiene, and groups inserts by subject.

This script's behaviour and validation are documented under `docs/manage_language_ignore.md`. The docs contain the canonical JSON input structure and examples; please consult them before using the script.

Usage examples (from docs):

  uv run python scripts/manage_language_ignore.py data/language-ignore/history.json

  uv run python scripts/manage_language_ignore.py data/language-ignore/history.json --dry-run

Notes:
  - The script validates subject names against `QUALIFICATION_URLS`.
  - Proper nouns must start with an uppercase character.
  - Allowed characters in ignored words are limited; use `docs/manage_language_ignore.md` for details.

## scripts/count_ize_suffixes.py

Purpose: Count occurrences of words that end with `-ize` (American style) in Markdown files under `Documents/`, excluding certain false positives, and generate an SVG badge summarising the count.

Usage example:

  python scripts/count_ize_suffixes.py --output badges/ize-suffixes.svg

Notes:
  - The script filters non-markdown files and uses a small exclusion set for words such as `size`, `prize`, `seize`, `bitesize`, etc.
  - The *generated* badge is committed via a GitHub action; see `.github/workflows/update-ize-badge.yml` for the automation that refreshes the badge on a scheduled basis.

## scripts/count_leaners.py

Purpose: Count whole-word occurrences of the supplied word (e.g. `leaners`) across Markdown files in `Documents/` and generate a badge SVG with the count.

Usage example (used in GitHub workflow):

  python3 scripts/count_leaners.py --word "leaners" --output badges/leaners.svg

Notes:
  - The script is used from `.github/workflows/update-leaners-badge.yml` which runs it daily and commits the badge if changed.

## src/scripts/document_stats.py

Purpose: Generate statistics about documents in the `Documents/` folder, including counts of PDF files, converted markdown files, and total pages per subject.

Usage example:

  uv run python src/scripts/document_stats.py

Output:
  - Number of PDF documents per subject (from `pdfs/` folder)
  - Number of converted markdown documents per subject (from `markdown/` folder)
  - Total pages per subject (determined by the last page marker `{N}----` in each markdown document)
  - Grand totals for all subjects

Notes:
  - Page markers follow the format `{N}------------------------------------------------` where N is the 0-indexed page number.
  - Documents without page markers are counted as single-page documents.
  - The script uses the `find_page_markers` function from `src.utils.page_utils` to parse page information.

Related tests: `tests/test_document_stats.py`

## scripts/test_multilang_manual.py and `scripts/README_MANUAL_TESTING.md`

Purpose: Manual test harness for multi-language language checking. The script exercises LanguageTool downloads and multi-language checking behaviour (English + subject languages) and is used when network access is available.

Usage:

  uv run python scripts/test_multilang_manual.py

See `scripts/README_MANUAL_TESTING.md` for details on the tests, prerequisites, network caveats and expected output. Automated tests that don't require network are provided under `tests/`.

## Where to look for further documentation

- `docs/manage_language_ignore.md` — details and JSON examples for `manage_language_ignore.py`.
- `README.md` — high-level usage for `process_all_subjects.py` and the badge scripts.
- `.github/workflows` — automated runs for badges which show how `count_ize_suffixes.py` and `count_leaners.py` are used in CI.

If you want a new script added to this list, include a short docstring in the script plus a small example of expected usage and update this file.
