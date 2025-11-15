# LLM Categoriser**LLM Categoriser – Detailed Implementation Blueprint**



This folder contains the LLM-driven categoriser for LanguageTool issues. It ingests the `Documents/language-check-report.csv`, batches the issues per-document, builds contextual prompts using templates in `src/prompt/promptFiles`, calls configured LLM providers (via `src/llm.service`), validates the JSON response using `src/models/language_issue.LanguageIssue`, and persists the categorised issues.- **Scope**: Build a standalone categoriser that ingests `Documents/language-check-report.csv`, batches issues per document, prompts an LLM (via templates in `src/prompt/promptFiles/`) with per-batch tables and page context, retries malformed responses, and stores CSV outputs per document under `Documents/<subject>/document_reports/`.

- **Tech Constraints**: Stay single-threaded for API requests (this is a toy project using free-tier LLMs, so no point attempting concurrency); respect provider-specific minimum request intervals; default batch size 10 (env/CLI override); maximum two retries on JSON parse/validation failure per batch; persistence happens per batch (redo the batch if interrupted).

This README summarises each module, data flow, contracts, error handling, where failed validations are logged and how to run and test the code in this folder.- **Primary Dependencies**: `src.models.language_issue.LanguageIssue` (unified model), `src.models.document_key.DocumentKey`, `src.utils.page_utils.extract_pages_text`, `src.prompt.render_prompt.render_template`, `src.llm.provider_registry.create_provider_chain`, `src.llm.service.LLMService`, `src.models.ErrorCategory`.



## Overview---



- Entry point: `src/llm_review/llm_categoriser/cli.py` or `python -m src.llm_review.llm_categoriser`### Workflow Overview

- Top-level flow: load CSV -> batch issues -> build prompt -> call LLM -> validate -> save results

- Output location: `Documents/<Subject>/document_reports/<filename>.csv`1. **Load issues**: Parse the LanguageTool CSV report into `LanguageIssue` objects grouped by subject and filename.

- Failed validations: written to `data/llm_categoriser_errors/<subject>/<filename>.batch-<index>.errors.json`2. **Batch issues**: Slice each document’s issues into manageable batches (default 10). For every batch, collect the relevant page snippets from the Markdown source so the LLM gets only the necessary context.

3. **Render prompts**: Build a two-part prompt (system + user) using `language_tool_categoriser.md` (with partials `llm_reviewer_system_prompt.md` and `authoritative_sources.md`) that:

## Key modules and responsibilities   - Introduces the subject and document being reviewed.

   - Presents the batch as a Markdown table mirroring the CSV columns.

- `data_loader.py`   - Appends a “Page context” section listing the raw Markdown for each referenced page.

  - Reads the language-check CSV and maps it to `LanguageIssue` objects.4. **Send to LLM**: Use `LLMService` to call the configured provider (chat or batch endpoint). Enforce provider min-request intervals to respect quotas.

  - Assigns `issue_id` per-document (auto-increment starting at 0).5. **Validate output**: Parse the returned JSON, repair it when needed, and validate each record using `LanguageIssue.from_llm_response()`. On failure, isolate the problematic issues and re-ask the provider (up to two retries). Any remaining failures are logged and skipped.

  - Validates the corresponding Markdown file exists at `Documents/<subject>/markdown/<filename>`.6. **Persist results**: Write valid responses into `Documents/<Subject>/document_reports/<filename>.csv`, one row per `issue_id`. Track completed batches in a state file so restarts skip successful work unless `--force` is used.

  - Returns a dict: `DocumentKey -> list[LanguageIssue]`.7. **Manual testing**: Optional `--emit-batch-payload` flag writes batch payloads to `data/` and exits, enabling manual submission to provider batch consoles.



- `batcher.py`---

  - Splits a document's issues into batches (default 10).

  - Deduplicates page numbers and collects page excerpts for context.### Error Categories

  - Returns `Batch` objects (dataclass) containing:

    - subject, filename, index, issues (list[LanguageIssue])The LLM must classify each issue into one of these enums (defined in `src/models/enums.py`):

    - page_context: mapping page number -> page markdown

    - markdown_table: a simplified 4-column table used in LLM prompts- `PARSING_ERROR`: Mechanical or tokenisation mistakes such as missing hyphens (`privacyfocused`) or accidental concatenations.

- `SPELLING_ERROR`: Genuine misspellings or the wrong lexical choice given context (e.g., “their” vs “there”).

- `prompt_factory.py`- `ABSOLUTE_GRAMMATICAL_ERROR`: Definite grammatical violations, including non-UK spelling variants that conflict with policy (“organize” vs “organise”).

  - Renders templates using `src/prompt/render_prompt.py`.- `POSSIBLE_AMBIGUOUS_GRAMMATICAL_ERROR`: Grammatically debatable constructions that may be awkward or non-standard rather than strictly wrong.

  - Returns `[system_prompt, user_prompt]` or just `[user_prompt]`.- `STYLISTIC_PREFERENCE`: Stylistic suggestions where the original text is acceptable (“in order to” vs “to”).

  - Template context includes subject, filename, `issue_table`, `issue_pages`, and `page_context`.- `FALSE_POSITIVE`: Legitimate text flagged incorrectly (specialist terminology, proper nouns, foreign-language usage, etc.).



- `runner.py`Each record also carries a `confidence_score` (0–100) and a single-sentence `reasoning` justification referencing authoritative sources or contextual cues.

  - Orchestrates the categoriser: batching, prompting, LLM calls (via `LLMService`), validation & retries.

  - Validation: uses `LanguageIssue.from_llm_response()` to ensure data conforms to the expected model.---

  - If validation fails for some issues, re-prompts only those failures (by `issue_id`) up to the configured number of retries.

  - Persists validated results as flat batches using `persistence.save_batch_results()`.

  - If a batch cannot be validated after retries, saves failure details with `persistence.save_failed_issues()`.

### Expected Output Structure

- **LLM response**: A single JSON array (no root object) where each element contains exactly `issue_id`, `error_category`, `confidence_score`, and `reasoning`.

- **Persisted artifact**: After validation, each document gets a CSV at `Documents/<Subject>/document_reports/<filename>.csv` with columns `issue_id`, `page_number`, `issue`, `highlighted_context`, `error_category`, `confidence_score`, and `reasoning`. Rows are deduplicated by `issue_id`, so reruns simply overwrite the latest categorisation.

- **`persistence.py`**

  - `save_batch_results()` writes/merges CSV rows atomically (temp file + replace) and deduplicates by `issue_id`.

  - `save_failed_issues()` writes failed validation logs to `data/llm_categoriser_errors/<subject>/...`, including collected `error_messages` metadata for debugging.

- **`state.py`**

  - Tracks progress per document in a persistable state file so reruns can skip completed batches unless `--force` is set.

- **`cli.py` & `__main__.py`**

  - Provide the CLI. Key options include subject/document filters, batch size, `--max-retries`, `--state-file`, `--force`, `--emit-batch-payload`, `--dotenv`, and `--dry-run`.

## Error logging and debugging

Set `LLM_CATEGORISER_LOG_RESPONSES=true` (or pass `--log-responses` on the CLI) to dump every raw provider reply into `data/llm_categoriser_responses/<subject>/...` (override the directory with `LLM_CATEGORISER_LOG_DIR=/path` or `--log-responses-dir`). Leave the env var empty/undefined and omit the flag to disable logging when you’re not debugging.

### Core Modules & Responsibilities

- These files are stored under `data` so they are easy to inspect and debug without overwriting Documents output. They are meant to be read by the maintainers when manual inspection of LLM responses is required.

- **`models/document_key.py`** (new)

## Running & testing  - Frozen dataclass containing `subject: str` and `filename: str` for identifying documents.

  - Provides `__str__()` returning `"{subject}/{filename}"` for composite keys.

- Run categoriser CLI (example):

- **`llm_categoriser/data_loader.py`**

```bash  - Parse CSV into `LanguageIssue` objects grouped by `DocumentKey`.

uv run python -m src.llm_review.llm_categoriser --documents "gcse-art-and-design---guidance-for-teaching.md"  - Assign auto-incrementing `issue_id` (starting at 0) to each issue within a document.

```  - Validate corresponding Markdown files exist at `Documents/<subject>/markdown/<filename>`.

  - Filter for subject/document subsets if requested.

- `--dry-run` will skip the LLM call and validate only data loading.  - Error handling: If Markdown file missing, log error and skip that document; if page markers malformed, log and skip.

  - Contract: `load_issues(report_path: Path, *, subjects: set[str] | None, documents: set[str] | None) -> dict[DocumentKey, list[LanguageIssue]]`.

- `--emit-batch-payload` can be used to write the prompt payloads to `data/batch_payloads` for manual inspection and simulating provider calls.

- **`llm_categoriser/batcher.py`**

- Tests for this module live under `tests/llm_categoriser/` and cover:  - Chunk issues per document by issue count (`batch_size`, default 10).

  - `data_loader` behaviour and CSV parsing  - For each batch: deduplicate page numbers, fetch page snippets via `extract_pages_text`.

  - `batcher` logic and page_context extraction  - For documents with no page numbers (empty Page column in CSV), submit the entire document content as context for all batches.

  - `prompt_factory` correctness and partial handling  - Create simplified Markdown tables using helper from `report_utils.py` (4 columns: issue_id, page_number, issue, highlighted_context).

  - Validation and error logging (including `save_failed_issues` changes)  - Contract: `iter_batches(issues: list[LanguageIssue], batch_size: int, markdown_path: Path) -> Iterable[Batch]` where each `Batch` contains `subject`, `filename`, `index`, `issues`, `page_context`, `markdown_table`.



- Use uv for the environment: `uv run pytest tests/llm_categoriser -q`.- **`llm_categoriser/prompt_factory.py`**

  - Render prompts using the revised `language_tool_categoriser.md` template.

## File naming and invariants  - Template context must provide: `subject`, `filename`, `issue_table` (simplified 4-column table), and `page_context` (list of dicts with `page_number` and `content`).

  - Contract: `build_prompts(batch: Batch) -> list[str]` returning `[system_prompt, user_prompt]`.

- `DocumentKey(subject, filename)` uniquely identifies a document.

- `issue_id` is unique per-document.- **`llm/json_utils.py`** (new)

- Page keys in JSON results always use the `page_<n>` format.  - Shared JSON extraction/repair using `json-repair` plus validation helpers.

- `highlighted_context` is used in prompts instead of the older `context` column.  - Extract functionality from `GeminiLLM._parse_response_json()` into this module for reuse across all providers.

  - Contract: `parse_json_response(text: str) -> Any` - extracts JSON from text, repairs, and parses.

## Next steps & suggestions  - `GeminiLLM` and future providers delegate to this utility when `filter_json=True`.



- Add a helper to print a friendly summary of `errors` when a batch fails: mapping between `issue_id`, `rule_id`, and the error messages for quicker CLI troubleshooting.- **`llm_categoriser/runner.py`**

- Consider storing raw LLM responses for the failing batches for advanced post-mortem analysis (beware PII & size).  - Orchestrate the workflow: call providers with `filter_json=True`, apply retries using `issue_id` to track problematic issues, validate using `LanguageIssue.from_llm_response()`, and direct successful results to persistence.

- Add rotation/retention policy for `data/llm_categoriser_errors` if the project runs regularly.  - Respects provider min-request intervals and logs quota fallbacks.

  - Logging: Use idiomatic Python print statements for progress/status reporting.

If you want me to expand any of these sections into a developer-facing doc (with examples of prompt payloads or a quick CLI recipe for reproducing errors), tell me which one and I'll add it.
- **`llm_categoriser/persistence.py`**
  - Write per-document JSON atomically (temp file + replace); merge batches when rerunning without `--force`.
  - Create `document_reports/` directory if it doesn't exist.

- **`llm_categoriser/state.py`**
  - Maintain a JSON state file (default `data/llm_categoriser_state.json`) with nested structure:
    ```json
    {
      "version": "1.0",
      "subjects": {
        "Art-and-Design": {
          "file.md": {
            "completed_batches": [0, 1, 2],
            "total_issues": 45
          }
        }
      }
    }
    ```
  - Tracks completed batches per document; cleared/reset with `--force`.

- **`llm_categoriser/cli.py` & `__main__.py`**
  - Provide CLI entrypoint: `python -m src.llm_review.llm_categoriser`
  - Options: `--subjects`, `--documents`, `--from-report`, `--batch-size`, `--max-retries`, `--state-file`, `--force`, `--use-batch-endpoint`, `--emit-batch-payload`, `--provider`, `--dotenv`, `--dry-run`.
  - Use British spelling throughout (e.g., "categoriser", "optimise", "behaviour").

---

### Provider & Template Adjustments

- **Rate Limiting**: Extend provider wrappers (starting with Gemini) to honour a `min_request_interval` to respect provider rate limits. Environment variables like `GEMINI_MIN_REQUEST_INTERVAL` control intervals.
- **JSON Parsing**: Extract `GeminiLLM._parse_response_json()` functionality into `llm/json_utils.py` so every provider behaves consistently. All providers should delegate to this shared utility when `filter_json=True`.
- **Error Context**: Ensure provider errors carry context for runner logging and retry decisions.
- **Template Partials**: Update `render_prompt.py` to load both required partials:
  ```python
  partials = {
      "llm_reviewer_system_prompt": _read_prompt("llm_reviewer_system_prompt.md"),
      "authoritative_sources": _read_prompt("authoritative_sources.md")
  }
  renderer = pystache.Renderer(partials=partials)
  ```
- **Template Synchronisation**: When templates in `src/prompt/promptFiles/` change, adjust `prompt_factory.py` and related tests to keep placeholder names consistent.

---

### Retry & Error Handling

1. Parse provider response via shared `json_utils.parse_json_response()`.
2. Validate each entry using `LanguageIssue.from_llm_response()` which parses LLM response fields and validates using Pydantic.
3. If some records fail validation, use `issue_id` to map failed outputs back to input issues, rebuild a reduced prompt with only those issues, and retry (max two retries). Successful records are kept; failed ones after retries are printed (logged) and skipped.
4. Malformed page markers or missing Markdown files: log error and skip the document.
5. State file is only updated after a batch fully succeeds to avoid skipping unfinished work on rerun.
6. Single-issue batches or batches smaller than `batch_size` are handled with standard logic.

---

### Persistence & Output

- Results stored in `Documents/<Subject>/document_reports/<filename>.csv`.
- Each write is atomic (temporary file + replace).
- Existing files are merged unless `--force` is set.
- Optional state/resume support prevents duplicate calls when restarting the CLI.

---

### CLI & Configuration

- Key options: `--subjects`, `--documents`, `--from-report`, `--batch-size`, `--max-retries`, `--state-file`, `--force`, `--use-batch-endpoint`, `--emit-batch-payload`, `--provider`, `--dotenv`, `--dry-run`.
- Environment overrides: `LLM_CATEGORISER_BATCH_SIZE`, `LLM_CATEGORISER_MAX_RETRIES`, `LLM_CATEGORISER_STATE_FILE`, provider-specific min interval vars (e.g., `GEMINI_MIN_REQUEST_INTERVAL`).

---

### Testing Strategy

- Create targeted tests in `tests/llm_categoriser/` covering loaders, batching, prompt generation, retry logic, persistence, state tracking, and CLI behaviour.
- Update provider tests to confirm min-interval enforcement and shared JSON parsing.

---

### Implementation Sequence

1. **Create `DocumentKey` model**: Add `src/models/document_key.py` with frozen dataclass; update `src/models/__init__.py` exports. ✅ DONE
2. **Unify `LanguageIssue` model**: Merge `LanguageIssue` and `LlmLanguageIssue` into a single Pydantic model in `src/models/language_issue.py`:
   - Include all fields from both models
   - Make LLM categorisation fields optional (default: None)
   - Add validation that if any LLM field is set, all must be set
   - Add `from_llm_response()` class method to parse LLM responses with `_from_tool` suffix fields
   - Re-export from `src/language_check/language_issue.py` for backward compatibility ✅ DONE
3. **Update CSV handling**: 
   - Modify `report_utils.py` to use `highlighted_context` instead of `context` in CSV output. ✅ DONE
4. **Update `.gitignore`**: Add entries for:
   - `data/llm_categoriser_state.json`
   - `data/batch_payloads/`
   - `Documents/*/document_reports/` ✅ DONE
5. **Extract JSON utilities**: Create `llm/json_utils.py` by extracting `GeminiLLM._parse_response_json()` functionality; refactor `GeminiLLM` to use shared utility; add unit tests. ✅ DONE
6. **Add rate limiting**: Extend providers with `min_request_interval` support and environment variable configuration. ✅ DONE
7. **Fix `render_prompt.py`**: Update to load both `llm_reviewer_system_prompt` and `authoritative_sources` partials. ✅ DONE
8. **Add Markdown table helper**: Implement `build_issue_batch_table(issues: list[LanguageIssue]) -> str` in `report_utils.py` (4 columns: issue_id, page_number, issue, highlighted_context). ✅ DONE
9. **Scaffold categoriser modules**: Create directory structure and empty modules with docstrings and contracts. ✅ DONE
10. **Implement modules with tests**: data_loader → batcher → prompt_factory → state → persistence → runner → CLI. ✅ DONE
11. **Integration testing**: Create `tests/llm_categoriser/` with fixtures; run `uv run pytest -q`. ✅ DONE
12. **Manual validation**: Use `--emit-batch-payload` to verify prompt structure and payload format. ✅ DONE
13. **Update documentation**: Finalise this README and update ARCHITECTURE.md. ✅ DONE

---

### Risks & Mitigations

- **Token Usage**: Control by limiting page context to referenced pages only. Even the largest full documents are around 30,000 tokens, so no explicit truncation needed initially. We'll cross that bridge if we come to it.
- **Deduplication**: Deduplicate CSV issues before batching to avoid redundant prompts; also deduplicate on persistence merge using (rule_id, highlighted_context) as unique key.
- **State Management**: Defer state updates until after successful writes to handle retries cleanly.
- **Manual Testing**: Offer `--emit-batch-payload` for troubleshooting provider issues.
- **Batch Size Edge Cases**: Handle single-issue batches and batches smaller than `batch_size` with standard logic.

---

### Documentation & Follow-up

- Keep this README aligned with any future changes to prompt structure or CLI options.
- State file format is documented in the "Core Modules & Responsibilities" section above.
- Future enhancement: optional importer for externally processed batch results.
- Single-threaded design rationale: This is a toy project using free-tier LLMs, so there's no point attempting concurrency. Rate limiting is handled per-request with provider-specific minimum intervals.

---

### Data Model Clarifications

**Unified LanguageIssue Model:**
- Combines detection fields (from LanguageTool) with optional LLM categorisation fields
- Core fields: `filename`, `rule_id`, `message`, `issue_type`, `replacements`, `highlighted_context`, `issue`, `page_number`, `issue_id`
- LLM categorisation fields (optional): `error_category`, `confidence_score`, `reasoning`
- Validation ensures if any LLM field is set, all three must be set
- `from_llm_response()` method handles LLM response format with `_from_tool` suffix fields
- Single source of truth in `src/models/language_issue.py`, re-exported from `src/language_check/language_issue.py` for backward compatibility

**CSV Structure:**
- Columns: Subject, Filename, Page, Rule ID, Type, Issue, Message, Suggestions, **Highlighted Context** (changed from Context)
- Empty Page column: indicates single-page document; submit entire document as context for all batches

**Markdown Table for LLM (simplified):**
- 4 columns only: `issue_id`, `page_number`, `issue`, `highlighted_context`
- Purpose: Keep token count controlled while providing essential information

---

This blueprint consolidates all agreed constraints and clarifications, including the document key model, issue tracking via `issue_id`, CSV updates, simplified table structure, state file format, JSON utilities extraction, rate limiting, British spelling, and single-threaded design rationale.