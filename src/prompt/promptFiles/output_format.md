## Output Format

Return a **single top-level JSON array** (no surrounding object, no page keys) and nothing else. Do not include backticks, commentary, or any text before or after the JSON. Each array element represents one issue from the table.

For each issue, return exactly the following fields and nothing more:

- `issue_id`: integer — the issue identifier from the input CSV (auto-increment per-document)
- `error_category`: one of the enum values listed in "Error Categories" above (e.g., `SPELLING_ERROR`)
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