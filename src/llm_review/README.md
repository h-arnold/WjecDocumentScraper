# LLM Review Module

## Overview

This module provides infrastructure for implementing multiple LLM-powered review passes on WJEC examination documents. Currently implements:

- **llm_categoriser**: Categorizes LanguageTool issues into error types

## Current Status

⚠️ **Under Refactoring** - See planning documents below

The module is being refactored to separate generic document processing functionality from review-pass-specific implementations. This will enable easy addition of new review passes (fact-checking, style validation, etc.).

## Planning Documents (Important!)

Three comprehensive specification documents have been created:

### 📋 [SUMMARY.md](./SUMMARY.md) - Start Here
Quick reference guide with:
- Executive summary
- Before/after architecture comparison
- Key abstractions
- Benefits and example
- Timeline and next steps

**Read this first** to understand the refactoring at a high level.

### 📘 [REFACTORING_SPEC.md](./REFACTORING_SPEC.md) - Deep Dive
Comprehensive specification (23KB) with:
- Detailed problem statement
- Component-by-component analysis (% generic vs specific)
- Proposed architecture with core/ directory
- SOLID principles application
- DRY analysis
- Risk assessment with mitigation strategies
- 6-phase migration plan
- Success metrics

**Read this** for complete architectural understanding.

### 🔧 [ACTION_PLAN.md](./ACTION_PLAN.md) - Implementation Guide
Step-by-step implementation instructions (40KB) with:
- Concrete file operations for each phase
- Code examples for all abstractions
- Import update procedures
- Verification steps
- Testing requirements
- Rollback procedures

**Use this** when implementing the refactoring.

## Current Architecture

```
src/llm_review/
├── llm_categoriser/          # Categoriser implementation
│   ├── cli.py                # CLI entry point
│   ├── runner.py             # Orchestration logic
│   ├── batcher.py            # Batching issues
│   ├── data_loader.py        # CSV loading
│   ├── persistence.py        # CSV output
│   ├── state.py              # State tracking
│   ├── prompt_factory.py     # Prompt generation
│   ├── batch_orchestrator.py # Batch API support
│   └── batch_cli.py          # Batch CLI commands
└── possible_review_flow.md   # Future review pass ideas
```

**Issues:**
- Generic functionality (loading, batching, state, persistence) tightly coupled with categoriser
- ~70% of code is reusable but not separated
- Adding new review passes would require significant duplication

## Proposed Architecture

```
src/llm_review/
├── core/                          # Generic reusable components
│   ├── document_loader.py         # CSV loading
│   ├── batcher.py                 # Issue batching
│   ├── persistence.py             # Configurable CSV output
│   ├── state_manager.py           # Progress tracking
│   ├── review_runner.py           # Abstract orchestrator
│   ├── batch_orchestrator.py     # Generic batch API
│   ├── base_cli.py                # CLI framework
│   ├── config.py                  # Configuration base
│   └── models.py                  # Shared models
│
├── llm_categoriser/               # Categoriser implementation
│   ├── runner.py                  # Extends ReviewRunner
│   ├── prompt_factory.py          # Categoriser prompts
│   ├── config.py                  # Categoriser config
│   └── cli.py                     # Uses base_cli
│
└── [future review passes]/        # Easy to add
    ├── llm_fact_checker/
    ├── llm_style_validator/
    └── ...
```

**Benefits:**
- 50% reduction in categoriser module size
- Zero code duplication
- New review pass in < 200 lines
- Clear separation of concerns
- SOLID principles throughout

## Adding a New Review Pass (After Refactoring)

```python
# 1. Define configuration
class MyReviewConfig(ReviewConfiguration):
    def get_output_path(self, key: DocumentKey) -> Path:
        return Path("Documents") / key.subject / "my_reports" / f"{key.filename}.csv"
    
    def get_csv_columns(self) -> list[str]:
        return ["issue_id", "field1", "field2", "field3"]

# 2. Implement runner
class MyReviewRunner(ReviewRunner):
    def _build_prompts(self, batch: Batch) -> list[str]:
        return render_my_prompts(batch)
    
    def _validate_response(self, response, issues):
        return validate_my_response(response, issues)

# 3. Create CLI (optional)
class MyReviewCLI(BaseCLI):
    def get_default_config(self):
        return MyReviewConfig(...)

# Done! All generic logic (loading, batching, state, retry) is reused.
```

## Current Implementation

### llm_categoriser

Categorizes LanguageTool-detected issues into error types:

**Input:** `Documents/language-check-report.csv`
**Output:** `Documents/<subject>/document_reports/<filename>.csv`

**Features:**
- Batch processing with configurable size
- Retry logic for failed validations
- State management for resume capability
- Synchronous (chat API) and asynchronous (batch API) modes
- Comprehensive error logging

**Usage:**
```bash
# Synchronous categorisation
uv run python -m src.llm_review.llm_categoriser

# With filters
uv run python -m src.llm_review.llm_categoriser --subjects Geography

# Batch API
uv run python -m src.llm_review.llm_categoriser batch-create
uv run python -m src.llm_review.llm_categoriser batch-fetch --check-all-pending
```

See `llm_categoriser/README.md` for detailed documentation.

## Future Review Passes (Planned)

Based on `possible_review_flow.md`:

1. **Document Conversion Cleanup** - Classify parsing vs human errors
2. **Contextual Language Review** - Catch wrong-word errors
3. **Grounded Factual Verification** - RAG-based fact checking
4. **Internal Consistency** - Arithmetic and cross-reference checking
5. **Cross-Document Consistency** - Suite-wide validation

Each will be implementable in < 200 lines by extending `core/` abstractions.

## Implementation Timeline

| Phase | Tasks | Duration | Risk |
|-------|-------|----------|------|
| 1 | Move generic modules to core/ | 1 day | Low |
| 2 | Create configurable persistence | 2 days | Low |
| 3 | Extract abstract runner | 3 days | Medium |
| 4 | CLI framework | 1 day | Low |
| 5 | Batch orchestration | 2 days | Medium |
| 6 | Documentation & examples | 1 day | Low |

**Total:** 10 days + 2 days testing = **2 weeks**

## Development Guidelines

### For Current Development (Before Refactoring)

- All changes should be made in `llm_categoriser/`
- Follow existing patterns
- Consider impact of upcoming refactoring
- Document any new coupling for refactoring analysis

### For Future Development (After Refactoring)

1. **Understand abstractions** - Read `core/README.md`
2. **Extend, don't modify** - New passes extend `ReviewRunner`
3. **Configure, don't hardcode** - Use configuration objects
4. **Test at all levels** - Unit, integration, regression
5. **Document extensions** - Update this README with new passes

## Testing

### Current Tests

```bash
# Run all categoriser tests
uv run pytest tests/llm_categoriser/ -v

# Run specific test
uv run pytest tests/llm_categoriser/test_batcher.py -v
```

### After Refactoring

```bash
# Core module tests
uv run pytest tests/core/ -v

# Categoriser tests
uv run pytest tests/llm_categoriser/ -v

# Integration tests
uv run pytest tests/integration/test_review_workflow.py -v
```

## Documentation

- **This README**: Module overview and refactoring status
- **SUMMARY.md**: Executive summary of refactoring
- **REFACTORING_SPEC.md**: Complete architectural specification
- **ACTION_PLAN.md**: Implementation guide
- **llm_categoriser/README.md**: Categoriser-specific documentation
- **llm_categoriser/LLM_CATEGORISER_SPEC.md**: Original categoriser spec
- **possible_review_flow.md**: Ideas for future review passes

## Related Documentation

- **docs/ARCHITECTURE.md**: Overall project architecture
- **docs/UV_GUIDE.md**: Using uv for development
- **docs/DEV_WORKFLOWS.md**: Development workflows

## Contributing

Before making changes:

1. Read **SUMMARY.md** to understand refactoring plans
2. Check if change affects generic vs specific functionality
3. Follow SOLID principles
4. Add tests for new functionality
5. Update relevant documentation

## Status

- ✅ **Current State**: llm_categoriser working and tested
- ✅ **Planning**: Comprehensive specification complete
- ⏳ **Refactoring**: Awaiting approval to begin
- ⬜ **Future Passes**: Planned but not implemented

## Questions?

1. **What's being refactored?** See SUMMARY.md
2. **Why refactor?** See REFACTORING_SPEC.md "Problem Statement"
3. **How to implement?** See ACTION_PLAN.md
4. **When complete?** Estimated 2 weeks after approval
5. **Impact on users?** None - backward compatible

## Contact

For questions about refactoring:
- Review the planning documents
- Check inline comments in ACTION_PLAN.md
- Consult REFACTORING_SPEC.md for rationale

---

**Last Updated:** 2025-11-18
**Status:** Planning complete, awaiting implementation approval
**Documents:** 3 specs (72KB total)
