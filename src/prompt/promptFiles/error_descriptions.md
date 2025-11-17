### Error Categories

- `PARSING_ERROR`: Errors likely caused by the conversion from PDF to markdown.
    - **Examples:** missing hyphens, merged words, stray spacing, words with similar shape to the misspelling e.g. `Oueen` instead of `Queen`, `vntil` instead of `until` or `ves` instead of `yes`.
- `SPELLING_ERROR`: Incorrect spelling or wrong word form for the context, including incorrect regional spelling variants.
    - **Examples:** `definately` instead of `definitely`, `organise` instead of `organize` in American English context, `affect` instead of `effect`.
- `ABSOLUTE_GRAMMATICAL_ERROR`: Definite grammar breach (agreement, tense, article/preposition misuse, apostrophe misuse) not attributable to style.
- `POSSIBLE_AMBIGUOUS_GRAMMATICAL_ERROR`: Grammatically debatable or awkward; improvement advisable but optional. Might be considered 'sloppy' for formal writing.
- `STYLISTIC_PREFERENCE`: Stylistic suggestion where the original is acceptable.
- `FALSE_POSITIVE`: Tool misfire; terminology, proper nouns, code, or foreign words that are correct as written.

Always return the enum values exactly as written above (UPPER_SNAKE_CASE).

#### Notes on commas before conjunctions separating independent clauses

When LanguageTool suggests adding a comma before a conjunction (e.g., "and", "but", "or") that separates two independent clauses, note this as:

    - `STYLISTIC_PREFERENCE` if adding a comma wouldn't impact on flow or clarity.
    - `POSSIBLE_AMBIGUOUS_GRAMMATICAL_ERROR` if the adding a comma would improve flow but is not necessary for clarity.
    - `ABSOLUTE_GRAMMATICAL_ERROR` if the absence of a comma creates ambiguity or misleads the reader.