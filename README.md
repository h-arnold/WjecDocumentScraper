# WJEC Document Scraper

Command-line tool for downloading PDF documents exposed on the WJEC GCSE Made-for-Wales qualification pages. The scraping logic lives in `wjec_scraper.py` and can be reused programmatically, while `main.py` provides a friendly CLI.

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
