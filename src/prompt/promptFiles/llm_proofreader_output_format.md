## Output Format

All spelling and grammar rules must be based on British English.

Return a **single top-level JSON array** (no surrounding object, no page keys) and nothing else. Do not include backticks, commentary, or any text before or after the JSON. Each array element represents one issue from the table.

For each issue, output a full object following the format below:

- `issue`: The specific word or short phrase containing the error.
- `page_number`: The page number where the issue is located from your context.
- `highlighted_context`: The sentence containing the error (plus the preceding and succeeding sentence, if necessary for clarity) with the error highlighted using double asterisks `**` before and after the error.
- `error_category`: one of the enum values listed in "Error Categories" above (e.g., `SPELLING_ERROR`)
- `confidence_score`: integer 0–100 (if you prefer to provide 0–1 floats, the runner will convert them)
- `reasoning`: single-sentence justification

### Example Output

```json
[
  {
    "issue": "loose",
    "highlighted_context": "The students **loose** several marks for poor grammar.",
    "error_category": "SPELLING_ERROR",
    "confidence_score": 95,
    "reasoning": "Common misspelling of 'lose' in this context."
  },
  {
    "issue": "well-run",
    "highlighted_context": "This was a **well-run** event that concluded smoothly.",
    "error_category": "STYLISTIC_PREFERENCE",
    "confidence_score": 88,
    "reasoning": "Compound adjective requires hyphenation in UK English when used before a noun."
  }
]
```


Each error object **must** include **all and only** the fields above.

IMPORTANT: Always return a JSON array even for a single issue.

Do not return the single object without wrapping it in an array. Also ensure every string uses double-quotes and there are no trailing commas.