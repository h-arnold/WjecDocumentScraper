### Error Categories

- `PARSING_ERROR`: Mechanical/string issues (missing hyphen, merged words, stray spacing, words with similar shape to the misspelling e.g. `Oueen` instead of `Queen`, `vntil` instead of `until` or `ves` instead of `yes`.).
- `SPELLING_ERROR`: Incorrect spelling or wrong word form for the context, including incorrect regional spelling variants.
- `ABSOLUTE_GRAMMATICAL_ERROR`: Definitive grammar breach, i.e. one that is wrong in all standard English dialects.
- `POSSIBLE_AMBIGUOUS_GRAMMATICAL_ERROR`: Where the grammar may be correct in some standard English dialects but would be considered sloppy or poor practice for formal academic writing (e.g., split infinitives, ending sentences with prepositions, singular "they" in formal contexts).
- `STYLISTIC_PREFERENCE`: Stylistic suggestion where the original is acceptable.
- `FALSE_POSITIVE`: Tool misfire; terminology, proper nouns, code, or foreign words that are correct as written.

Always return the enum values exactly as written above (UPPER_SNAKE_CASE).

#### Notes on commas before conjunctions separating independent clauses

When LanguageTool suggests adding a comma before a conjunction (e.g., "and", "but", "or") that separates two independent clauses, note this as:

    - `STYLISTIC_PREFERENCE` if adding a comma wouldn't impact on flow or clarity.
    - `POSSIBLE_AMBIGUOUS_GRAMMATICAL_ERROR` if the adding a comma would improve flow but is not necessary for clarity.
    - `ABSOLUTE_GRAMMATICAL_ERROR` if the absence of a comma creates ambiguity or misleads the reader.