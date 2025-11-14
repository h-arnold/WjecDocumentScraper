"""Configuration for language checking rules and ignored words.

This module defines the default rules to disable and words to ignore
when running language quality checks on technical documents.
"""

# Default rules to disable (can be overridden via command-line arguments)
DEFAULT_DISABLED_RULES = {
    "WHITESPACE_RULE",
    "CONSECUTIVE_SPACES",
    "SENTENCE_WHITESPACE",
    "OXFORD_SPELLING_Z_NOT_S",
    "UPPERCASE_SENTENCE_START",
    "HYPHEN_TO_EN",
    "COMMA_PARENTHESIS_WHITESPACE",
    "PROBLEM_SOLVE_HYPHEN",
    "UP_TO_DATE_HYPHEN",
    "PHRASE_REPETITION",
    "IN_A_X_MANNER",
    "DECISION_MAKING",
    "EN_UNPAIRED_BRACKETS",
    "ENGLISH_WORD_REPEAT_BEGINNING_RULE",
    "DASH_RULE",
    "ADMIT_ENJOY_VB"


}


# Default words to ignore (case-sensitive; can be extended via command-line)
# The set below intentionally preserves casing because many entries are
# case-specific (e.g. organisation names, acronyms, product names).
DEFAULT_IGNORED_WORDS = {
}