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
- `--post-process-workers N` limits how many subject folders are handled concurrently.
- `--converter {markitdown,marker}` selects the PDF to Markdown converter (default: `markitdown`).

#### Available Converters

**MarkItDown** (default): Fast, reliable converter using Microsoft's MarkItDown library. Suitable for most use cases.

**Marker**: Advanced converter using the [marker](https://github.com/datalab-to/marker) library with superior OCR and layout detection capabilities. Requires downloading ML models on first use and may need GPU resources for optimal performance.

Examples:

```bash
# Download, then organise PDFs into a pdfs/ folder and create markdown/ outputs (default converter)
uv run python main.py --subjects Geography --post-process

# Use marker for higher quality conversion
uv run python main.py --subjects Geography --post-process --converter marker

# Only re-run the organiser against an existing output directory with marker
uv run python main.py --output Documents --post-process-only --post-process-workers 4 --converter marker
```
