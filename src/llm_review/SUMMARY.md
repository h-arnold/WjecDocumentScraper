# LLM Review Module Refactoring - Executive Summary

## Purpose

This folder contains the comprehensive specification and implementation plan for refactoring the `llm_review` module to separate generic document processing functionality from categoriser-specific logic.

## Documents

### 1. REFACTORING_SPEC.md
**Comprehensive analysis and architectural design**

- **Problem Statement**: Identifies tight coupling between generic and specific functionality
- **Current Architecture Analysis**: Detailed breakdown of each module (3000+ lines) with percentage split of generic vs. specific code
- **Proposed Architecture**: New directory structure with `core/` for generic components
- **SOLID Principles Application**: How each principle is applied to the refactoring
- **DRY Analysis**: Elimination of code duplication
- **Risk Assessment**: High/medium/low risk areas with mitigation strategies
- **Success Metrics**: Measurable criteria for the refactoring

### 2. ACTION_PLAN.md
**Step-by-step implementation guide**

- **Phase 1**: Move completely generic modules (data_loader, batcher, state) - 1 day
- **Phase 2**: Create configurable persistence - 2 days
- **Phase 3**: Extract abstract runner - 3 days
- **Phase 4**: CLI framework - 1 day
- **Phase 5**: Batch orchestration - 2 days
- **Phase 6**: Documentation - 1 day

Each phase includes:
- Concrete file operations
- Code examples
- Import updates
- Verification steps
- Testing requirements

### 3. This README (SUMMARY.md)
**Quick reference guide**

## Key Outcomes

### Before Refactoring
```
src/llm_review/
└── llm_categoriser/
    ├── cli.py (491 lines - mixed concerns)
    ├── runner.py (513 lines - mixed concerns)
    ├── batcher.py (115 lines - 100% generic)
    ├── data_loader.py (172 lines - 100% generic)
    ├── persistence.py (251 lines - 90% generic)
    ├── state.py (162 lines - 100% generic)
    ├── prompt_factory.py (82 lines - specific)
    ├── batch_orchestrator.py (556 lines - 80% generic)
    └── batch_cli.py (~200 lines - 70% generic)

Total: ~3000 lines with significant duplication risk
```

### After Refactoring
```
src/llm_review/
├── core/                          # Reusable components (~1500 lines)
│   ├── document_loader.py         # Generic CSV loading
│   ├── batcher.py                 # Generic batching
│   ├── persistence.py             # Configurable persistence
│   ├── state_manager.py           # Generic state tracking
│   ├── review_runner.py           # Abstract orchestrator
│   ├── batch_orchestrator.py     # Generic batch API
│   ├── base_cli.py                # Reusable CLI framework
│   ├── config.py                  # Configuration base classes
│   └── models.py                  # Shared data models
│
├── llm_categoriser/               # Categoriser implementation (~500 lines)
│   ├── runner.py                  # Extends ReviewRunner
│   ├── prompt_factory.py          # Categoriser prompts
│   ├── config.py                  # Categoriser configuration
│   ├── cli.py                     # Uses base_cli
│   └── batch_cli.py               # Uses core batch orchestrator
│
└── [future review passes]/        # Easy to add
    ├── llm_fact_checker/
    ├── llm_style_validator/
    └── ...
```

## Architecture Principles

### Single Responsibility Principle (SRP)
- Each module has one clear purpose
- Orchestration, validation, persistence separated

### Open/Closed Principle (OCP)
- Core framework is closed for modification
- New review passes extend via abstract base classes

### Liskov Substitution Principle (LSP)
- All `ReviewRunner` subclasses can be used interchangeably
- Consistent interface contracts

### Interface Segregation Principle (ISP)
- Focused interfaces: `IDocumentLoader`, `IBatcher`, `IPromptBuilder`, etc.
- No forced dependencies on unused functionality

### Dependency Inversion Principle (DIP)
- High-level components depend on abstractions
- Concrete implementations injected via configuration

## Key Abstractions

### 1. ReviewConfiguration
Base class for all review pass configurations:
- Input/output paths
- Batch settings
- State management
- LLM settings
- CSV column definitions

### 2. ReviewRunner
Abstract base class providing:
- Generic orchestration workflow
- Retry logic
- Error handling
- Progress tracking
- Extension points: `_build_prompts()`, `_validate_response()`

### 3. PersistenceManager
Configurable persistence with:
- Parametrized output paths
- Custom CSV columns
- Atomic writes
- Merge logic

### 4. StateManager
Generic state tracking:
- Resume capability
- Batch completion tracking
- JSON state file

### 5. BaseCLI
Reusable CLI framework:
- Common arguments
- Service setup
- Subclass hooks

## Implementation Phases

### Phase 1: Foundation (Low Risk - 1 day)
Move completely generic modules to `core/`:
- `data_loader.py` → `core/document_loader.py`
- `batcher.py` → `core/batcher.py`
- `state.py` → `core/state_manager.py`

**Risk**: Very low - pure code movement
**Impact**: No user-facing changes

### Phase 2: Configurability (Low Risk - 2 days)
Make persistence configurable:
- Create `core/config.py`
- Create `core/persistence.py`
- Create `llm_categoriser/config.py`

**Risk**: Low - backward compatible
**Impact**: Enables future flexibility

### Phase 3: Abstraction (Medium Risk - 3 days)
Extract generic orchestration:
- Create `core/review_runner.py`
- Refactor `llm_categoriser/runner.py` to extend

**Risk**: Medium - complex refactoring
**Impact**: Major architectural improvement

### Phase 4-6: Polish (Low Risk - 4 days)
CLI framework, batch orchestration, documentation

**Risk**: Low - incremental improvements
**Impact**: Developer experience

## Benefits

### For Maintainers
- **50% less code to maintain** in categoriser module
- **Clear separation of concerns** makes debugging easier
- **Comprehensive tests** at abstraction layer catch issues early

### For Future Development
- **New review pass in < 200 lines** of code
- **Reuse all generic logic** (loading, batching, state, persistence)
- **Focus on domain logic** (prompts, validation)

### For Quality
- **SOLID principles** ensure maintainability
- **DRY approach** eliminates duplication
- **Abstract base classes** enforce consistency

## Example: Adding a New Review Pass

```python
# 1. Create configuration
class StyleCheckerConfiguration(ReviewConfiguration):
    def get_output_path(self, key: DocumentKey) -> Path:
        return Path("Documents") / key.subject / "style_reports" / f"{key.filename}.csv"
    
    def get_csv_columns(self) -> list[str]:
        return ["issue_id", "style_issue", "suggestion", "severity"]

# 2. Create runner
class StyleCheckerRunner(ReviewRunner):
    def _build_prompts(self, batch: Batch) -> list[str]:
        # Build style-checking prompts
        return render_style_prompt(batch)
    
    def _validate_response(self, response, issues):
        # Validate style-check response
        return validate_style_response(response, issues)

# 3. Create CLI (optional)
class StyleCheckerCLI(BaseCLI):
    def get_default_config(self) -> ReviewConfiguration:
        return StyleCheckerConfiguration(...)
    
    def add_custom_arguments(self, parser):
        parser.add_argument("--style-guide", help="Path to style guide")

# Done! ~150 lines of code for a complete review pass.
```

## Risk Mitigation

### Testing
- Unit tests for each core module
- Integration tests for workflows
- Regression tests for existing functionality
- Example implementation as reference

### Rollback
- Phased approach allows partial rollback
- Each phase is independently testable
- Keep deprecated modules temporarily

### Communication
- Document in each PR
- Code review for each phase
- Update user-facing documentation

## Success Metrics

### Code Quality
- [x] Zero duplication of generic logic
- [ ] Each module < 300 lines
- [ ] > 90% test coverage
- [ ] All SOLID principles applied

### Functionality
- [ ] All existing features work unchanged
- [ ] Output format identical
- [ ] CLI commands work as before
- [ ] Performance acceptable

### Extensibility
- [ ] Example review pass implemented
- [ ] Clear documentation for adding passes
- [ ] New pass requires < 200 lines

## Timeline

- **Planning & Approval**: 1 day (complete)
- **Implementation**: 10 days (6 phases)
- **Testing & Review**: 2 days
- **Documentation**: 1 day (included in phases)

**Total**: ~2 weeks

## Next Steps

1. **Review these documents** with the team
2. **Approve the approach** or suggest modifications
3. **Create feature branch** for implementation
4. **Begin Phase 1** (foundation - low risk)
5. **Iterative implementation** following the ACTION_PLAN
6. **Continuous testing** after each phase
7. **Final review** before merging

## Questions?

See the detailed documents:
- **REFACTORING_SPEC.md** for comprehensive analysis
- **ACTION_PLAN.md** for step-by-step implementation

## Status

✅ **Planning Complete**
⏳ **Awaiting Approval**
⬜ **Implementation Pending**

---

*Generated: 2025-11-18*
*Author: Copilot Agent*
*Purpose: Specification and planning only - no code changes*
