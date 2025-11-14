---
description: 'False positive '
tools: ['runCommands', 'runTasks', 'edit', 'search', 'todos', 'think', 'changes']
---

  ## Purpose

  This prompt defines a strict, repeatable workflow for curating genuinely-correct tokens (false positives) for inclusion in `DEFAULT_IGNORED_WORDS` using the `scripts/manage_language_ignore.py` tool. The goal is high precision: only fully-verified, canonical forms are added.

  ## Scope & Inputs

  - Input: a CSV (or plain list) of candidate tokens, processed sequentially in 30-line batches.
  - Languages: primary English; Welsh and subject-specific domain terms allowed but must be orthographically correct.
  - Output: one or more JSON manifests (per subject) that conform to the script's expected schema and use canonical categories.

  ## Canonical Categories (use these exact names)

  - REJECT: Anything that is incorrect. This should be your default assumption.
  - Proper Noun — capitalised names of people, places, organisations. Diacritics must be present when required.
  - Technical Term — subject-specific terminology or jargon (lowercase unless the term is normally capitalised).
  - Initialism/Acronym — acronyms and initialisms (typically ALL CAPS; preserve conventional punctuation only when idiomatic).
  - Other — valid non-English or otherwise correct words that do not fit the above (e.g., Welsh words, loanwords).

  Note: map any informal label to one of the canonical names above before producing JSON.

  ## Quality Standards (non-negotiable)

  - Spelling must be perfect. If in doubt, mark as REJECT or AMBIGUOUS and escalate—do not add. This includes non-British spellings of words.
  - Proper nouns must be correctly capitalised and accented where appropriate.
  - Allowed characters: letters, digits, spaces, hyphens (`-`), periods (`.`), apostrophes (`'`). No leading/trailing whitespace.
  - No possessive forms (e.g., `teacher's`) and avoid variants (prefer canonical dictionary form).
  - Do not add plural-only or alternate inflections unless the spec requires them.
  - Follow the repository invariant: subject names must match keys in `src/scraper/__init__.py` (case-insensitive mapping allowed).

  ## Decision Workflow (apply in order for each token)

  1. Normalize: trim and preserve internal punctuation. Do not auto-correct casing.
  2. Skip if already present in `DEFAULT_IGNORED_WORDS` (report as skipped).
  3. Validate characters against allowed set; if invalid → REJECT.
  4. If spelling or form is uncertain (accent, casing, punctuation) → AMBIGUOUS (do not add; request clarification).

  Always include a one-line rationale for each classification (source or rule used).

  ## Batch Processing Protocol (30-line batches)

  For each batch of up to 30 tokens (sequential order):

  1. Classify each token and add a one-line rationale (e.g., "Proper Noun — appears as person name in syllabus").
  2. Produce a summary: counts per category, rejected, ambiguous.
  3. Produce a proposed JSON manifest using canonical categories.
  4. Present the batch summary + proposed JSON to the user and request explicit confirmation.
  5. On explicit confirmation, run the script to apply the JSON manifest:

  ```bash
  uv run python scripts/manage_language_ignore.py data/language-ignore/<subject>.json
  ```

  Pause if >40% of the batch is AMBIGUOUS and request guidance.

  Repeat steps 1–6 for subsequent batches until you reach the end of the input CSV/list. Process sequentially; do not skip ahead or parallelise batches.

  ## JSON Manifest Schema (example)

  ```json
  [
    {
      "subject": "History",
      "words": [
        {"word": "Cynan", "category": "Proper Noun"},
        {"word": "motte", "category": "Technical Term"},
        {"word": "GCSE", "category": "Initialism/Acronym"},
        {"word": "ysgol", "category": "Other"}
      ]
    }
  ]
  ```

  Rules:
  - Category must be one of the canonical names above.
  - Words must not exceed current maximum length in `DEFAULT_IGNORED_WORDS` unless you explicitly update the config first.
  - No duplicates within the same subject manifest.

## How to craft the JSON file & apply it (practical steps)

1. Choose a subject that matches a key in `src/scraper/__init__.py` (case-insensitive). Use this as the `subject` field in the manifest.
2. Create a file under `data/language-ignore/`, e.g. `data/language-ignore/history.json` (filename should indicate the subject for traceability).
3. Assemble the manifest using the JSON schema above. Example minimal file:

```json
[{
  "subject": "History",
  "words": [
    {"word": "Cynan", "category": "Proper Noun"},
    {"word": "motte", "category": "Technical Term"}
  ]
}]
```

4. Validate locally by running a dry-run first (this shows what would be inserted without changing files):

```bash
uv run python scripts/manage_language_ignore.py data/language-ignore/history.json --dry-run
```

5. Inspect the dry-run output carefully. If corrections are needed, edit the JSON and repeat step 4.
6. When satisfied, apply the changes (this updates the `DEFAULT_IGNORED_WORDS` config):

```bash
uv run python scripts/manage_language_ignore.py data/language-ignore/history.json
```

7. Record the applied filename, timestamp, and counts in your audit log (append to a CSV or other log file).

Notes:
- The script will skip duplicates automatically, but keep manifests small and focused per subject.
- If you need to raise the maximum allowed word length, update the config first (see repo docs) before applying.

  ## Examples (for reviewer training)

  Positive (accept):
  - "Cynan" → Proper Noun
  - "motte" → Technical Term
  - "GCSE" → Initialism/Acronym
  - "ysgol" → Other (Welsh)

  Negative (reject):
  - "mispellings" (typo)
  - "Intiailisms" (typo)
  - "histroy" (typo)
  - "garcia" (missing accent; should be "García")
  - "G.C.S.E" (incorrect punctuation for this repo habit)
  - "glutenfree" (word should be separated or hyphenated)

  Ambiguous (flag, do not add):
  - Tokens with uncertain diacritics
  - Tokens where casing is inconsistent with authoritative sources

  ## Edge Cases & Handling

  - Possessives and punctuation: do not add.
  - Hyphenation: accept only documented forms (e.g., "double-award" if present in spec).
  - Numbered terms and formulas: verify canonical representation (e.g., "CO2" not "CO²").
  - Plurals: avoid unless the domain specifically uses plural as a stable lexeme.

  ## Interaction & Confirmation

  - Present classification + proposed JSON and request explicit user confirmation.
  - After confirmation, run the `uv` command above to update the config.

  ## Operational Notes

  - Work sequentially: do not parallelise review or script runs—this preserves context and avoids accidental double-applications.
  - Be conservative: false positives hurt less than false inclusions—prefer rejecting/flagging uncertain tokens.
  - Only pause for the user to confirm the spellings categorisations. Otherwise, keep working.

Please begin the process outlined above.