# Dev Workflows and Testing (MUST CONSULT BEFORE TESTING OR DEBUGGING)

This guide lists quick checks, debugging patterns, and testing conventions for the scraper.

## Quick Checks

- List subjects:
```bash
uv run python main.py --list-subjects
```
- Dry-run a subject without writing files:
```bash
uv run python main.py --subjects Geography --dry-run
```
- Try multiple subjects and custom output:
```bash
uv run python main.py --subjects "Art and Design" French -o ./wjec-pdfs
```
- Post-process an existing download set only:
```bash
uv run python main.py --post-process-only --post-process-workers 4
```
- Download, then immediately post-process a subject:
```bash
uv run python main.py --subjects Geography --post-process
```

## Interactive Debugging

Launch a REPL with project deps:
```bash
uv run python
```
In REPL:
```python
from src.scraper import (
    fetch_html,
    collect_pdf_links,
    iter_pdf_links,
    iter_pdf_from_react_props,
    sanitise_filename,
    subject_directory_name,
)
html = fetch_html("https://example.com/subject")
links = list(iter_pdf_links(html))
react_links = list(iter_pdf_from_react_props(html))
filename = sanitise_filename("Sample PDF", "https://example.com/sample.pdf", set())
```

## Working with Page Utilities

The `src.utils.page_utils` module provides utilities for working with page markers in Markdown documents. Page markers follow the format `{N}------------------------------------------------`.

Example usage:
```python
from src.utils.page_utils import (
    find_page_markers,
    build_page_number_map,
    extract_page_text,
    extract_pages_text,
)
from pathlib import Path

# Load a document
doc = Path("Documents/Business/markdown/gcse-business---guidance-for-teaching-unit-1.md")
text = doc.read_text()

# Find all page markers
markers = find_page_markers(text)
print(f"Found {len(markers)} pages")

# Extract a single page
page_3 = extract_page_text(text, page_number=3)

# Extract a range of pages
pages_0_to_2 = extract_page_text(text, start_page=0, end_page=2)

# Extract multiple non-consecutive pages
pages = extract_pages_text(text, [0, 5, 10])
for page_num, page_text in pages.items():
    print(f"Page {page_num}: {len(page_text)} characters")

# Build a position-to-page map (used by language_check.py)
page_map = build_page_number_map(text)
position = text.find("some text")
page_num = page_map.get(position)
```

## Minimal Test Scaffold

We use pytest. Add it first if missing:
```bash
uv add --dev pytest
```
Example tests to start with (create `tests/test_filenames.py`):
```python
import re
from src.scraper import sanitise_filename, subject_directory_name

def test_subject_directory_name_basic():
    assert subject_directory_name("Cymraeg Language and Literature").startswith("Cymraeg-Language")


def test_sanitise_filename_uniqueness():
    existing = {"doc.pdf", "doc-2.pdf"}
    name = sanitise_filename("Doc", "http://x/doc.pdf", existing)
    assert re.match(r"doc-(\d+)\.pdf", name)
```
Run tests:
```bash
uv run pytest -q
```

## Logging and Failure Handling

- Network/IO errors should log a message and continue; partial files are removed on failure.
- Duplicate URLs are coalesced; duplicate filenames receive `-N` suffixes.
- Post-processing logs conversion failures per file and continues; the CLI exit code is 2 when any subject reports errors.

## PR Hygiene & Validation

- Keep changes small and aligned with contracts in `docs/ARCHITECTURE.md`.
- After any scraping or filename change:
  - Run a dry-run for a couple of subjects.
  - If tests exist, run `uv run pytest` and fix failures.
- After modifying post-processing logic:
    - Run `uv run python main.py --post-process-only` against a populated output folder.
    - Inspect a sample of generated Markdown files to confirm the converter output still matches expectations.

## When to Update This Document

- New debugging utilities or reporter hooks are added.
- We adopt a new testing pattern or directory structure.
