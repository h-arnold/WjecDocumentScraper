# LLM Review Module Refactoring - Detailed Action Plan

## Overview

This document provides step-by-step implementation guidance for refactoring the `llm_review` module. Each phase includes concrete code changes, file operations, and verification steps.

## Prerequisites

1. Feature branch created
2. All existing tests passing
3. Test fixtures prepared
4. Rollback plan documented

## Phase 1: Core Infrastructure (Day 1)

### Objective
Move completely generic modules to `core/` with minimal changes. This phase is low-risk because we're only moving files and updating imports.

### Step 1.1: Create Directory Structure

```bash
mkdir -p src/llm_review/core
touch src/llm_review/core/__init__.py
```

### Step 1.2: Move document_loader.py

**Source:** `src/llm_review/llm_categoriser/data_loader.py`
**Destination:** `src/llm_review/core/document_loader.py`

**Changes needed:**
1. Copy file to new location
2. Update module docstring to indicate it's generic
3. No functional changes

**Update imports in:**
- `llm_categoriser/runner.py`
- `llm_categoriser/cli.py`
- `llm_categoriser/batch_orchestrator.py`

**Old import:**
```python
from .data_loader import load_issues
```

**New import:**
```python
from ..core.document_loader import load_issues
```

### Step 1.3: Move batcher.py

**Source:** `src/llm_review/llm_categoriser/batcher.py`
**Destination:** `src/llm_review/core/batcher.py`

**Changes needed:**
1. Copy file to new location
2. Update module docstring
3. No functional changes

**Update imports in:**
- `llm_categoriser/runner.py`
- `llm_categoriser/cli.py`
- `llm_categoriser/batch_orchestrator.py`

**Old import:**
```python
from .batcher import Batch, iter_batches
```

**New import:**
```python
from ..core.batcher import Batch, iter_batches
```

### Step 1.4: Move state_manager.py

**Source:** `src/llm_review/llm_categoriser/state.py`
**Destination:** `src/llm_review/core/state_manager.py`

**Changes needed:**
1. Copy file to new location
2. Rename class if needed (optional: keep `CategoriserState` or rename to `StateManager`)
3. Update module docstring

**Update imports in:**
- `llm_categoriser/runner.py`
- `llm_categoriser/cli.py`
- `llm_categoriser/batch_cli.py`
- `llm_categoriser/batch_orchestrator.py`

**Old import:**
```python
from .state import CategoriserState
```

**New import:**
```python
from ..core.state_manager import CategoriserState
# Or if renamed:
from ..core.state_manager import StateManager as CategoriserState
```

### Step 1.5: Update core/__init__.py

```python
"""Generic core components for LLM review passes.

This module provides reusable infrastructure for implementing multiple
review passes (categorisation, fact-checking, style validation, etc.).
"""

from .document_loader import load_issues
from .batcher import Batch, iter_batches
from .state_manager import CategoriserState as StateManager

__all__ = [
    "load_issues",
    "Batch",
    "iter_batches",
    "StateManager",
]
```

### Step 1.6: Remove old files

After verifying tests pass:
```bash
git rm src/llm_review/llm_categoriser/data_loader.py
git rm src/llm_review/llm_categoriser/batcher.py
git rm src/llm_review/llm_categoriser/state.py
```

### Step 1.7: Verification

```bash
# Run tests
export PATH="$HOME/.local/bin:$PATH"
cd /home/runner/work/WjecDocumentScraper/WjecDocumentScraper
uv run pytest tests/llm_categoriser/ -v

# Check imports
grep -r "from .data_loader" src/llm_review/llm_categoriser/
grep -r "from .batcher" src/llm_review/llm_categoriser/
grep -r "from .state" src/llm_review/llm_categoriser/

# Should return no results
```

### Phase 1 Deliverables

- [x] `core/` directory created
- [x] `core/__init__.py` with exports
- [x] `core/document_loader.py` (from data_loader.py)
- [x] `core/batcher.py` (moved)
- [x] `core/state_manager.py` (from state.py)
- [x] All imports updated
- [x] All tests passing
- [x] Old files removed

---

## Phase 2: Configurable Persistence (Days 2-3)

### Objective
Make persistence configurable so different review passes can specify their own output paths and CSV columns.

### Step 2.1: Create base configuration

**File:** `src/llm_review/core/config.py`

```python
"""Configuration base classes for review passes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from src.models import DocumentKey


@dataclass
class ReviewConfiguration(ABC):
    """Base configuration for any review pass.
    
    Each review pass should subclass this and provide:
    - Output path structure
    - CSV column definitions
    - Any pass-specific settings
    """
    
    # Input
    input_csv_path: Path
    
    # Batch settings
    batch_size: int = 10
    max_retries: int = 2
    
    # State management
    state_file: Path = Path("data/review_state.json")
    
    # Filtering
    subjects: set[str] | None = None
    documents: set[str] | None = None
    
    # LLM settings
    llm_provider: str | None = None
    fail_on_quota: bool = True
    
    # Logging
    log_raw_responses: bool = False
    log_response_dir: Path = Path("data/review_responses")
    
    # Force reprocessing
    force: bool = False
    
    @abstractmethod
    def get_output_path(self, key: DocumentKey) -> Path:
        """Get output CSV path for a specific document.
        
        Args:
            key: DocumentKey identifying the document
            
        Returns:
            Path where the CSV results should be saved
        """
        pass
    
    @abstractmethod
    def get_csv_columns(self) -> list[str]:
        """Get CSV column names for this review pass.
        
        Returns:
            List of column names for the output CSV
        """
        pass
    
    @abstractmethod
    def get_error_output_dir(self) -> Path:
        """Get directory for error logs.
        
        Returns:
            Path to directory where error logs should be saved
        """
        pass
```

### Step 2.2: Create generic persistence

**File:** `src/llm_review/core/persistence.py`

```python
"""Generic persistence manager with configurable paths and columns."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable
from datetime import datetime, timezone

from src.models import DocumentKey, LanguageIssue

from .config import ReviewConfiguration


class PersistenceManager:
    """Manages persistence of review results with configurable output."""
    
    def __init__(self, config: ReviewConfiguration):
        """Initialize with a review configuration.
        
        Args:
            config: Configuration specifying output paths and columns
        """
        self.config = config
    
    def save_batch_results(
        self,
        key: DocumentKey,
        batch_results: list[dict[str, Any]],
        *,
        merge: bool = True,
    ) -> Path:
        """Save batch results to a CSV file.
        
        Args:
            key: DocumentKey identifying the document
            batch_results: List of issue dictionaries (must include issue_id)
            merge: If True and file exists, merge with existing rows
            
        Returns:
            Path to the saved file
        """
        output_file = self.config.get_output_path(key)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        columns = self.config.get_csv_columns()
        
        existing_rows: dict[int, dict[str, str]] = {}
        if merge and output_file.exists():
            existing_rows = self._read_existing_rows(output_file, columns)
        
        # Build new rows keyed by issue_id
        new_rows: dict[int, dict[str, str]] = {}
        for issue in batch_results:
            try:
                iid, row = self._normalise_issue_row(issue, columns)
            except ValueError as exc:
                print(f"    Warning: Skipping issue without valid issue_id: {exc}")
                continue
            new_rows[iid] = row
        
        if not new_rows and not existing_rows:
            return output_file
        
        merged_rows = existing_rows | new_rows
        
        # Write atomically
        temp_file = output_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                for issue_id in sorted(merged_rows):
                    writer.writerow(merged_rows[issue_id])
            
            temp_file.replace(output_file)
        
        except OSError as e:
            print(f"Error writing to {output_file}: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise
        
        return output_file
    
    def clear_document_results(self, key: DocumentKey) -> None:
        """Delete results file for a document.
        
        Args:
            key: DocumentKey identifying the document
        """
        output_file = self.config.get_output_path(key)
        
        if output_file.exists():
            try:
                output_file.unlink()
            except OSError as e:
                print(f"Warning: Could not delete {output_file}: {e}")
    
    def save_failed_issues(
        self,
        key: DocumentKey,
        batch_index: int,
        failed_issues: Iterable[LanguageIssue],
        *,
        error_messages: dict | None = None,
    ) -> Path:
        """Save details about failed validation attempts to a JSON file.
        
        Args:
            key: DocumentKey identifying the document
            batch_index: Integer index of the batch
            failed_issues: Iterable of LanguageIssue objects
            error_messages: Optional mapping of issue ids to error messages
            
        Returns:
            Path to the saved file
        """
        report_dir = self.config.get_error_output_dir() / key.subject
        report_dir.mkdir(parents=True, exist_ok=True)
        
        safe_filename = key.filename.replace("/", "-")
        output_file = report_dir / f"{safe_filename}.batch-{batch_index}.errors.json"
        
        current_time = datetime.now(timezone.utc)
        payload = {
            "timestamp": current_time.isoformat().replace("+00:00", "Z"),
            "subject": key.subject,
            "filename": key.filename,
            "batch_index": batch_index,
            "issues": [issue.model_dump() for issue in failed_issues],
        }
        
        temp_file = output_file.with_suffix(".tmp")
        if error_messages:
            serialisable_errors = {str(k): v for k, v in error_messages.items()}
            payload["errors"] = serialisable_errors
        
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            
            temp_file.replace(output_file)
        except OSError as e:
            print(f"Error writing failed issues to {output_file}: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise
        
        return output_file
    
    def _read_existing_rows(self, path: Path, columns: list[str]) -> dict[int, dict[str, str]]:
        """Read an existing CSV file into a mapping keyed by issue_id."""
        rows: dict[int, dict[str, str]] = {}
        try:
            with open(path, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    raw_id = row.get("issue_id")
                    if raw_id is None:
                        continue
                    try:
                        iid = int(raw_id)
                    except ValueError:
                        continue
                    # Normalise the row to ensure all columns are present
                    normalised_row = {col: row.get(col, "") for col in columns}
                    rows[iid] = normalised_row
        except OSError as e:
            print(f"Warning: Could not read existing CSV {path}: {e}")
        return rows
    
    def _normalise_issue_row(
        self,
        issue: dict[str, Any],
        columns: list[str],
    ) -> tuple[int, dict[str, str]]:
        """Normalise a validated issue dict into a CSV row."""
        raw_id = issue.get("issue_id")
        if raw_id is None:
            raise ValueError("missing issue_id")
        try:
            issue_id = int(raw_id)
        except Exception as exc:
            raise ValueError(f"invalid issue_id {raw_id!r}") from exc
        
        def _clean(value: Any) -> str:
            if value is None:
                return ""
            return str(value)
        
        # Build row with only the columns we care about
        row = {}
        for col in columns:
            # Map column names to issue dict keys
            # This is flexible and can be customized per review pass
            value = issue.get(col)
            
            # Special handling for certain fields
            if col == "issue" and value is None:
                value = issue.get("context") or issue.get("context_from_tool")
            elif col == "highlighted_context" and value is None:
                value = issue.get("context_from_tool")
            
            row[col] = _clean(value)
        
        return issue_id, row
```

### Step 2.3: Create categoriser configuration

**File:** `src/llm_review/llm_categoriser/config.py`

```python
"""Configuration for the LLM categoriser review pass."""

from __future__ import annotations

from pathlib import Path

from src.models import DocumentKey
from ..core.config import ReviewConfiguration


class CategoriserConfiguration(ReviewConfiguration):
    """Configuration for the categoriser review pass."""
    
    # Override defaults
    state_file: Path = Path("data/llm_categoriser_state.json")
    log_response_dir: Path = Path("data/llm_categoriser_responses")
    
    def get_output_path(self, key: DocumentKey) -> Path:
        """Get output path for categoriser results.
        
        Format: Documents/<subject>/document_reports/<filename>.csv
        """
        output_base = Path("Documents")
        report_dir = output_base / key.subject / "document_reports"
        return report_dir / key.filename.replace(".md", ".csv")
    
    def get_csv_columns(self) -> list[str]:
        """Get CSV columns for categoriser output."""
        return [
            "issue_id",
            "page_number",
            "issue",
            "highlighted_context",
            "pass_code",
            "error_category",
            "confidence_score",
            "reasoning",
        ]
    
    def get_error_output_dir(self) -> Path:
        """Get error output directory for categoriser."""
        return Path("data/llm_categoriser_errors")
```

### Step 2.4: Update core/__init__.py

```python
"""Generic core components for LLM review passes."""

from .document_loader import load_issues
from .batcher import Batch, iter_batches
from .state_manager import CategoriserState as StateManager
from .config import ReviewConfiguration
from .persistence import PersistenceManager

__all__ = [
    "load_issues",
    "Batch",
    "iter_batches",
    "StateManager",
    "ReviewConfiguration",
    "PersistenceManager",
]
```

### Step 2.5: Update llm_categoriser to use new persistence

Update `llm_categoriser/runner.py`:

```python
# Add at top
from .config import CategoriserConfiguration
from ..core.persistence import PersistenceManager

# In __init__:
def __init__(
    self,
    llm_service: LLMService,
    state: CategoriserState,
    config: CategoriserConfiguration,
    ...
):
    self.config = config
    self.persistence = PersistenceManager(config)
    ...

# Replace save_batch_results calls:
# OLD:
from .persistence import save_batch_results
output_path = save_batch_results(key, list(all_results.values()), merge=True)

# NEW:
output_path = self.persistence.save_batch_results(
    key, 
    list(all_results.values()), 
    merge=True
)
```

### Step 2.6: Deprecate old persistence.py

Add deprecation notice to `llm_categoriser/persistence.py`:

```python
"""DEPRECATED: Use core.persistence.PersistenceManager instead.

This module is kept for backward compatibility but will be removed
in a future version. New code should use:

    from ..core.persistence import PersistenceManager
    from .config import CategoriserConfiguration
    
    config = CategoriserConfiguration(...)
    persistence = PersistenceManager(config)
"""

import warnings
warnings.warn(
    "llm_categoriser.persistence is deprecated, use core.persistence.PersistenceManager",
    DeprecationWarning,
    stacklevel=2
)

# Keep old functions wrapping new implementation
...
```

### Phase 2 Deliverables

- [x] `core/config.py` with `ReviewConfiguration`
- [x] `core/persistence.py` with `PersistenceManager`
- [x] `llm_categoriser/config.py` with `CategoriserConfiguration`
- [x] `llm_categoriser/runner.py` updated to use new persistence
- [x] Old `persistence.py` deprecated
- [x] All tests passing
- [x] Integration tests added

---

## Phase 3: Abstract Runner (Days 4-6)

### Objective
Extract generic orchestration logic into an abstract base class that can be extended for different review passes.

### Step 3.1: Create abstract review runner

**File:** `src/llm_review/core/review_runner.py`

```python
"""Abstract base class for review pass runners.

This module provides the generic orchestration logic that all review
passes share: loading issues, batching, calling LLM, validation, retries,
and persistence.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Sequence

from src.models import LanguageIssue, DocumentKey
from src.llm.service import LLMService
from src.llm.provider import LLMQuotaError

from .config import ReviewConfiguration
from .document_loader import load_issues
from .batcher import Batch, iter_batches
from .state_manager import StateManager
from .persistence import PersistenceManager


class ReviewRunner(ABC):
    """Abstract base class for all review pass runners.
    
    Subclasses must implement:
    - _build_prompts: Generate prompts for LLM
    - _validate_response: Validate and parse LLM responses
    
    The base class handles:
    - Loading and filtering issues
    - Batching issues per document
    - Calling LLM with retry logic
    - Progress tracking via state
    - Result persistence
    - Error handling and logging
    """
    
    def __init__(
        self,
        config: ReviewConfiguration,
        llm_service: LLMService,
        state: StateManager,
    ):
        """Initialize the runner.
        
        Args:
            config: Configuration for this review pass
            llm_service: LLM service for making API calls
            state: State manager for tracking progress
        """
        self.config = config
        self.llm_service = llm_service
        self.state = state
        self.persistence = PersistenceManager(config)
    
    def run(
        self,
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Run the review workflow.
        
        Args:
            dry_run: If True, only validate data loading (don't call LLM)
            
        Returns:
            Summary statistics dictionary
        """
        print(f"Loading issues from {self.config.input_csv_path}...")
        grouped_issues = load_issues(
            self.config.input_csv_path,
            subjects=self.config.subjects,
            documents=self.config.documents,
        )
        
        if not grouped_issues:
            print("No issues found matching the filters")
            return {"total_documents": 0, "total_batches": 0, "total_issues": 0}
        
        print(f"Loaded {len(grouped_issues)} document(s) with issues")
        
        total_batches = 0
        total_issues = 0
        processed_batches = 0
        skipped_batches = 0
        
        for key, issues in grouped_issues.items():
            print(f"\nProcessing {key} ({len(issues)} issues)...")
            total_issues += len(issues)
            
            # Get Markdown path
            markdown_path = Path("Documents") / key.subject / "markdown" / key.filename
            
            # Clear state if force mode
            if self.config.force:
                self.state.clear_document(key)
                self.persistence.clear_document_results(key)
            
            # Process batches for this document
            for batch in iter_batches(
                issues,
                self.config.batch_size,
                markdown_path,
                subject=key.subject,
                filename=key.filename,
            ):
                total_batches += 1
                
                # Check if already completed
                if not self.config.force and self.state.is_batch_completed(key, batch.index):
                    print(f"  Batch {batch.index}: Already completed (skipping)")
                    skipped_batches += 1
                    continue
                
                if dry_run:
                    print(f"  Batch {batch.index}: Dry run (not calling LLM)")
                    continue
                
                # Process the batch
                success = self._process_batch(key, batch)
                if success:
                    processed_batches += 1
                    self.state.mark_batch_completed(key, batch.index, len(issues))
        
        print(f"\n{'=' * 60}")
        print(f"Summary:")
        print(f"  Total documents: {len(grouped_issues)}")
        print(f"  Total batches: {total_batches}")
        print(f"  Processed: {processed_batches}")
        print(f"  Skipped (already done): {skipped_batches}")
        print(f"  Total issues: {total_issues}")
        print(f"{'=' * 60}")
        
        return {
            "total_documents": len(grouped_issues),
            "total_batches": total_batches,
            "processed_batches": processed_batches,
            "skipped_batches": skipped_batches,
            "total_issues": total_issues,
        }
    
    @abstractmethod
    def _build_prompts(self, batch: Batch) -> list[str]:
        """Build prompts for this review pass.
        
        Args:
            batch: A Batch object containing issues and context
            
        Returns:
            List of prompts (typically [system_prompt, user_prompt])
        """
        pass
    
    @abstractmethod
    def _validate_response(
        self,
        response: Any,
        issues: list[LanguageIssue],
    ) -> tuple[list[dict[str, Any]], set[int], dict[object, list[str]]]:
        """Validate LLM response for this review pass.
        
        Args:
            response: The LLM response to validate
            issues: The issues that were sent to the LLM
            
        Returns:
            Tuple of (validated_results, failed_issue_ids, error_messages)
        """
        pass
    
    def _process_batch(self, key: DocumentKey, batch: Batch) -> bool:
        """Process a single batch with retries.
        
        This is the generic workflow that all review passes share.
        Extension points are the abstract methods.
        
        Returns:
            True if batch was successfully processed and persisted
        """
        print(f"  Batch {batch.index}: Processing {len(batch.issues)} issue(s)...")
        
        remaining_issues = batch.issues.copy()
        all_results: dict[int, dict[str, Any]] = {}
        agg_failed_errors: dict[object, list[str]] = {}
        
        for attempt in range(self.config.max_retries + 1):
            if not remaining_issues:
                break
            
            if attempt > 0:
                print(f"    Retry {attempt}/{self.config.max_retries} for {len(remaining_issues)} issue(s)")
            
            # Build prompts for remaining issues
            retry_batch = Batch(
                subject=batch.subject,
                filename=batch.filename,
                index=batch.index,
                issues=remaining_issues,
                page_context=batch.page_context,
                markdown_table=self._build_table_for_issues(remaining_issues),
            )
            
            prompts = self._build_prompts(retry_batch)
            
            # Extract user prompts (skip system prompt if present)
            if len(prompts) > 1:
                user_prompts = prompts[1:]
            else:
                user_prompts = prompts
            
            # Call LLM
            response = self._call_llm(user_prompts, key, batch.index, attempt)
            if response is None:
                return False
            
            self._maybe_log_response(key, batch.index, attempt, response, remaining_issues)
            
            # Validate and collect results
            validated, failed, errors = self._validate_response(response, remaining_issues)
            
            # Add validated results
            for issue_dict in validated:
                issue_id = issue_dict.get("issue_id")
                if issue_id is None:
                    continue
                try:
                    iid_int = int(issue_id)
                except Exception:
                    continue
                all_results[iid_int] = issue_dict
            
            # Update remaining issues for next retry
            remaining_issues = [issue for issue in remaining_issues if issue.issue_id in failed]
            
            # Aggregate errors
            for k, msgs in errors.items():
                if msgs:
                    agg_failed_errors.setdefault(k, []).extend(msgs)
            
            if not remaining_issues:
                print(f"    All issues validated successfully")
                break
        
        # Log failures
        if remaining_issues:
            print(f"    Warning: {len(remaining_issues)} issue(s) could not be validated")
            try:
                err_path = self.persistence.save_failed_issues(
                    key, batch.index, remaining_issues, error_messages=agg_failed_errors
                )
                total_errors = sum(len(msgs) for msgs in agg_failed_errors.values())
                print(f"      Saved failed-issues details to {err_path} ({total_errors} messages)")
            except Exception as e:
                print(f"      Could not save failed issues: {e}")
        
        # Persist results
        if all_results:
            try:
                output_path = self.persistence.save_batch_results(
                    key, list(all_results.values()), merge=True
                )
                print(f"    Saved results to {output_path}")
                return True
            except Exception as e:
                print(f"    Error saving results: {e}")
                return False
        else:
            print(f"    No valid results to save")
            return False
    
    def _call_llm(
        self,
        user_prompts: Sequence[str],
        key: DocumentKey,
        batch_index: int,
        attempt: int,
    ) -> Any | None:
        """Call the LLM and handle provider-level exceptions."""
        try:
            return self.llm_service.generate(user_prompts, filter_json=True)
        except LLMQuotaError as exc:
            print(f"    Provider quota exhausted: {exc}")
            if self.config.fail_on_quota:
                raise
            return None
        except Exception as e:
            if self._is_503_error(e):
                print(f"    Provider service unavailable (503): {e}")
                raise
            print(f"    Error calling LLM: {e}")
            return None
    
    def _maybe_log_response(
        self,
        key: DocumentKey,
        batch_index: int,
        attempt: int,
        response: Any,
        issues: list[LanguageIssue],
    ) -> None:
        """Log raw LLM response if configured."""
        if not self.config.log_raw_responses:
            return
        try:
            self._log_raw_response(key, batch_index, attempt, response, issues)
        except Exception as exc:
            print(f"    Warning: Could not log raw response: {exc}")
    
    def _log_raw_response(
        self,
        key: DocumentKey,
        batch_index: int,
        attempt: int,
        response: Any,
        issues: list[LanguageIssue],
    ) -> None:
        """Log raw response to JSON file."""
        import json
        from datetime import datetime, timezone
        
        subject_dir = self.config.log_response_dir / key.subject
        subject_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = key.filename.replace("/", "-")
        current_time = datetime.now(timezone.utc)
        timestamp = current_time.strftime("%Y%m%dT%H%M%S%fZ")
        output_file = subject_dir / f"{safe_filename}.batch-{batch_index}.attempt-{attempt}.{timestamp}.json"
        
        payload = {
            "timestamp": current_time.isoformat().replace("+00:00", "Z"),
            "subject": key.subject,
            "filename": key.filename,
            "batch_index": batch_index,
            "attempt": attempt,
            "issue_ids": [issue.issue_id for issue in issues],
            "response": response,
        }
        
        with open(output_file, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, default=str)
    
    def _is_503_error(self, exc: Exception) -> bool:
        """Return True if exception indicates HTTP 503."""
        try:
            if getattr(exc, "status_code", None) == 503:
                return True
            resp = getattr(exc, "response", None)
            if resp is not None and getattr(resp, "status_code", None) == 503:
                return True
            if resp is not None and getattr(resp, "status", None) == 503:
                return True
            if getattr(exc, "http_status", None) == 503:
                return True
            if "503" in str(exc):
                return True
        except Exception:
            return False
        return False
    
    def _build_table_for_issues(self, issues: list[LanguageIssue]) -> str:
        """Build a Markdown table for a subset of issues."""
        from src.language_check.report_utils import build_issue_batch_table
        return build_issue_batch_table(issues)
```

### Step 3.2: Refactor CategoriserRunner to extend ReviewRunner

Update `llm_categoriser/runner.py`:

```python
"""Categoriser-specific runner implementation."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from src.models import LanguageIssue, PassCode

from ..core.review_runner import ReviewRunner
from ..core.batcher import Batch
from .prompt_factory import build_prompts
from .config import CategoriserConfiguration


class CategoriserRunner(ReviewRunner):
    """Runner for LLM categorisation of language issues.
    
    Extends ReviewRunner with categoriser-specific:
    - Prompt generation
    - Response validation (merging with original detection data)
    """
    
    def __init__(
        self,
        config: CategoriserConfiguration,
        llm_service,
        state,
    ):
        """Initialize categoriser runner.
        
        Args:
            config: Categoriser configuration
            llm_service: LLM service
            state: State manager
        """
        super().__init__(config, llm_service, state)
        self.config: CategoriserConfiguration = config  # Type hint
    
    def _build_prompts(self, batch: Batch) -> list[str]:
        """Build categorisation prompts."""
        return build_prompts(batch)
    
    def _validate_response(
        self,
        response: Any,
        issues: list[LanguageIssue],
    ) -> tuple[list[dict[str, Any]], set[int], dict[object, list[str]]]:
        """Validate LLM categorisation response.
        
        Merges LLM categorisation with original detection data.
        """
        validated_results: list[dict[str, Any]] = []
        failed_issue_ids: set[int] = set(issue.issue_id for issue in issues)
        error_messages: dict[object, list[str]] = {
            issue.issue_id: [] for issue in issues
        }
        error_messages.setdefault("batch_errors", [])
        
        # Validate top-level structure
        if not isinstance(response, list):
            msg = "Expected top-level JSON array of objects"
            print(f"    Error: {msg}")
            error_messages["batch_errors"].append(msg)
            return validated_results, failed_issue_ids, error_messages
        
        if not response:
            msg = "Response is empty; no issues to validate"
            print(f"    Warning: {msg}")
            error_messages["batch_errors"].append(msg)
            return validated_results, failed_issue_ids, error_messages
        
        # Build issue map
        filename = issues[0].filename if issues else ""
        issue_map = {issue.issue_id: issue for issue in issues}
        
        # Process each entry
        for issue_dict in response:
            if not isinstance(issue_dict, dict):
                warn = "Entry in response array is not a JSON object"
                print(f"    Warning: {warn}")
                error_messages["batch_errors"].append(warn)
                continue
            
            try:
                iid = issue_dict.get("issue_id")
                
                if iid is not None and iid in issue_map:
                    # Merge LLM categorisation with original detection data
                    orig = issue_map[iid]
                    merged = {
                        "filename": orig.filename,
                        "rule_id": orig.rule_id,
                        "message": orig.message,
                        "issue_type": orig.issue_type,
                        "replacements": orig.replacements,
                        "context": orig.context,
                        "highlighted_context": orig.highlighted_context,
                        "issue": orig.issue,
                        "page_number": orig.page_number,
                        "issue_id": orig.issue_id,
                        "pass_code": PassCode.LTC,
                        # LLM fields
                        "error_category": issue_dict.get("error_category"),
                        "confidence_score": issue_dict.get("confidence_score"),
                        "reasoning": issue_dict.get("reasoning"),
                    }
                    validated = LanguageIssue(**merged)
                else:
                    # Fallback
                    validated = LanguageIssue.from_llm_response(issue_dict, filename=filename)
                
                validated_results.append(validated.model_dump())
                
                if validated.issue_id >= 0:
                    failed_issue_ids.discard(validated.issue_id)
            
            except ValidationError as e:
                iid = issue_dict.get("issue_id")
                if iid is not None:
                    error_messages.setdefault(iid, []).append(str(e))
                else:
                    error_messages["batch_errors"].append(str(e))
            except Exception as e:
                iid = issue_dict.get("issue_id")
                if iid is not None:
                    error_messages.setdefault(iid, []).append(str(e))
                else:
                    error_messages["batch_errors"].append(str(e))
        
        if not validated_results:
            msg = "Response contained no valid issue objects"
            error_messages["batch_errors"].append(msg)
        
        return validated_results, failed_issue_ids, error_messages
```

### Step 3.3: Update CLI to use new runner

Update `llm_categoriser/cli.py`:

```python
# Update imports
from .config import CategoriserConfiguration
from .runner import CategoriserRunner

# In main():
def main(args: list[str] | None = None) -> int:
    ...
    
    # Create configuration
    config = CategoriserConfiguration(
        input_csv_path=parsed_args.from_report,
        batch_size=parsed_args.batch_size,
        max_retries=parsed_args.max_retries,
        state_file=parsed_args.state_file,
        subjects=subjects_set,
        documents=documents_set,
        force=parsed_args.force,
        llm_provider=parsed_args.provider,
        fail_on_quota=fail_on_quota,
        log_raw_responses=log_responses_flag,
        log_response_dir=log_responses_dir,
    )
    
    # Create state manager
    from ..core.state_manager import StateManager
    state = StateManager(config.state_file)
    
    # Create runner
    runner = CategoriserRunner(
        config=config,
        llm_service=llm_service,
        state=state,
    )
    
    # Run
    runner.run(dry_run=parsed_args.dry_run)
    
    return 0
```

### Phase 3 Deliverables

- [x] `core/review_runner.py` with abstract base class
- [x] `llm_categoriser/runner.py` refactored to extend abstract runner
- [x] `llm_categoriser/cli.py` updated to use new runner
- [x] All categoriser-specific logic isolated
- [x] All tests passing
- [x] Integration tests verify workflow

---

## Phase 4-6: Additional Phases

(Abbreviated for space - follow similar patterns)

### Phase 4: CLI Framework
- Create `core/base_cli.py`
- Extract common argument patterns
- Refactor categoriser CLI to use base

### Phase 5: Batch Orchestration
- Create `core/batch_orchestrator.py`
- Extract generic batch job management
- Parametrize validation logic

### Phase 6: Documentation
- Write `core/README.md`
- Create example review pass
- Update all documentation

---

## Testing Strategy

### Unit Tests

Each core module should have comprehensive unit tests:

```python
# tests/core/test_document_loader.py
def test_load_issues_groups_by_document():
    # Test grouping logic
    pass

def test_load_issues_assigns_issue_ids():
    # Test ID assignment
    pass

# tests/core/test_persistence.py
def test_save_batch_results_creates_file():
    # Test file creation
    pass

def test_save_batch_results_merges_existing():
    # Test merge logic
    pass

# tests/core/test_review_runner.py
def test_runner_orchestrates_workflow():
    # Test workflow with mocks
    pass

def test_runner_handles_retries():
    # Test retry logic
    pass
```

### Integration Tests

Test complete workflows:

```python
# tests/llm_categoriser/test_integration.py
def test_categoriser_end_to_end(tmp_path):
    # Set up test data
    # Run categoriser
    # Verify output
    pass

def test_categoriser_resumes_on_interrupt(tmp_path):
    # Test state management
    pass
```

### Regression Tests

Ensure no breaking changes:

```python
# tests/llm_categoriser/test_regression.py
def test_output_format_unchanged():
    # Compare old vs new output
    pass

def test_cli_commands_work():
    # Test all CLI commands
    pass
```

---

## Rollback Plan

If issues arise during migration:

1. **Immediate Rollback:**
   ```bash
   git revert <commit-hash>
   git push origin <branch>
   ```

2. **Partial Rollback:**
   - Keep completed phases
   - Rollback problematic phase
   - Fix issues
   - Re-apply

3. **Keep Both:**
   - Add feature flag
   - Run old and new in parallel
   - Gradually migrate

---

## Success Criteria

- [ ] All existing tests pass
- [ ] New unit tests added for core modules
- [ ] Integration tests verify workflows
- [ ] Example review pass implemented
- [ ] Documentation complete
- [ ] Code review approved
- [ ] Performance acceptable

---

## Timeline

- Phase 1: 1 day
- Phase 2: 2 days
- Phase 3: 3 days
- Phase 4: 1 day
- Phase 5: 2 days
- Phase 6: 1 day

**Total: 10 days** (includes testing and reviews)

---

## Notes

- This is a **planning document only** - no code changes yet
- Each phase should be a separate PR for easier review
- Run tests after each phase
- Document any deviations from plan
- Keep stakeholders informed of progress
