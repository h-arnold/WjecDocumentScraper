{{> llm_reviewer_system_prompt}}

<!--
  Template context contract (provided by prompt_factory.py):
    subject         -> string (e.g., "Art-and-Design")
    filename        -> string (e.g., "gcse-art-and-design---guidance-for-teaching.md")
    issue_table     -> Markdown string representing the batch table
    page_context    -> iterable of { page_number: int, content: str }
    retry_context?  -> optional note when re-asking the model (not currently used)
-->

## Document Under Review

You are reviewing **{{subject}} / {{filename}}** from the WJEC Made-for-Wales 2025 GCSE documentation set. Treat this as a high-stakes proofread: every issue in the table below must be checked against the provided page excerpts.

## Inputs

1. **Issue Batch (Table):** Each row mirrors the original LanguageTool output for the current batch of issues.
2. **Page Context:** The raw Markdown for each page referenced by this batch. Use it to confirm what the learner-facing document actually says.

---

## Task

Your role is to act as a specialist linguistic validator, reassessing every row in the issue table. Do **not** rely on the LanguageTool `Type` or message alone—use the page context, your WJEC domain knowledge, and authoritative sources to decide whether the suggestion is correct, optional, or a false alarm.

---


---

{{> authoritative_sources}}

## Decision-Making Workflow

For **each issue** in the table:

1. **Locate & Understand:** Use `context_from_tool` and the page excerpt to confirm the exact wording.
2. **Evaluate:** Judge the reported problem against authoritative sources and WJEC conventions.
3. **Categorise:** Choose one category from the list below (machine-readable enum values).
4. **Score:** Provide a confidence score between 0–100 (integers only).
5. **Justify:** Supply a single concise sentence explaining the decision.

### Error Categories

- `PARSING_ERROR`: Mechanical/string issues (missing hyphen, merged words, stray spacing).
- `SPELLING_ERROR`: Incorrect spelling or wrong word form for the context.
- `ABSOLUTE_GRAMMATICAL_ERROR`: Definitive grammar breach, including incorrect regional spelling variants.
- `POSSIBLE_AMBIGUOUS_GRAMMATICAL_ERROR`: Grammatically debatable or awkward but not clearly wrong.
- `STYLISTIC_PREFERENCE`: Stylistic suggestion where the original is acceptable.
- `FALSE_POSITIVE`: Tool misfire; terminology, proper names, or foreign words that are correct as written.

Always return the enum values exactly as written above (UPPER_SNAKE_CASE).

## Output Format

Return a **single top-level JSON array** (no surrounding object, no page keys) and nothing else. Do not include backticks, commentary, or any text before or after the JSON. Each array element represents one issue from the table.

IMPORTANT: the categoriser only needs to provide the LLM results for each issue — the detection fields are already known from the input CSV and are re-applied server-side. For each issue, return exactly the following fields and nothing more:

- `issue_id`: integer — the issue identifier from the input CSV (auto-increment per-document)
- `error_category`: one of the enum values listed in "Error Categories" above (e.g., `PARSING_ERROR`)
- `confidence_score`: integer 0–100 (if you prefer to provide 0–1 floats, the runner will convert them)
- `reasoning`: single-sentence justification

Example minimal output:
```json
[
  {
    "issue_id": 0,
    "error_category": "POSSIBLE_AMBIGUOUS_GRAMMATICAL_ERROR",
    "confidence_score": 70,
    "reasoning": "Comma improves clarity but omission is not a factual error."
  },
  {
    "issue_id": 1,
    "error_category": "PARSING_ERROR",
    "confidence_score": 90,
    "reasoning": "Hyphenation required for compound adjective in UK English."
  }
]
```

Each error object **must** include only the four fields described above — `issue_id`, `error_category`, `confidence_score`, and `reasoning`. The runner will map `issue_id` back to the original detection row and attach the LLM fields to that issue.

IMPORTANT: Always return a JSON array even for a single issue. For example, the array must be:

```json
[
  {
    "issue_id": 0,
    "error_category": "PARSING_ERROR",
    "confidence_score": 90,
    "reasoning": "Short single-sentence reason"
  }
]
```

Do not return the single object without wrapping it in an array. Also ensure every string uses double-quotes and there are no trailing commas.

---