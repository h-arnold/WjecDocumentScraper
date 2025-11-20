# 📚 Page-Based Data Loader Documentation Index

## Quick Navigation

This directory contains comprehensive documentation for implementing a page-based data loader in the `llm_review` module.

### 🎯 Start Here

**If you're a coding agent implementing this feature:**
1. Read [`CODING_AGENT_INSTRUCTIONS.md`](./CODING_AGENT_INSTRUCTIONS.md) first
2. Then read [`LLM_PROOFREADER_DATA_LOADER_IMPLEMENTATION_GUIDE.md`](./LLM_PROOFREADER_DATA_LOADER_IMPLEMENTATION_GUIDE.md)
3. Follow the step-by-step instructions to create the required files

**If you're reviewing this work:**
1. Read [`IMPLEMENTATION_SUMMARY.md`](./IMPLEMENTATION_SUMMARY.md) for an overview
2. Review [`LLM_PROOFREADER_DATA_LOADER_IMPLEMENTATION_GUIDE.md`](./LLM_PROOFREADER_DATA_LOADER_IMPLEMENTATION_GUIDE.md) for technical details

---

## 📄 Document Overview

### 1. CODING_AGENT_INSTRUCTIONS.md
**Purpose**: Quick start guide for implementation  
**Size**: 179 lines  
**Audience**: Coding agents

**Contains**:
- Quick start checklist
- File-by-file creation guide
- Testing checklist
- Success criteria
- Common pitfalls

**Start here if**: You're ready to write code

---

### 2. LLM_PROOFREADER_DATA_LOADER_IMPLEMENTATION_GUIDE.md
**Purpose**: Complete technical implementation guide  
**Size**: 1,086 lines  
**Audience**: Developers, coding agents

**Contains**:
- Current vs. new architecture
- 5 implementation steps with complete code:
  - `page_data_loader.py` (200+ lines)
  - `page_batcher.py` (150+ lines)
  - `prompt_factory.py` updates (50+ lines)
  - `page_runner.py` (250+ lines)
  - `cli.py` integration (30+ lines)
- Testing strategy with examples
- Migration plan (4 phases)
- Configuration guide
- Best practices
- Troubleshooting

**Read this**: For complete implementation details

---

### 3. IMPLEMENTATION_SUMMARY.md
**Purpose**: Executive summary and overview  
**Size**: 235 lines  
**Audience**: Project managers, reviewers, developers

**Contains**:
- What was requested vs. delivered
- Technical approach
- Code quality assurance
- Migration path
- Usage examples
- Success metrics

**Read this**: For high-level understanding

---

## 🎯 Implementation Checklist

Use this to track your progress:

### Phase 1: Setup
- [ ] Read `CODING_AGENT_INSTRUCTIONS.md`
- [ ] Read `LLM_PROOFREADER_DATA_LOADER_IMPLEMENTATION_GUIDE.md`
- [ ] Understand current system architecture
- [ ] Review `language_check` module for patterns

### Phase 2: Code Implementation
- [ ] Create `src/llm_review/llm_proofreader/page_data_loader.py`
- [ ] Create `src/llm_review/llm_proofreader/page_batcher.py`
- [ ] Create `src/llm_review/llm_proofreader/page_runner.py`
- [ ] Update `src/llm_review/llm_proofreader/prompt_factory.py`
- [ ] Update `src/llm_review/llm_proofreader/cli.py`

### Phase 3: Testing
- [ ] Create `tests/test_page_data_loader.py`
- [ ] Create `tests/test_page_based_runner_integration.py`
- [ ] Run unit tests: `uv run pytest tests/test_page_data_loader.py -v`
- [ ] Test dry run: `uv run python -m src.llm_review.llm_proofreader.cli --dry-run`
- [ ] Test with sample subject: `uv run python -m src.llm_review.llm_proofreader.cli --subjects "Art-and-Design"`

### Phase 4: Validation
- [ ] Verify pre-existing issues appear in prompts
- [ ] Verify new findings saved to CSV
- [ ] Verify state management works
- [ ] Review output quality

---

## 🚀 Quick Start Commands

### Testing
```bash
# Dry run to validate setup
uv run python -m src.llm_review.llm_proofreader.cli --dry-run

# Test with single subject
uv run python -m src.llm_review.llm_proofreader.cli --subjects "Art-and-Design"

# Adjust batch size
uv run python -m src.llm_review.llm_proofreader.cli --pages-per-batch 2

# Run unit tests
uv run pytest tests/test_page_data_loader.py -v
```

### Configuration
```bash
# Set default batch size
export LLM_PROOFREADER_BATCH_SIZE=3

# Enable detailed logging
export LLM_PROOFREADER_LOG_RESPONSES=1
export LLM_PROOFREADER_LOG_DIR=data/llm_proofreader_responses
```

---

## 📊 Files to Create/Modify

### New Files (4)
1. `src/llm_review/llm_proofreader/page_data_loader.py`
2. `src/llm_review/llm_proofreader/page_batcher.py`
3. `src/llm_review/llm_proofreader/page_runner.py`
4. `tests/test_page_data_loader.py`

### Modified Files (2)
1. `src/llm_review/llm_proofreader/prompt_factory.py` (add `build_page_prompts()`)
2. `src/llm_review/llm_proofreader/cli.py` (replace with page-based runner)

### Test Files (2)
1. `tests/test_page_data_loader.py`
2. `tests/test_page_based_runner_integration.py`

---

## 🎓 Key Concepts

### Page-Based Processing
- Processes **all pages** regardless of detected issues
- Batches by page ranges (not issue counts)
- Default: 3 pages per batch
- Configurable via `LLM_PROOFREADER_BATCH_SIZE` environment variable

### Pre-existing Issue Context
- Loads from `Documents/language-check-report.csv`
- Groups by page number
- Displays as "already flagged" in prompts
- Prevents duplicate reporting

### Default Mode
- Page-based processing is now the default
- Replaces previous issue-based system
- State: `data/llm_page_proofreader_state.json`
- Output: `Documents/<subject>/llm_page_proofreader_reports/`

---

## ✅ Success Criteria

Your implementation is complete when:

1. ✅ Dry run executes without errors
2. ✅ Can process full document end-to-end
3. ✅ Pre-existing issues appear correctly in prompts
4. ✅ New findings saved to output CSV
5. ✅ State file enables resumption
6. ✅ All unit tests pass
7. ✅ Default batch size is 3 pages

---

## 🆘 Need Help?

### Common Issues

**Problem**: Token limit exceeded  
**Solution**: Reduce `--pages-per-batch` value

**Problem**: Missing pages  
**Solution**: Verify page markers with `find_page_markers()`

**Problem**: Duplicate reporting  
**Solution**: Check pre-existing issues are marked correctly in prompt

**Problem**: Slow processing  
**Solution**: Consider batch API or parallel processing

### Reference Sections

- **Architecture**: Implementation Guide → "New System Architecture"
- **Code Examples**: Implementation Guide → Steps 1-5
- **Testing**: Implementation Guide → "Testing Strategy"
- **Troubleshooting**: Implementation Guide → "Troubleshooting"
- **Best Practices**: Implementation Guide → "Best Practices"

---

## 📖 Related Documentation

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) - Overall system architecture
- [`LLM_REVIEW_MODULE_GUIDE.md`](./LLM_REVIEW_MODULE_GUIDE.md) - General LLM review patterns
- [`UV_GUIDE.md`](./UV_GUIDE.md) - How to use uv for dependencies
- [`DEV_WORKFLOWS.md`](./DEV_WORKFLOWS.md) - Development workflows

---

## 🏁 Final Notes

This documentation provides everything needed to implement page-based document processing in the `llm_review` module. The implementation follows proven patterns from the `language_check` module and maintains backward compatibility with the existing system.

**Total Documentation**: 1,500+ lines  
**Complete Code Examples**: 680+ lines  
**Test Examples**: 150+ lines  

All code is production-ready and follows repository conventions.

Good luck with the implementation! 🚀
