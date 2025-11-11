{{> llm_reviewer_system_prompt}}

---

## Inputs

You will be given two pieces of text:

1.  **`[DOCUMENT TO REVIEW]`**: The full source document, which you must use as **context** to judge the validity of the errors.
2.  **`[LANGUAGE TOOL REPORT]`**: A markdown report containing a table of issues. You must **process every issue** in this table.

---

## Task

Your job is to review **each individual error** (each row) listed in the `[LANGUAGE TOOL REPORT]`'s table.

You must **not** simply trust the tool's `Type` (e.g., "misspelling," "grammar"). Your specialist task is to use the `Context` snippet, the `[DOCUMENT TO REVIEW]` for wider context, and your specialist WJEC knowledge to re-evaluate and re-categorise every single item.

For **each reported error**, you must:

1.  **Assign it** to one of the following six categories.
2.  **Provide a Confidence Score** (0-100) for your categorization.
3.  **Write a brief Reasoning** explaining your choice. **This must be limited to a single, concise sentence.**

### Error Categories

- **Parsing Error:** A "mechanical" error. e.g., `privacyfocused` (missing hyphen), `multi player` (should be one word or hyphenated), `fadein` (missing space).
- **Spelling Error:** An incorrect spelling or the incorrect word version used out of context (e.g., "their" vs. "there").
- **Absolute Grammatical Error:** The grammar is definitively incorrect (e.g., "...learners should be **able review**..."). This includes non-UK spelling variants (e.g., `organize` vs. `organise`).
- **Possible/Ambiguous Grammatical Error:** Not necessarily incorrect, but potentially awkward, unclear, or non-standard (e.g., The tool's "consequences to" suggestion).
- **Stylistic Preference:** The tool's suggestion is a stylistic choice, but the original text is not incorrect.
- **False Positive:** The tool is wrong; the text is correct. This is often due to specialist terminology (`tweening`), proper names, or complex sentences the tool misunderstands.

## Output Format

You must output your findings as a **single JSON object**. Do not include any text, backticks, or `json` labels before or after the JSON. The entire output must be one single, valid JSON block.

The structure must be a **nested object** organised by page number at the top level, with filenames nested under each page.

**Structure Example:**

```json
{
  "page_5": [
    { ...error_object_1... },
    { ...error_object_2... }
  ],
  "page_7": [
    { ...error_object_3... }
  ],
  "page_19": [
    { ...error_object_4... }
  ]
}
```

### Structure Details

1.  **Top Level (Object):** The root is a JSON object (`{}`) whose keys are page identifiers formatted with the prefix `page_` (for example, `"page_5"`).
2.  **Page Keys (Object):** Each top-level page key maps to an object containing one or more filename keys.
3.  **Error List (Array):** The value for each filename key is an **array** (`[]`) that contains one or more `Error Objects`.
4.  **Error Object (Object):** This is the object containing your analysis. It must **only** contain the following fields:

<!-- end list -->

```json
{
  "rule_from_tool": "...",
  "type_from_tool": "...",
  "message_from_tool": "...",
  "suggestions_from_tool": "...",
  "context_from_tool": "...",
  "error_category": "...",
  "confidence_score": 0,
  "reasoning": "..."
}
```
