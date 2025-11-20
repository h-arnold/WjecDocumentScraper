# Coding Agent Instructions: Implement Page-Based Data Loader

## Quick Start

**Primary Task**: Implement a new page-based data loader for the `llm_proofreader` module that processes every page of every document (instead of only processing pre-verified issues).

**Reference Document**: Read `docs/LLM_PROOFREADER_DATA_LOADER_IMPLEMENTATION_GUIDE.md` for complete implementation details.

## What You Need to Do

### 1. Read the Implementation Guide First

Before writing any code, thoroughly read:
```
docs/LLM_PROOFREADER_DATA_LOADER_IMPLEMENTATION_GUIDE.md
```

This guide contains:
- Complete architecture explanation
- Full code for all 5 required modules
- Testing strategies
- Migration plan

### 2. Create 4 New Files

Follow Step 1-4 in the guide to create:

1. **`src/llm_review/llm_proofreader/page_data_loader.py`**
   - Purpose: Load all documents page-by-page with pre-existing issues
   - Key function: `load_page_based_documents()`
   - Reference: Language check module for document processing patterns

2. **`src/llm_review/llm_proofreader/page_batcher.py`**
   - Purpose: Create batches based on page ranges (not issue counts)
   - Key function: `iter_page_batches()`
   - Reference: Existing `src/llm_review/core/batcher.py`

3. **`src/llm_review/llm_proofreader/page_runner.py`**
   - Purpose: Orchestrate page-based proofreading workflow
   - Key class: `PageBasedProofreaderRunner`
   - Reference: Existing `runner.py` in same directory

4. **Add to `src/llm_review/llm_proofreader/prompt_factory.py`**
   - Purpose: Build prompts for page-based batches
   - Key function: `build_page_prompts()`
   - Note: This is an addition to existing file, not a new file

### 3. Update CLI (Step 5)

Modify `src/llm_review/llm_proofreader/cli.py` to add:
- `--page-based` flag
- `--pages-per-batch` parameter
- Conditional logic to use either page-based or issue-based runner

### 4. Write Tests

Create test files:
- `tests/test_page_data_loader.py` - Unit tests for data loader
- `tests/test_page_based_runner_integration.py` - Integration tests

Use examples from the implementation guide.

### 5. Test Your Implementation

```bash
# Run unit tests
uv run pytest tests/test_page_data_loader.py -v

# Test with dry run
uv run python -m src.llm_review.llm_proofreader.cli --page-based --dry-run

# Test with small subject
uv run python -m src.llm_review.llm_proofreader.cli --page-based --subjects "Art-and-Design" --pages-per-batch 3
```

## Key Design Principles

### Follow the Language Check Pattern

The `language_check` module already processes documents page-by-page. Study these files:
- `src/language_check/language_check.py` - Document processing
- `src/language_check/page_utils.py` - Page marker handling
- `src/language_check/report_utils.py` - Report building

### Maintain Consistency

- Use same naming conventions as existing modules
- Follow error handling patterns from `language_check`
- Use existing data structures (`DocumentKey`, `LanguageIssue`, `PassCode`)
- Reuse utilities like `find_page_markers()` and `extract_pages_text()`

### Keep It Modular

- Each new module should be independent and testable
- Don't modify existing issue-based system
- Add new functionality alongside existing code
- Use feature flags (like `--page-based`) for gradual adoption

## Critical Implementation Details

### 1. Pre-existing Issues Must Be Context Only

In the prompt template (`user_llm_proofreader.md`), pre-existing issues should be displayed but marked as:
```markdown
#### Pre-existing issues (Ignore - these have been flagged already)
```

The LLM should see them but NOT report them again.

### 2. Page Batching Strategy

- Default: 5 pages per batch
- Adjustable via `--pages-per-batch`
- Consider token limits when batching
- Each batch should include full page content + pre-existing issues for those pages

### 3. State Management

- Use separate state file: `data/llm_page_proofreader_state.json`
- Track completed batches by DocumentKey + batch index
- Allow resumption of interrupted runs

### 4. Output Format

- Save to: `Documents/<subject>/llm_page_proofreader_reports/<filename>.csv`
- Columns: `page_number`, `issue`, `highlighted_context`, `error_category`, `confidence_score`, `reasoning`
- Use `PassCode.LP` for new findings

## Testing Checklist

Before submitting, verify:

- [ ] All 4 new files created with complete implementations
- [ ] `prompt_factory.py` updated with `build_page_prompts()`
- [ ] `cli.py` updated with page-based mode
- [ ] Unit tests pass for data loader
- [ ] Dry run works without errors
- [ ] Can process at least one small document end-to-end
- [ ] Pre-existing issues appear in prompts correctly
- [ ] State management works (can resume interrupted runs)
- [ ] Output CSV files are created with correct format

## Common Pitfalls to Avoid

1. **Don't break existing system**: Keep issue-based mode working
2. **Don't forget page markers**: Use `find_page_markers()` from page_utils
3. **Don't skip error handling**: Follow patterns from `language_check.py`
4. **Don't hardcode paths**: Use Path objects and configuration
5. **Don't ignore filters**: Respect `--subjects` and `--documents` flags

## Questions?

Refer to these sections in the implementation guide:
- **Architecture**: Section "New System Architecture"
- **Code examples**: Steps 1-5
- **Testing**: Section "Testing Strategy"
- **Troubleshooting**: Section "Troubleshooting"
- **Best practices**: Section "Best Practices"

## Success Criteria

Your implementation is complete when:

1. ✅ Can run: `uv run python -m src.llm_review.llm_proofreader.cli --page-based --dry-run`
2. ✅ Can process a full document with: `--page-based --subjects "Art-and-Design"`
3. ✅ Pre-existing issues appear in prompts but aren't re-reported
4. ✅ Output CSV files contain new findings
5. ✅ State file allows resumption
6. ✅ All tests pass

## Final Notes

- **Take your time**: This is a complex change affecting multiple files
- **Test incrementally**: Test each module as you create it
- **Follow the guide**: All code you need is in the implementation guide
- **Ask questions**: If something is unclear, refer back to the guide sections
- **Maintain quality**: Follow existing code style and patterns

Good luck! The implementation guide has everything you need. 🚀
