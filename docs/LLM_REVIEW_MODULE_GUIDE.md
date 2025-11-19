# LLM Review Module Implementation Guide

This guide explains how to create a new LLM-based review module (e.g., `llm_proofreader`, `llm_factchecker`) using the shared infrastructure in `src.llm_review.core`.

## Overview

The `src.llm_review.core` package provides a standard framework for:
1.  **Loading Issues**: Reading `language-check-report.csv` and grouping by document.
2.  **Batching**: Chunking issues and retrieving relevant page context from Markdown files.
3.  **State Management**: Tracking which batches are complete to allow resuming.
4.  **Runner Logic**: Handling the retry loop, validation, and logging.
5.  **Batch API Support**: Orchestrating async jobs via providers like Gemini.

To implement a new module, you essentially subclass the core components and provide your specific prompts, validation logic, and output format.

## Architecture

A typical module `src/llm_review/llm_new_task/` consists of:

*   `config.py`: Subclass of `ReviewConfiguration`.
*   `prompt_factory.py`: Logic to render Jinja2 templates.
*   `runner.py`: Subclass of `ReviewRunner` (the main logic).
*   `persistence.py`: Wrappers for saving results (optional but recommended).
*   `batch_orchestrator.py`: Subclass/Wrapper for `BatchOrchestrator`.
*   `batch_cli.py`: CLI subcommands for batch operations.
*   `cli.py`: Main entry point.

## Implementation Steps

### 1. Create Directory Structure

Create `src/llm_review/llm_your_task/` with an empty `__init__.py`.

### 2. Define Configuration (`config.py`)

Subclass `ReviewConfiguration` to define where your output files go and what columns they have.

```python
from dataclasses import dataclass
from pathlib import Path
from src.models.document_key import DocumentKey
from ..core.config import ReviewConfiguration

@dataclass
class YourTaskConfiguration(ReviewConfiguration):
    def get_output_path(self, key: DocumentKey) -> Path:
        # Define where output CSVs are saved
        # e.g. Documents/Subject/your_task_reports/filename.csv
        report_dir = self.output_base_dir / key.subject / self.output_subdir
        report_dir.mkdir(parents=True, exist_ok=True)
        
        filename = key.filename
        if filename.endswith(".md"):
            filename = filename[:-3] + ".csv"
            
        return report_dir / filename
```

### 3. Create Prompt Templates

Add templates to `src/prompt/templates/`. You usually need:
*   `system_your_task.md`: The system instruction (persona, rules).
*   `user_your_task.md`: The user prompt containing the issue table and context.

**Tip**: Use `{{ issue_table }}` and `{{ page_context }}` in your templates.

### 4. Implement Prompt Factory (`prompt_factory.py`)

Create a function to render your templates.

```python
from src.prompt.render_prompt import render_prompts
from ..core.batcher import Batch

def build_prompts(batch: Batch) -> list[str]:
    # Prepare context for Jinja2
    page_context_list = [
        {"page_number": p, "content": c} 
        for p, c in sorted(batch.page_context.items())
    ]
    
    context = {
        "subject": batch.subject,
        "filename": batch.filename,
        "issue_table": batch.markdown_table,
        "page_context": page_context_list,
    }

    # Render system and user prompts
    system, user = render_prompts(
        "system_your_task.md", 
        "user_your_task.md", 
        context
    )
    return [system, user]
```

### 5. Implement Runner (`runner.py`)

Subclass `ReviewRunner`. This is where you define how to validate the LLM's response.

```python
from typing import Any
from src.models import LanguageIssue
from ..core.review_runner import ReviewRunner
from .config import YourTaskConfiguration
from .prompt_factory import build_prompts

class YourTaskRunner(ReviewRunner):
    def __init__(self, llm_service, state, **kwargs):
        # Initialize config
        config = YourTaskConfiguration(
            # ... set defaults or pass from kwargs ...
            output_csv_columns=["issue_id", "your_new_column", "reasoning"]
        )
        super().__init__(llm_service, state, config)

    def build_prompts(self, batch):
        return build_prompts(batch)

    def validate_response(self, response: Any, issues: list[LanguageIssue]):
        validated_results = []
        failed_ids = set(i.issue_id for i in issues)
        errors = {}

        if not isinstance(response, list):
            return [], failed_ids, {"batch": ["Expected list"]}

        for item in response:
            # 1. Validate item structure (pydantic or manual)
            # 2. Ensure issue_id exists in the batch
            # 3. Merge with original issue data if needed
            
            # Example:
            if "issue_id" in item and item["issue_id"] in failed_ids:
                validated_results.append(item)
                failed_ids.discard(item["issue_id"])
        
        return validated_results, failed_ids, errors
```

### 6. Implement Batch Orchestrator (`batch_orchestrator.py`)

You need a class that inherits from `BatchOrchestrator` (or uses it) to handle the asynchronous results. The critical part is `_process_batch_response`, which must perform the same validation/merging logic as your Runner.

```python
from ..core.batch_orchestrator import BatchOrchestrator

class YourTaskBatchOrchestrator(BatchOrchestrator):
    def _process_batch_response(self, response, job_metadata):
        # Load original issues using job_metadata info
        # Validate response against those issues
        # Return list of dicts ready for CSV saving
        pass
```

### 7. Create CLI (`cli.py`)

Wire it all together. Use `argparse` to accept flags like `--subjects`, `--batch-size`, etc.

*   Instantiate `LLMService`.
*   Instantiate `StateManager` (with a unique state file path).
*   Instantiate your `Runner`.
*   Call `runner.run()`.

For batch commands, register subcommands that use your `BatchOrchestrator`.

## Implementation Checklist

Use this checklist to ensure your module is complete.

- [ ] **Configuration**
    - [ ] Created `config.py` subclassing `ReviewConfiguration`.
    - [ ] Defined `output_csv_columns` (must include `issue_id`).
    - [ ] Implemented `get_output_path` logic.

- [ ] **Prompts**
    - [ ] Created `system_xxx.md` and `user_xxx.md` in `src/prompt/templates/`.
    - [ ] Implemented `prompt_factory.py` to render them with batch context.

- [ ] **Core Logic (Runner)**
    - [ ] Subclassed `ReviewRunner`.
    - [ ] Implemented `validate_response` to parse LLM JSON.
    - [ ] **Crucial**: Ensure validation merges original issue data (filename, context) if the LLM doesn't return it.

- [ ] **Batch Support**
    - [ ] Implemented `BatchOrchestrator` subclass (or equivalent logic).
    - [ ] Implemented `_process_batch_response` for async result handling.
    - [ ] Added batch CLI commands (`batch-create`, `batch-fetch`, etc.).

- [ ] **CLI & Entry Point**
    - [ ] Created `cli.py` with `main()`.
    - [ ] Added standard flags: `--subjects`, `--documents`, `--force`, `--dry-run`.
    - [ ] Added environment variable support for defaults (e.g., `LLM_YOURTASK_BATCH_SIZE`).

- [ ] **Persistence**
    - [ ] (Optional) Created `persistence.py` wrappers if custom saving logic is needed.
    - [ ] Verified CSV output format matches requirements.

- [ ] **Logging & State**
    - [ ] Defined a unique state file (e.g., `data/llm_yourtask_state.json`).
    - [ ] Configured raw response logging (useful for debugging).

## Key Concepts

### The `LanguageIssue` Object
The core unit of work. The LLM usually enriches this object. Ensure your validation logic preserves original fields (like `issue_id`, `filename`, `page_number`) when saving results.

### State Management
The `StateManager` uses a JSON file to track completed batches. Always pass the correct `state_file` path in your CLI.

### Batch vs. Sync
*   **Sync**: `Runner.run()` calls `llm_service.generate()` directly. Good for small runs or debugging.
*   **Batch**: `BatchOrchestrator` creates jobs on the provider side. Requires `fetch_batch_results` to retrieve and process later.
