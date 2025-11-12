# WJEC Document Scraper

A command-line which:

 - scrapes all WJEC GCSE Made-for-Wales qualification pages for linked PDF documents
 - converts them into Markdown format for easier reading and processing
 - uses [Language Tool](https://languagetool.org/) to check the converted documents for spelling and grammar issues, with multi-language support for French and German subjects and soon, Spanish.
 - uses LLMs to 
## Why does this tool need to exist?

[See the comment thread on LinkedIn that started all of this off.](https://www.linkedin.com/feed/update/urn:li:ugcPost:7386346400038682624?commentUrn=urn%3Ali%3Acomment%3A%28ugcPost%3A7386346400038682624%2C7386507884081270784%29&dashCommentUrn=urn%3Ali%3Afsd_comment%3A%287386507884081270784%2Curn%3Ali%3AugcPost%3A7386346400038682624%29).

Because it's clear that the WJEC do not have any quality assurance process for their qualification materials, and teachers in Wales are left to pick up the pieces.

At the moment, no one with any power to do anything seems to care. It's too easy to fob off concerns by pretending that it's an isolated incident. I intend to change that by demonstrating that this is a systemic issue across *all* WJEC GCSE Made-for-Wales qualification materials and I will make some pretty graphs to prove it.




Tagging the press in that thread has achieved nothing as of the time of this scrape, all the errors are still there!


# Technical Details

Command-line tool for downloading PDF documents exposed on the WJEC GCSE Made-for-Wales qualification pages. The scraping logic lives in `src/scraper/__init__.py` and can be reused programmatically, while `main.py` provides a friendly CLI.

## Setup

Dependencies are managed with [uv](https://github.com/astral-sh/uv).

```bash
uv sync
```

## CLI Usage

List every subject that the scraper knows about:

```bash
uv run python main.py --list-subjects
```

Download all configured subjects into the default `Documents/` folder:

```bash
uv run python main.py
```

Download a subset of subjects into a custom directory:

```bash
uv run python main.py --subjects "Art and Design" French --output ./wjec-pdfs
```

Preview what would be downloaded without touching the filesystem:

```bash
uv run python main.py --subjects Geography --dry-run
```

All files are grouped by subject using a filesystem-safe folder name, and duplicate filenames are handled automatically by appending numeric suffixes where required.

### Post-processing downloads

The CLI can tidy downloaded folders and convert PDFs to Markdown using your choice of converter:

- `--post-process` runs the organiser once downloads finish (skipped during `--dry-run`).
- `--post-process-only` skips downloading and processes the existing output directory.
- `--post-process-file <path>` processes a single PDF file (copy to pdfs/ if needed, convert to Markdown). Cannot be combined with `--post-process` or `--post-process-only`.
- `--post-process-workers N` limits how many subject folders are handled concurrently (ignored for the `marker` converter, which always runs a single worker).
- `--converter {markitdown,marker}` selects the PDF to Markdown converter (default: `markitdown`).

#### Available Converters

**MarkItDown** (default): Fast, reliable converter using Microsoft's MarkItDown library. Suitable for most use cases.

**Marker**: Advanced converter using the [marker](https://github.com/datalab-to/marker) library with superior OCR and layout detection capabilities. Requires downloading ML models on first use and may need GPU resources for optimal performance. Post-processing always runs with a single worker to avoid duplicate model downloads, even if a higher worker count is requested.

Examples:

```bash
# Download, then organise PDFs into a pdfs/ folder and create markdown/ outputs (default converter)
uv run python main.py --subjects Geography --post-process

# Use marker for higher quality conversion
uv run python main.py --subjects Geography --post-process --converter marker

# Only re-run the organiser against an existing output directory with marker (single worker enforced)
uv run python main.py --output Documents --post-process-only --converter marker

# Process a single PDF file
uv run python main.py --post-process-file Documents/Art-and-Design/sample.pdf --converter markitdown
```

### Long-running batch processing

For processing all subjects over an extended period (potentially days), use the `scripts/process_all_subjects.py` script. This script is designed for unattended operation on a server with automatic progress tracking and resumption capabilities.

Features:
- **Git-based checkpointing**: Creates or checks out a branch (default: `processedDocuments`) and commits after each subject completes
- **State file tracking**: Maintains `unprocessedSubjects.txt` to track remaining subjects
- **Resumable**: Can be interrupted and resumed from where it left off
- **Sequential processing**: Processes subjects one at a time to avoid resource exhaustion
- **Robust error handling**: Continues processing if a single subject fails

Usage:

```bash
# Start processing all subjects (or resume if previously interrupted)
uv run python scripts/process_all_subjects.py

# Preview what would be processed without making changes
uv run python scripts/process_all_subjects.py --dry-run

# Reset and start from scratch
uv run python scripts/process_all_subjects.py --reset

# Use a different branch name
uv run python scripts/process_all_subjects.py --branch my-processed-docs

# Use markitdown converter instead of marker
uv run python scripts/process_all_subjects.py --converter markitdown

# Specify custom paths
uv run python scripts/process_all_subjects.py --root ./MyDocuments --state-file ./state.txt
```

The script discovers all subject directories in the Documents folder, processes each one using `main.py --post-process-only`, and commits the changes to a dedicated branch. If interrupted (e.g., server restart), simply run the script again to continue from where it left off.

## Page utilities

The `page_utils.py` module provides utilities for working with page markers in Markdown documents. After post-processing, Markdown files contain page markers in the format `{N}------------------------------------------------` where N is the page number.

Key functions:

- `find_page_markers(text)` - Find all page markers in a document
- `build_page_number_map(text)` - Create a position-to-page-number mapping (used by language checking)
- `extract_page_text(text, page_number=N)` - Extract text from a specific page
- `extract_page_text(text, start_page=N, end_page=M)` - Extract a range of pages
- `extract_pages_text(text, [N, M, ...])` - Extract multiple non-consecutive pages

Example:

```python
from page_utils import extract_page_text, find_page_markers
from pathlib import Path

# Load a document
doc = Path("Documents/Business/markdown/gcse-business---guidance-for-teaching-unit-1.md")
text = doc.read_text()

# Find all pages
markers = find_page_markers(text)
print(f"Document has {len(markers)} pages")

# Extract a specific page (includes the page marker)
page_3 = extract_page_text(text, page_number=3)

# Extract a range of pages
pages_0_to_2 = extract_page_text(text, start_page=0, end_page=2)
```

The extracted text includes the page markers themselves to maintain context. See `tests/test_page_utils.py` for comprehensive examples.

## Gemini LLM helper

The `GeminiLLM` helper in `gemini_llm.py` wraps the Google GenAI SDK so you can reuse system prompts stored in Markdown files when calling the Gemini API.

- Reads the system instruction from a Markdown file when instantiated.
- Joins user prompt fragments with newlines before sending them to the API.
- Calls the `gemini-flash-2.5` model with the maximum supported thinking budget (24,576 tokens) via `google.genai.types.ThinkingConfig`.
- Loads environment variables from a `.env` file automatically (useful for storing `GEMINI_API_KEY`).
- Expects `GEMINI_API_KEY` to be present in the environment, matching [Google's Python quickstart](https://ai.google.dev/gemini-api/docs/get-started/python).

Example:

```python
from gemini_llm import GeminiLLM

llm = GeminiLLM("prompts/system.md")
response = llm.generate([
	"Summarise the recent downloads.",
	"Highlight any missing PDFs."
])
print(response.text)
```

Refer to the [Gemini text generation guide](https://ai.google.dev/gemini-api/docs/text-generation) for additional configuration options.
