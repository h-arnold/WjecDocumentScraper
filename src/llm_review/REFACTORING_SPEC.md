# LLM Review Module Refactoring Specification

## Executive Summary

This document provides a comprehensive analysis and action plan for decoupling generic document processing functionality from the categoriser-specific implementation in the `llm_review` module. The goal is to create a reusable framework that can support multiple review passes (categoriser, fact-checking, style validation, etc.) while maintaining SOLID principles and DRY code.

## Problem Statement

Currently, the `llm_categoriser` module contains tightly coupled generic and specific functionality:

**Generic Functionality (Should be moved to `llm_review`):**
1. Creating job batches from a single CSV file
2. Processing and validation of LLM JSON output into LanguageIssue objects
3. Output of document reports into CSV files
4. Batch job orchestration (synchronous via chat endpoints or asynchronous via batch endpoints)
5. State management for resume capability
6. CSV loading and document grouping
7. Generic retry logic and error handling

**Specific Functionality (Should remain in `llm_categoriser`):**
1. Prompt generation logic for categorisation
2. Source CSV report location (`Documents/language-check-report.csv`)
3. Destination folder for categorised reports (`Documents/<subject>/document_reports/`)

## Current Architecture Analysis

### Module Structure

```
src/llm_review/
├── llm_categoriser/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                    # CLI entry point (mixed concerns)
│   ├── runner.py                 # Orchestration (mixed concerns)
│   ├── batcher.py                # Generic batching logic
│   ├── data_loader.py            # Generic CSV loading
│   ├── persistence.py            # Generic persistence
│   ├── state.py                  # Generic state management
│   ├── prompt_factory.py         # Specific prompt generation
│   ├── batch_cli.py              # Batch commands (mixed concerns)
│   └── batch_orchestrator.py    # Batch API orchestration (mixed concerns)
└── possible_review_flow.md
```

### Detailed Component Analysis

#### 1. **data_loader.py** (Generic - 172 lines)
**Current Responsibilities:**
- Load CSV report into LanguageIssue objects
- Group issues by DocumentKey
- Validate Markdown file existence
- Apply subject/document filters
- Assign issue IDs

**Generic Parts (100%):**
- All functionality is reusable for any review pass
- Only assumes CSV structure with specific columns

**Categoriser-Specific Parts (0%):**
- None

**Recommendation:** Move to `llm_review/core/document_loader.py`

---

#### 2. **batcher.py** (Generic - 115 lines)
**Current Responsibilities:**
- Chunk issues into batches by size
- Extract page context from Markdown
- Build simplified issue tables
- Yield Batch objects

**Generic Parts (100%):**
- All batching logic is reusable
- Page context extraction is generic

**Categoriser-Specific Parts (0%):**
- None (table format is controlled by external function)

**Recommendation:** Move to `llm_review/core/batcher.py`

---

#### 3. **persistence.py** (Generic - 251 lines)
**Current Responsibilities:**
- Save batch results to CSV files
- Merge results with existing files
- Clear document results
- Save failed issues to JSON
- Atomic file operations

**Generic Parts (90%):**
- CSV writing logic
- Atomic file operations
- Issue deduplication
- Failed issue logging

**Categoriser-Specific Parts (10%):**
- Hard-coded output path structure (`Documents/<subject>/document_reports/`)
- Hard-coded CSV columns for categorisation

**Recommendation:** 
- Create `llm_review/core/persistence.py` with generic base class
- Make output path and CSV columns configurable
- Keep categoriser-specific configuration in `llm_categoriser/config.py`

---

#### 4. **state.py** (Generic - 162 lines)
**Current Responsibilities:**
- Track completed batches per document
- JSON state file management
- Atomic state updates
- State querying methods

**Generic Parts (100%):**
- All state management is reusable
- Only state file path is variable

**Categoriser-Specific Parts (0%):**
- None

**Recommendation:** Move to `llm_review/core/state_manager.py`

---

#### 5. **runner.py** (Mixed - 513 lines)
**Current Responsibilities:**
- Orchestrate workflow (load → batch → prompt → LLM → validate → persist)
- Handle retries
- Validate LLM responses
- Call LLM service
- Log responses
- Manage quota errors

**Generic Parts (70%):**
- Workflow orchestration structure
- Retry logic
- Response validation framework
- LLM service interaction
- Error handling
- Progress reporting

**Categoriser-Specific Parts (30%):**
- Merging LLM response with original detection data
- Specific validation rules for categorisation fields
- Hard-coded response format expectations

**Recommendation:**
- Create `llm_review/core/review_runner.py` with abstract base class
- Extract generic orchestration, retry, and validation patterns
- Keep categoriser-specific merge logic in `llm_categoriser/runner.py`

---

#### 6. **prompt_factory.py** (Specific - 82 lines)
**Current Responsibilities:**
- Build prompts using categorisation templates
- Render template with batch context

**Generic Parts (20%):**
- Template rendering infrastructure (but uses shared utilities)

**Categoriser-Specific Parts (80%):**
- Categorisation-specific templates
- Context preparation for categorisation

**Recommendation:** Keep in `llm_categoriser/` with minor refactoring

---

#### 7. **cli.py** (Mixed - 491 lines)
**Current Responsibilities:**
- Parse command-line arguments
- Configure LLM service
- Create runner and execute
- Handle special modes (dry-run, emit-batch-payload, etc.)

**Generic Parts (60%):**
- Argument parsing patterns
- LLM service setup
- Common CLI options (subjects, documents, batch-size, etc.)
- Special modes infrastructure

**Categoriser-Specific Parts (40%):**
- Default report path
- Categorisation-specific options
- Prompt emission logic

**Recommendation:**
- Create `llm_review/core/base_cli.py` with reusable CLI framework
- Keep categoriser-specific CLI in `llm_categoriser/cli.py`

---

#### 8. **batch_orchestrator.py** (Mixed - 556 lines)
**Current Responsibilities:**
- Create batch jobs via LLM API
- Track batch job metadata
- Fetch and process batch results
- Cancel batch jobs
- List tracked jobs

**Generic Parts (80%):**
- Batch job creation workflow
- Job tracking infrastructure
- Result fetching and validation
- Job management operations

**Categoriser-Specific Parts (20%):**
- Response validation specifics
- Result processing logic

**Recommendation:**
- Create `llm_review/core/batch_orchestrator.py` with abstract base
- Parametrize validation and processing logic

---

#### 9. **batch_cli.py** (Mixed - ~200 lines estimated)
**Current Responsibilities:**
- Add batch subcommands to parser
- Handle batch command execution

**Generic Parts (70%):**
- Subcommand structure
- Common batch operations

**Categoriser-Specific Parts (30%):**
- Specific defaults and paths

**Recommendation:**
- Create reusable batch command framework in core
- Keep categoriser specifics in `llm_categoriser/batch_cli.py`

---

## Proposed Architecture

### New Directory Structure

```
src/llm_review/
├── core/                          # Generic reusable components
│   ├── __init__.py
│   ├── document_loader.py         # Generic CSV loading (from data_loader.py)
│   ├── batcher.py                 # Generic batching (from batcher.py)
│   ├── persistence.py             # Generic persistence with config
│   ├── state_manager.py           # Generic state tracking (from state.py)
│   ├── review_runner.py           # Abstract review orchestrator
│   ├── batch_orchestrator.py     # Generic batch API orchestration
│   ├── base_cli.py                # Reusable CLI framework
│   ├── models.py                  # Shared data models
│   └── config.py                  # Configuration base classes
│
├── llm_categoriser/               # Categoriser-specific implementation
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                     # Categoriser CLI (uses base_cli)
│   ├── runner.py                  # Categoriser runner (extends review_runner)
│   ├── prompt_factory.py          # Categoriser prompts (unchanged)
│   ├── config.py                  # Categoriser configuration
│   ├── batch_cli.py               # Categoriser batch commands
│   └── [existing docs]
│
└── [future review passes]/
    ├── llm_fact_checker/
    ├── llm_style_validator/
    └── ...
```

### Core Abstractions

#### 1. ReviewConfiguration (Base Class)

```python
@dataclass
class ReviewConfiguration:
    """Base configuration for any review pass."""
    
    # Input/Output
    input_csv_path: Path
    output_base_dir: Path
    output_subdir: str  # e.g., "document_reports" or "fact_check_reports"
    
    # Batch settings
    batch_size: int
    max_retries: int
    
    # State management
    state_file: Path
    
    # Filtering
    subjects: set[str] | None
    documents: set[str] | None
    
    # LLM settings
    llm_provider: str | None
    fail_on_quota: bool
    
    # Logging
    log_raw_responses: bool
    log_response_dir: Path
    
    # CSV output columns (configurable per review pass)
    output_csv_columns: list[str]
    
    @abstractmethod
    def get_output_path(self, key: DocumentKey) -> Path:
        """Get output path for a specific document."""
        pass
```

#### 2. ReviewRunner (Abstract Base Class)

```python
class ReviewRunner(ABC):
    """Abstract base class for all review runners."""
    
    def __init__(
        self,
        config: ReviewConfiguration,
        llm_service: LLMService,
        state_manager: StateManager,
    ):
        self.config = config
        self.llm_service = llm_service
        self.state = state_manager
    
    def run(
        self,
        *,
        force: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Generic orchestration workflow."""
        # 1. Load issues
        grouped_issues = self._load_issues()
        
        # 2. Process each document
        for key, issues in grouped_issues.items():
            self._process_document(key, issues, force, dry_run)
        
        return self._generate_summary()
    
    @abstractmethod
    def _build_prompts(self, batch: Batch) -> list[str]:
        """Build prompts for this review pass (pass-specific)."""
        pass
    
    @abstractmethod
    def _validate_response(
        self,
        response: Any,
        issues: list[LanguageIssue],
    ) -> tuple[list[dict], set[int], dict]:
        """Validate LLM response (pass-specific)."""
        pass
    
    def _load_issues(self) -> dict[DocumentKey, list[LanguageIssue]]:
        """Generic issue loading (reuses core.document_loader)."""
        return load_issues(
            self.config.input_csv_path,
            subjects=self.config.subjects,
            documents=self.config.documents,
        )
    
    def _process_document(
        self,
        key: DocumentKey,
        issues: list[LanguageIssue],
        force: bool,
        dry_run: bool,
    ) -> None:
        """Generic document processing workflow."""
        # This contains the retry logic, batch processing, etc.
        # Calls abstract methods at extension points
        pass
```

#### 3. PersistenceManager (Configurable)

```python
class PersistenceManager:
    """Generic persistence with configurable paths and columns."""
    
    def __init__(self, config: ReviewConfiguration):
        self.config = config
    
    def save_batch_results(
        self,
        key: DocumentKey,
        batch_results: list[dict[str, Any]],
        *,
        merge: bool = True,
    ) -> Path:
        """Save results using configured paths and columns."""
        output_file = self.config.get_output_path(key)
        # Generic atomic write logic
        # Uses config.output_csv_columns for header
        pass
```

#### 4. StateManager (Generic)

Already generic, just needs to be moved to core.

#### 5. BaseCLI (Reusable Framework)

```python
class BaseCLI(ABC):
    """Base CLI framework for review passes."""
    
    @abstractmethod
    def get_default_config(self) -> ReviewConfiguration:
        """Get default configuration for this review pass."""
        pass
    
    @abstractmethod
    def add_custom_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add review-pass-specific arguments."""
        pass
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create parser with common and custom arguments."""
        parser = argparse.ArgumentParser(...)
        
        # Add common arguments (subjects, documents, batch-size, etc.)
        self._add_common_arguments(parser)
        
        # Let subclass add custom arguments
        self.add_custom_arguments(parser)
        
        return parser
    
    def main(self, args: list[str] | None = None) -> int:
        """Generic main entry point."""
        parsed_args = self.parse_args(args)
        config = self._build_config(parsed_args)
        runner = self._create_runner(config)
        return runner.run(...)
```

## SOLID Principles Application

### Single Responsibility Principle (SRP)

**Current Issues:**
- `runner.py` handles orchestration, validation, retry logic, LLM calls, and persistence
- `cli.py` handles argument parsing, service setup, and execution

**Solution:**
- Split `ReviewRunner` into focused components:
  - `ReviewOrchestrator`: High-level workflow coordination
  - `ResponseValidator`: Validation logic
  - `RetryManager`: Retry strategy
  - `PersistenceManager`: Result persistence
- Separate CLI argument parsing from execution logic

### Open/Closed Principle (OCP)

**Current Issues:**
- Hard-coded paths and column names make extension difficult
- Adding new review passes requires duplicating code

**Solution:**
- Abstract base classes (`ReviewRunner`, `ReviewConfiguration`)
- Extension points for pass-specific logic
- Configuration objects for paths and formats
- New review passes extend base classes without modifying core

### Liskov Substitution Principle (LSP)

**Current Issues:**
- Not applicable (no inheritance hierarchy exists)

**Solution:**
- Ensure `CategoriserRunner extends ReviewRunner` can be used wherever `ReviewRunner` is expected
- All abstract methods must be implementable consistently

### Interface Segregation Principle (ISP)

**Current Issues:**
- Large interfaces with mixed concerns

**Solution:**
- Split into focused interfaces:
  - `IDocumentLoader`: Load and filter documents
  - `IBatcher`: Create batches from issues
  - `IPromptBuilder`: Build prompts for LLM
  - `IResponseValidator`: Validate LLM responses
  - `IPersistence`: Save results
  - `IStateManager`: Track progress

### Dependency Inversion Principle (DIP)

**Current Issues:**
- High-level runner depends on low-level CSV format details
- Concrete implementations instead of abstractions

**Solution:**
- High-level `ReviewRunner` depends on abstract interfaces
- Concrete implementations injected via configuration
- Example:
  ```python
  runner = CategoriserRunner(
      config=CategoriserConfig(...),
      llm_service=llm_service,  # Abstraction
      state_manager=state_manager,  # Abstraction
  )
  ```

## DRY (Don't Repeat Yourself) Analysis

### Current Violations

1. **CSV loading logic** - Would be duplicated for each review pass
2. **Batching logic** - Would be duplicated
3. **State management** - Would be duplicated
4. **Retry logic** - Would be duplicated
5. **CLI argument patterns** - Would be duplicated
6. **Batch API orchestration** - Would be duplicated

### Solution

All generic logic moved to `core/` and reused via:
- Inheritance (abstract base classes)
- Composition (injected components)
- Configuration (parametrized behavior)

## Migration Strategy

### Phase 1: Core Infrastructure (Minimal Risk)

1. Create `core/` directory structure
2. Move completely generic modules (no breaking changes):
   - `data_loader.py` → `core/document_loader.py`
   - `batcher.py` → `core/batcher.py`
   - `state.py` → `core/state_manager.py`
3. Update imports in `llm_categoriser/` to use `core/`
4. Run tests to verify no regressions

**Files Affected:** 3 files moved, ~450 lines
**Risk Level:** Low (pure refactoring)
**Testing:** Existing unit tests should pass without changes

---

### Phase 2: Configurable Persistence (Low Risk)

1. Create `core/config.py` with `ReviewConfiguration` base class
2. Create `core/persistence.py` with parametrized persistence
3. Create `llm_categoriser/config.py` with `CategoriserConfiguration`
4. Update `llm_categoriser/persistence.py` to use new core persistence
5. Deprecate old persistence module

**Files Affected:** 4 new files, 1 updated, ~300 lines
**Risk Level:** Low (backward compatible)
**Testing:** Add integration tests for configurable persistence

---

### Phase 3: Abstract Runner (Medium Risk)

1. Create `core/review_runner.py` with abstract base class
2. Extract generic orchestration logic
3. Define extension points (abstract methods)
4. Refactor `llm_categoriser/runner.py` to extend abstract runner
5. Move categoriser-specific logic to concrete methods
6. Update CLI to use new runner

**Files Affected:** 2 new files, 2 updated, ~700 lines
**Risk Level:** Medium (significant refactoring)
**Testing:** Full integration test suite required

---

### Phase 4: CLI Framework (Low Risk)

1. Create `core/base_cli.py` with reusable CLI patterns
2. Refactor `llm_categoriser/cli.py` to use base framework
3. Refactor `llm_categoriser/batch_cli.py` similarly
4. Test all CLI commands

**Files Affected:** 3 files, ~400 lines
**Risk Level:** Low (mostly extraction)
**Testing:** CLI integration tests

---

### Phase 5: Batch Orchestration (Medium Risk)

1. Create `core/batch_orchestrator.py` with abstract base
2. Extract generic batch API logic
3. Parametrize validation and processing
4. Update categoriser batch orchestrator to use core
5. Test batch operations end-to-end

**Files Affected:** 2 files, ~600 lines
**Risk Level:** Medium (complex logic)
**Testing:** Batch API integration tests

---

### Phase 6: Documentation & Examples (Low Risk)

1. Update all module docstrings
2. Create `core/README.md` with usage examples
3. Update `llm_categoriser/README.md` to reference core
4. Create example for new review pass implementation
5. Update main project README

**Files Affected:** Multiple documentation files
**Risk Level:** Very Low
**Testing:** Documentation review

---

## Testing Strategy

### Unit Tests
- Test each core module independently
- Mock dependencies
- Verify abstractions work correctly
- Test configuration objects

### Integration Tests
- Test concrete implementations (CategoriserRunner)
- Verify workflow end-to-end
- Test with real LLM service (mocked)
- Verify state management across runs

### Regression Tests
- Ensure existing categoriser functionality unchanged
- Compare outputs before/after refactoring
- Run on sample data

### Example Implementation Tests
- Create a minimal review pass using core framework
- Verify it works end-to-end
- Document as reference implementation

## Risk Assessment

### High Risk Areas
1. **Runner refactoring** - Complex logic with many interactions
2. **Batch orchestration** - Async operations, state management

**Mitigation:**
- Extensive integration tests
- Staged rollout with feature flags
- Keep old implementation temporarily

### Medium Risk Areas
1. **Persistence changes** - File I/O, data format changes
2. **CLI refactoring** - User-facing interface

**Mitigation:**
- Backward compatibility layer
- Thorough CLI testing
- User documentation

### Low Risk Areas
1. **Pure code moves** (data_loader, batcher, state)
2. **Documentation updates**

**Mitigation:**
- Standard testing
- Code review

## Success Metrics

1. **Code Reusability**
   - Zero duplication of generic logic
   - New review pass requires < 200 lines of code

2. **Maintainability**
   - Each module < 300 lines
   - Clear separation of concerns
   - Comprehensive documentation

3. **Testability**
   - > 90% code coverage
   - All abstractions have unit tests
   - Integration tests for workflows

4. **Backward Compatibility**
   - All existing CLI commands work
   - Output format unchanged
   - No breaking changes for users

5. **Extensibility**
   - New review pass implementable in < 1 day
   - Clear extension points documented
   - Example implementation provided

## Implementation Checklist

### Preparation
- [ ] Review and approve this specification
- [ ] Set up feature branch
- [ ] Create comprehensive test fixtures
- [ ] Document rollback plan

### Phase 1: Core Infrastructure
- [ ] Create `core/` directory
- [ ] Move `data_loader.py` → `core/document_loader.py`
- [ ] Move `batcher.py` → `core/batcher.py`
- [ ] Move `state.py` → `core/state_manager.py`
- [ ] Update all imports in `llm_categoriser/`
- [ ] Run full test suite
- [ ] Code review

### Phase 2: Configurable Persistence
- [ ] Create `core/config.py`
- [ ] Create `core/persistence.py`
- [ ] Create `llm_categoriser/config.py`
- [ ] Update categoriser to use new persistence
- [ ] Add persistence integration tests
- [ ] Code review

### Phase 3: Abstract Runner
- [ ] Create `core/review_runner.py`
- [ ] Extract generic orchestration patterns
- [ ] Define abstract methods
- [ ] Refactor `llm_categoriser/runner.py`
- [ ] Add runner unit tests
- [ ] Add workflow integration tests
- [ ] Code review

### Phase 4: CLI Framework
- [ ] Create `core/base_cli.py`
- [ ] Refactor `llm_categoriser/cli.py`
- [ ] Refactor `llm_categoriser/batch_cli.py`
- [ ] Test all CLI commands
- [ ] Code review

### Phase 5: Batch Orchestration
- [ ] Create `core/batch_orchestrator.py`
- [ ] Extract generic batch logic
- [ ] Update categoriser batch orchestrator
- [ ] Test batch operations
- [ ] Code review

### Phase 6: Documentation
- [ ] Write `core/README.md`
- [ ] Update `llm_categoriser/README.md`
- [ ] Create example review pass
- [ ] Update main README
- [ ] Final review

### Verification
- [ ] All tests passing
- [ ] Code coverage > 90%
- [ ] Example implementation works
- [ ] Documentation complete
- [ ] Performance benchmarks acceptable

## Timeline Estimate

- Phase 1: 1 day
- Phase 2: 2 days
- Phase 3: 3 days (most complex)
- Phase 4: 1 day
- Phase 5: 2 days
- Phase 6: 1 day

**Total: 10 days** (with testing and reviews)

## Conclusion

This refactoring will transform the `llm_review` module from a single-purpose categoriser into a flexible, extensible framework for multiple review passes. The approach follows SOLID principles, eliminates code duplication, and provides clear extension points for future development.

The phased migration strategy ensures minimal risk with comprehensive testing at each stage. The end result will be a maintainable, well-documented codebase that makes adding new review passes straightforward and efficient.
