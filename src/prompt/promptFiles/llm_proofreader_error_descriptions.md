### Error Categories

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
- `FACTUAL_INACCURACY`: Objectively false statement or terminology.
    - **Examples:** Referring to Lenin's `April Theses` as the `April Thesis`.

Always return the enum values exactly as written above (UPPER_SNAKE_CASE).

#### Rules for Commas before Conjunctions (and, but, or)

Classify comma issues between independent clauses using the following hierarchy:

1.  **`ABSOLUTE_GRAMMATICAL_ERROR`**: Use this if the text contains a **comma splice** (two independent clauses joined only by a comma without a conjunction) or a **run-on sentence** (two independent clauses joined with no punctuation).
2.  **`AMBIGUOUS_PHRASING`**: Use this if the absence (or presence) of the comma causes the subject of the second clause to be misidentified.