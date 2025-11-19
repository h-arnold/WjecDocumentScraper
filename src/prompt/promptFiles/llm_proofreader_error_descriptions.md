### Error Categories

- `SPELLING_ERROR`: Incorrect spelling or wrong word form for the context, including incorrect regional spelling variants.
    - **Examples:** `definately` instead of `definitely`, `organise` instead of `organize` in American English context, `affect` instead of `effect`.
- `CONTEXTUAL_SPELLING: `: Valid words used incorrectly (homophones, wrong word).
    - **Examples:** `their` vs `there`, `assess` vs `access`, `leaners` vs `learners`.
- `ABSOLUTE_GRAMMATICAL_ERROR`: Definite grammar breach (agreement, tense, article/preposition misuse, apostrophe misuse) not attributable to style.
- `POSSIBLE_AMBIGUOUS_GRAMMATICAL_ERROR`: Grammatically debatable or awkward; improvement advisable but optional. Might be considered 'sloppy' for formal writing.
- `STYLISTIC_PREFERENCE`: Stylistic suggestion where the original is acceptable.
- `CONSISTENCY_ERROR`: Valid in isolation but inconsistent with the rest of the document.
    - **Examples:** Mixing `web site` and `website`, inconsistent capitalisation in headers or bullet points, inconsistent use of initialisms (e.g., `UK` vs `U.K.`).
- `AMBIGUOUS_PHRASING`: Grammatically correct but confusing, clusmy or unclear in meaning. This is particularly important for areas where precision is critical e.g. terminology definitions, assessment criteria.


Always return the enum values exactly as written above (UPPER_SNAKE_CASE).

#### Notes on commas before conjunctions separating independent clauses

When LanguageTool suggests adding a comma before a conjunction (e.g., "and", "but", "or") that separates two independent clauses, note this as:

    - `STYLISTIC_PREFERENCE` if adding a comma wouldn't impact on flow or clarity.
    - `POSSIBLE_AMBIGUOUS_GRAMMATICAL_ERROR` if the adding a comma would improve flow but is not necessary for clarity.
    - `ABSOLUTE_GRAMMATICAL_ERROR` if the absence of a comma creates ambiguity or misleads the reader.