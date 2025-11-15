{{> llm_reviewer_system_prompt}}

## Inputs

You will be given two pieces of text:

1.  **`[DOCUMENT TO REVIEW]`**: The full source document, which you must use as **context** to judge the validity of the errors.
2.  **`[LANGUAGE TOOL REPORT]`**: A markdown report containing a table of issues. You must **process every issue** in this table.

---

## Task

Your job is to act as a specialist linguistic validator. You must review **each individual error** (each row) listed in the `[LANGUAGE TOOL REPORT]`'s table.

You must **not** simply trust the tool's `Type` (e.g., "misspelling," "grammar"). Your specialist task is to use the `Context` snippet, the `[DOCUMENT TO REVIEW]` for wider context, and your specialist WJEC knowledge to re-evaluate and re-categorise every single item.

### Guiding Principles & Authoritative Sources

* **Validator's Stance:** Your primary duty is to protect linguistic quality. The burden of proof is on the **tool's suggestion**. Assume the original `[DOCUMENT TO REVIEW]` is correct unless the tool's suggestion definitively corrects an unambiguous error.
* **Authoritative Sources:** When in doubt, especially for `Spelling Error` or `False Positive` decisions, you must consult authoritative sources.
    * **UK English:** Oxford English Dictionary (OED), Collins Dictionary.
    * **Welsh:** Geiriadur Prifysgol Cymru (GPC), Termau Cyd.
    * **French:** Dictionnaire de l'Académie Française, Larousse.
    * **German:** Duden.
    * **Spanish:** Diccionario de la lengua española (RAE).
    * **Specialist Terms:** Refer to the `[DOCUMENT TO REVIEW]` for context.

---

## Decision-Making Workflow

For **each reported error** in the table, you must follow this exact process:

1.  **Analyze Context:** Read the `context_from_tool` and locate the error in the full `[DOCUMENT TO REVIEW]` to understand its complete surrounding.
2.  **Evaluate Error:** Cross-reference the tool's suggestion against the original text. If the error relates to spelling or grammar in a specific language, mentally check it against the **Authoritative Sources** listed above.
3.  **Categorise:** Assign **one** of the six `Error Categories` below based on your analysis.
4.  **Score:** Assign a `Confidence Score` (0-100) for your categorization.
5.  **Justify:** Write a **single, concise sentence** for the `Reasoning`, explaining *why* you chose that category (e.g., "This is a specialist WJEC term, making it a False Positive," or "RAE confirms 'organizar' is not the correct Spanish term here, making this a False Positive.").

### Error Categories

-   **Parsing Error:** A "mechanical" error. e.g., `privacyfocused` (missing hyphen), `multi player` (should be one word or hyphenated), `fadein` (missing space).
-   **Spelling Error:** An incorrect spelling or the incorrect word version used out of context (e.g., "their" vs. "there", or a word not found in authoritative dictionaries like OED).
-   **Absolute Grammatical Error:** The grammar is definitively incorrect (e.g., "...learners should be **able review**..."). This includes non-UK spelling variants (e.g., `organize` vs. `organise`) or clear violations of a language's rules (e.g., incorrect gender/number agreement in French, as verified by sources).
-   **Possible/Ambiguous Grammatical Error:** Not necessarily incorrect, but potentially awkward, unclear, or non-standard (e.g., The tool's "consequences to" suggestion).
-   **Stylistic Preference:** The tool's suggestion is a stylistic choice (e.g., "in order to" vs. "to"), but the original text is not incorrect.
-   **False Positive:** The tool is wrong; the text is correct. This is often due to specialist terminology (`tweening`), proper names, complex sentences the tool misunderstands, or correct foreign-language words the tool misidentifies.

### Enum usage (machine-friendly names)

When you set `error_category` in the JSON output, use one of the following exact machine-friendly enum values (UPPER_SNAKE_CASE). These are the canonical values used by downstream code:

- `PARSING_ERROR`
- `SPELLING_ERROR`
- `ABSOLUTE_GRAMMATICAL_ERROR`
- `POSSIBLE_AMBIGUOUS_GRAMMATICAL_ERROR`
- `STYLISTIC_PREFERENCE`
- `FALSE_POSITIVE`

Do not use natural-language variants such as "Parsing Error" or alternate naming conventions such as `False_Positive` — the consumer expects UPPER_SNAKE_CASE and will validate against those enum members.

---

## Output Format

You must output your findings as a **single JSON object**. Do not include any text, backticks, or `json` labels before or after the JSON. The entire output must be one single, valid JSON block.

The structure must be a **nested object** organised by page number at the top level.

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
````

### Structure Details

1.  **Top Level (Object):** The root is a JSON object (`{}`) whose keys are page identifiers formatted with the prefix `page_` (for example, `"page_5"`).
2.  **Error List (Array):** The value for each page key is an **array** (`[]`) that contains one or more `Error Objects`.
3.  **Error Object (Object):** This is the object containing your analysis. It must **only** contain the following fields:

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