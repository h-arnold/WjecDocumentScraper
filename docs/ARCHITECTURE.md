# Architecture and API Contracts (MUST CONSULT BEFORE CODE CHANGES)

This document defines how the scraper works, the public contracts you must preserve, and where to make changes safely.

## Overview

The tool downloads GCSE PDF documents from WJEC "Made for Wales" qualification pages. It can be used via:
- CLI: `main.py` (thin wrapper that imports from `src.cli`)
- Library API: `src.scraper` module (functions in `src/scraper/__init__.py`)
- Post-processing: `src.postprocessing` module (functions in `src/postprocessing/__init__.py`)
- Converters: `src.converters.converters` module (PDF to Markdown conversion)
- Gemini helper: `src/llm/gemini_llm.py` module — wraps the Google GenAI client, reads system instructions from Markdown, and loads `.env` values (such as `GEMINI_API_KEY`)
- LLM orchestration: `src/llm/provider.py`, `src/llm/service.py`, and `src/llm/provider_registry.py` describe the shared `LLMProvider` contract, a quota-aware `LLMService` orchestrator, and a registry that builds the active provider list (currently Gemini and the batch-enabled Mistral implementation) while honoring `LLM_PRIMARY`/`LLM_FALLBACK` hints; unit tests cover fallback, quota handling, and reporting behavior.
- Page utilities: `src.utils.page_utils` module (page marker extraction and navigation)
- Language check: `src.language_check.language_check` module (spelling and grammar checking) with report builders in `src.language_check.report_utils`

Python >= 3.12. Dependencies are managed with uv (see `docs/UV_GUIDE.md`).

## Data flow

1. Subject selection
   - Subjects are defined by `QUALIFICATION_URLS: dict[str, str]` (name → landing URL).
   - The CLI matches subject names case-insensitively.

2. HTML acquisition
   - `fetch_html(url: str) -> str`
   - Uses `requests` to GET (or sometimes POST) pages.
   - For some subjects, an additional site-specific key-documents endpoint is probed; absence or failure is non-fatal.

3. Link discovery (two strategies combined)
  - `iter_pdf_links(soup: BeautifulSoup, base_url: str) -> Iterable[tuple[title, url]]`
  - Anchors with href ending in `.pdf`. This function accepts a pre-parsed `BeautifulSoup` object and a base URL; it yields tuples `(title, absolute_url)`.
  - `iter_pdf_from_react_props(soup: BeautifulSoup, base_url: str) -> Iterable[tuple[title, url]]`
     - Parses embedded React props JSON inside `textarea.react-component--props`.
     - Extracts `listItems` entries with `Link` (URL) and `Name` (title).

4. Coalescing and title choice
  - `collect_pdf_links(url: str) -> list[tuple[pdf_url, title]]`
  - HTML for the provided landing URL is fetched; the function extracts links from the landing page and (where available) the Key Documents tab. URLs are de-duplicated; the “best” title is chosen by preferring the longest non-empty title per URL. The function returns a list of `(pdf_url, title)` pairs (not a map) to preserve ordering for callers.

5. Filenames and directories
   - `subject_directory_name(subject: str) -> str`
     - Normalises to filesystem-safe dir name by replacing runs of characters not in [A-Za-z0-9._-] with `-` and trimming leading/trailing hyphens. Note: `.` and `_` are allowed and preserved.
   - `sanitise_filename(title: str, url: str, existing: set[str]) -> str`
     - Returns a filesystem-safe filename. It lowercases and replaces runs of characters not in [A-Za-z0-9._-] with `-`, ensures the filename ends with `.pdf`, and appends `-N` when collisions occur (N starting from 2). The function also falls back to a name derived from the URL path if the title is empty.

6. Downloading
   - `download_file(url: str, dest: Path) -> None`
     - Uses `requests` to download bytes; partial files are removed on error.
  - `download_subject_pdfs(subject: str, url: str, output_root: Path, reporter: Callable[[str, Path, str], None] | None = None) -> tuple[int, Path]`
     - Drives the end-to-end process for a subject.
     - Calls `reporter(label, destination, url)` for progress if provided.

## Post-processing pipeline

Once PDFs have been downloaded, the optional organiser lives in `src/postprocessing/__init__.py` and can be triggered from the CLI via `--post-process` or `--post-process-only`.

1. Subject discovery
   - `find_subject_directories(root: Path) -> list[Path]`
     - Returns all direct subdirectories (one per subject) under the chosen output root.

2. File layout
   - `copy_root_pdfs(subject_dir: Path, pdf_directory: Path) -> list[Path]`
     - Copies any PDFs in the subject root into the dedicated `pdfs/` subdirectory, removing originals after a successful copy.

3. Markdown conversion
   - The conversion system uses a pluggable architecture defined in `src/converters/converters.py`:
     - `PdfToMarkdownConverter` - Abstract base class for all converters
     - `MarkItDownConverter` - Uses [MarkItDown](https://pypi.org/project/markitdown/) (default)
     - `MarkerConverter` - Uses [marker](https://github.com/datalab-to/marker) for advanced OCR and layout detection
     - `create_converter(converter_type: str) -> PdfToMarkdownConverter` - Factory function to create converters
   - `convert_pdf_to_markdown(converter: PdfToMarkdownConverter, pdf_path: Path, markdown_directory: Path) -> Path`
     - Uses the provided converter to create a Markdown rendition for each PDF inside `markdown/`.
   - `process_single_pdf(pdf_path: Path, converter_type: str = "markitdown") -> SinglePdfResult`
     - Processes a single PDF file: copies to `pdfs/` if in subject root, converts to Markdown.
     - Returns `SinglePdfResult` with `success`, `pdf_path`, `markdown_path`, and `error` fields.
     - Validates that the PDF is within a subject directory structure (not at Documents root).

4. Orchestration
   - `process_subject(subject_dir: Path, converter_type: str = "markitdown") -> SubjectResult`
     - Copies PDFs, then converts each to Markdown using the specified converter, accumulating counts and per-file errors.
   - `run(root: Path, max_workers: int | None = None, converter_type: str = "markitdown") -> list[SubjectResult]`
     - Executes each subject in a `ThreadPoolExecutor`, respecting the optional worker limit and emitting simple progress prints.
   - CLI integration happens in `main.py` via `perform_post_processing(...)`, which prints aggregate totals and maps exit codes to success (0), "no directories" (1), or error (2).
   - For single-file processing, use `main.py --post-process-file <path>` which calls `process_single_pdf` directly.

### Post-processing invariants

- Each subject directory contains `pdfs/` and `markdown/` subdirectories after processing; the root directory remains untouched aside from removing PDFs that were relocated.
- Markdown files mirror the PDF stem (`name.md`), preserving hyphenated filenames produced during download.
- Concurrency is opt-in; when using multiple workers, per-subject work must remain independent so that converter instances are created per subject to avoid thread-safety issues.
- Failures in conversion are logged and recorded, but other files continue processing; exit code aggregates whether any subject produced errors.
- Converters must implement the `PdfToMarkdownConverter` interface with `convert(pdf_path: Path) -> ConversionResult` and `close() -> None` methods.

## Public API (contracts)

Keep function names, parameter orders, and behaviors stable unless you update all call sites and the CLI accordingly.

- `fetch_html(url) -> str`
  - Must raise for non-recoverable HTTP errors; may return empty string only on explicitly handled non-fatal conditions.

- `iter_pdf_links(soup, base_url) -> Iterable[(title, url)]`
  - Accepts a `BeautifulSoup` object and the page's base URL. Must ignore non-PDF links and return absolute URLs when possible; yields `(title, absolute_url)` where `title` may be empty (caller falls back to URL basename).

- `iter_pdf_from_react_props(soup, base_url) -> Iterable[(title, url)]`
  - Parses embedded JSON in `textarea.react-component--props`. Must be resilient to missing/invalid JSON and return an empty iterator on failure; yields `(title, absolute_url)`.

- `collect_pdf_links(url) -> list[tuple[pdf_url, title]]`
  - Fetches the landing page and optionally the Key Documents endpoint; must deduplicate URLs and choose the longest non-empty title per URL. Returns a list of `(pdf_url, title)` tuples (order is deterministic based on the page contents and title sorting used by callers).

- `subject_directory_name(subject) -> str`
  - Must replace runs of characters not in the set `[A-Za-z0-9._-]` with `-`, coalesce repeats, and trim leading/trailing `-`. Note that `.` and `_` are preserved.

- `sanitise_filename(title, url, existing) -> str`
  - Must be lowercase, hyphenated; must avoid collisions by appending `-N` where N ≥ 2.

- `download_subject_pdfs(subject, output_dir, reporter=None) -> None`
  - Must call `reporter(label, destination, url)` when provided.
  - Must not crash on individual network/IO errors; continue with other files.
  - Returns a tuple `(count, subject_dir)` where `count` is number of PDFs downloaded and `subject_dir` is the directory the files were saved into.

### Page utilities (`src/utils/page_utils.py`)

Functions for working with page markers in Markdown documents. Page markers follow the format `{N}------------------------------------------------`.

- `find_page_markers(text: str) -> list[PageMarker]`
  - Returns all page markers sorted by position in text.
  - `PageMarker` is a dataclass with `page_number: int` and `position: int`.

- `build_page_number_map(text: str) -> dict[int, int]`
  - Creates a mapping from character position to page number.
  - Used by `language_check.py` to determine which page an issue occurs on.
  - Returns empty dict if no page markers found.

- `get_page_number_at_position(position: int, page_map: dict[int, int]) -> int | None`
  - Helper to get page number at a specific character position.

- `extract_page_text(text: str, page_number: int | None = None, start_page: int | None = None, end_page: int | None = None) -> str`
  - Extracts text from a single page or range of pages.
  - Extracted text includes the page markers.
  - Returns empty string if requested pages not found.
  - Either `page_number` or both `start_page` and `end_page` must be specified.

- `extract_pages_text(text: str, page_numbers: Iterable[int]) -> dict[int, str]`
  - Extracts multiple non-consecutive pages.
  - Returns dict mapping page numbers to their text.
  - Pages not found are omitted from result.

**Invariants:**
- Page markers are always included in extracted text to maintain context.
- Page numbers can be non-sequential in the document.
- Positions before the first marker have no page number (return None).
- Functions are defensive: invalid page numbers return empty string/None rather than raising.

## Language Issue Model

The `LanguageIssue` model (defined in `src/models/language_issue.py`) is a unified Pydantic model that serves two purposes:

1. **LanguageTool Detection**: Stores detected issues from LanguageTool with core fields like `rule_id`, `message`, `issue_type`, `replacements`, `highlighted_context`, etc.

2. **LLM Categorisation**: Extends detection data with optional LLM-assigned fields: `error_category`, `confidence_score`, and `reasoning`.

### Core Fields (from LanguageTool)

- `filename: str` - Document filename (required)
- `rule_id: str` - Rule identifier from the tool (required)
- `message: str` - Tool-provided explanatory message (required)
- `issue_type: str` - Type from tool (e.g., "misspelling", "grammar") (required)
- `replacements: List[str]` - List of suggested replacements (default: empty list)
- `context: str` - Original context string (deprecated, for backward compatibility)
- `highlighted_context: str` - Context with issue highlighted (e.g., "This is **wrong**") (required)
- `issue: str` - The actual issue text extracted (required)
- `page_number: int | None` - Optional page number in document
- `issue_id: int` - Auto-incremented per document (-1 if not set, default: -1)
- `pass_code: PassCode | None` - Indicates which workflow pass produced or last updated the issue (`LT` for LanguageTool detection, `LTC` for LLM categorisation)

### LLM Categorisation Fields (Optional)

- `error_category: ErrorCategory | None` - LLM-assigned category (None if not categorised)
- `confidence_score: int | None` - LLM confidence 0-100 (None if not categorised)
- `reasoning: str | None` - LLM reasoning for categorisation (None if not categorised)

### Usage Patterns

**Direct Creation** (for LanguageTool detection):
```python
issue = LanguageIssue(
    filename="test.md",
    rule_id="GRAMMAR_RULE",
    message="Subject-verb agreement",
    issue_type="grammar",
    replacements=["is"],
    context="plain context",
    highlighted_context="They **are** happy",
    issue="are"
)
```

**From LLM Response** (for categorisation workflow):
```python
# LLM returns fields with '_from_tool' suffix
llm_data = {
    "rule_from_tool": "GRAMMAR_RULE",
    "type_from_tool": "grammar",
    "message_from_tool": "Subject-verb agreement",
    "suggestions_from_tool": ["is"],
    "context_from_tool": "They are happy",
    "error_category": "ABSOLUTE_GRAMMATICAL_ERROR",
    "confidence_score": 90,
    "reasoning": "Clear subject-verb agreement error"
}
issue = LanguageIssue.from_llm_response(llm_data, filename="test.md")
```

### Validation Rules

- All core fields must be non-empty strings after normalisation (whitespace trimming)
- If any LLM categorisation field is provided, all three (`error_category`, `confidence_score`, `reasoning`) must be provided
- `confidence_score` must be between 0-100 (inclusive)
- `error_category` must be a valid `ErrorCategory` enum value
- The model uses Pydantic validators to normalize strings, handle lists, and enforce constraints

### Migration Notes

The unified model replaces the previous separate classes:
- `LanguageIssue` (dataclass in `src/language_check/language_issue.py`) - now re-exports the unified model
- `LlmLanguageIssue` (Pydantic model in `src/models/issue.py`) - replaced by unified model

All existing code continues to work via backward-compatible imports, but the underlying implementation is now unified.

## Parsing rules and edge cases

- Key-documents endpoint: Some subjects expose PDFs only via this endpoint; the scraper should attempt to fetch it and proceed if unavailable.
- React props: Props are found in `textarea.react-component--props`; structure contains `listItems` with `Name` and `Link`.
- Titles: Prefer more descriptive (longer) titles when multiple are available for the same URL.
- Duplicates: Same URL appears once; filenames still must be unique on disk (use `sanitise_filename`).

## Change guidelines (must follow)

- Subjects
  - Edit `QUALIFICATION_URLS` in `src/scraper/__init__.py` to add/remove subjects. Keep user-facing names stable; CLI matches case-insensitively.

- Filenames and directories
  - Do not change normalization logic casually. If you must, update both `sanitise_filename` and `subject_directory_name` together and verify no regressions in already-downloaded structures.

- Progress reporting
  - Keep the `reporter(label, destination, url)` hook; the CLI depends on it for user feedback.

- Error handling
  - Log and continue on network/IO errors; ensure partial files are cleaned up on failure.

- Performance
  - Current implementation is synchronous and acceptable for the expected dataset size. If adding concurrency, ensure deterministic filenames and avoid race conditions when writing files.
  - Post-processing uses threads per subject; keep operations per subject independent so that shared state is not mutated unsafely.

- Post-processing
  - Preserve the `SubjectResult` dataclass fields (`copied`, `converted`, `errors`) so CLI summaries remain accurate.
  - Keep progress prints (`Starting...` / `Finished...`) concise; they are relied upon when running with many subjects.
  - If changing the Markdown conversion strategy, ensure conversion exceptions are caught and recorded without halting other subjects.

- Language Issue Model
  - The `LanguageIssue` model in `src/models/language_issue.py` is the single source of truth for all language issues.
  - Do not create parallel issue classes; extend the unified model if new fields are needed.
  - When adding LLM-specific fields, ensure they remain optional so the model works for both detection and categorisation use cases.
  - Use `LanguageIssue.from_llm_response()` to parse LLM responses with `_from_tool` suffix fields.
  - Maintain backward compatibility via re-export in `src/language_check/language_issue.py`.

## When to update this document

- You add/remove public functions in `src/scraper/__init__.py` or `src/utils/page_utils.py`.
- You change filename or directory normalization.
- You modify how subjects are configured or matched.
- You change link-discovery strategies or title selection rules.
- You alter the post-processing pipeline (new steps, different outputs, CLI behavior changes).
- You modify page marker format or page extraction logic.
- You change the `LanguageIssue` model structure or add new fields.
