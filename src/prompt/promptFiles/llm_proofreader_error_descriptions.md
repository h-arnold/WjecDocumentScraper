### Error Categories

- `SPELLING_ERROR`: The token is not a valid word in the dictionary for the target dialect. For English, always use British English spelling and conventions.
    - **Examples:** `Malcom X` (should be Malcolm), `warravaged` (missing hyphen), `definately`.
- `ABSOLUTE_GRAMMATICAL_ERROR`: An objective breach of syntax rules - wrong in all contexts.
    - **Examples:** Missing prepositions (`collective highly qualified authors`), extra words (`quantity and of goods`), or capitalisation errors (`therefore, That...`).
- `CONSISTENCY_ERROR`: The usage is valid in isolation but contradicts patterns established elsewhere.
    - **Examples:** Mixing `war communism` and `war Communism`, or spelling it `Malcom X` in a question when the source text says `Malcolm X`.
    - **Examples:** `due to the fact that` (prefer `because`), `in order to` (prefer `to`).
- `AMBIGUOUS_PHRASING`: The text is grammatically valid but the syntax creates confusion (e.g., dangling modifiers).
    - **Examples:** `Faced with the potential of radical elements, the demands were met...` (Implies the 'demands' were facing the elements, not the government).
- `STYLISTIC_PREFERENCE`: Stylistic suggestion where the original is awkward, confusing, or unprofessional.
    - **Restriction:** Do NOT use this for simple preference variations (e.g., changing "how we assess" to "assessment methodology"). Only flag if the current phrasing actively hinders comprehension or tone.
- `FACTUAL_INACCURACY`: Objectively false statement or terminology.
    - **Examples:** Referring to Lenin's `April Theses` as the `April Thesis`.

Always return the enum values exactly as written above (UPPER_SNAKE_CASE).
