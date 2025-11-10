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
    "DECISION_MAKING"


}

# Default words to ignore (case-sensitive; can be extended via command-line)
# The set below intentionally preserves casing because many entries are
# case-specific (e.g. organisation names, acronyms, product names).
DEFAULT_IGNORED_WORDS = {
    # prominent names / proper nouns
    "WJEC",
    "CBAC",
    "Fitzalan",
    "Llanwern",
    "GCSE",
    "tkinter",

    # hardware / acronyms
    "CPU",
    "GPU",
    "RAM",
    "NIC",
    "NICs",
    "HDD",
    "SSD",
    "SD",
    "SDS",
    "DVD",
    "PC",
    "SCSI",
    "USB",
    "HDMI",
    "RCA",

    # networking / bandwidth
    "LAN",
    "WAN",
    "Ethernet",
    "Wi-Fi",
    "kbps",
    "mbps",
    "gbps",
    "bps",
    "MiTM",
    "MITM",

    # audio / connectors / formats
    "SPDIF",
    "S/PDIF",
    "TOSLINK",

    # core / cpu descriptors
    "quad-core",
    "hexa-core",
    "octa-core",
    "deca-core",

    # image / bit-depth / throughput
    "BPC",
    "BPP",
    "bits-per-channel",
    "bit-depth",

    # hyphen / multi-word variants
    "multitasking",
    "multi-tasking",
    "high-speed",

    # misc
    "white-hat",
    "whitehat",
    "nano",
}

# Additional words observed in the language-check report that are valid
# terms or proper nouns for WJEC documents. These are case-sensitive
# entries because the spellchecker configuration preserves casing.
ADDITIONAL_IGNORED = {
    # Welsh / domain-specific
    "cynefin",
    "Cynefin",

    # Education / resource names
    "Bitesize",
    "Eduqas",

    # Museums / organisations and acronyms seen in reports
    "MoMA",
    "MOMA",
    "Mostyn",
    "Presteigne",
    "UWTSD",
    "NSEAD",

    # People / names encountered
    "Lubaina",
    "Himid",
    "Yinka",
    "Shonibare",

    # Other acronyms and subject-specific tokens
    "CWRE",
    "AOs",
    "SAMs",
    "SAM",

    # Vendor / product names
    "kitronik",
    "Kitronik",

    # Place names, people and tokens seen in language-check reports
    # (added as case-sensitive entries to avoid masking real errors)
    "Machynlleth",
    "Hwb",
    "Cynon",
    "Piech",
    "Bracewell",
    "Heatherwick",
    "Kéré",
    "Tregwynt",
    "Melin",
    "Haf",
    "Weighton",
    "Blant",
    "Byd",
    "Fairey",
    "Hickman",
    "Delita",
    "Rego",
    "Ekta",
    "Kaul",
    "Adfer",
    "Felin",
    "Fons",
}

# Merge the additional set into the main default set
DEFAULT_IGNORED_WORDS.update(ADDITIONAL_IGNORED)

# Additional false positives observed in recent language-check reports
# (added here so the checker won't flag common technical tokens, acronyms,
# file-format labels and multi-word product/term forms used in WJEC docs).
MORE_IGNORED = {
    # release / build terms
    "prerelease",
    "pre-release",

    # security / cyber terms (variants seen in reports)
    "DoS",
    "DOS",
    "cybersecurity",
    "cyber security",
    "cyberattacks",
    "cyber attacks",
    "cyberattack",
    "cyber attack",

    # UK term seen in docs
    "Centres",

    # website / multipage variants
    "multipage",
    "multi-page",
    "multi page",

    # common long-form / product names
    "HyperText Markup Language",
    "Hypertext Markup Language",

    # tools / acronyms / UI terms
    "HUDs",
    "rotoscoping",
    "tweening",
    "AutoFilter",

    # spreadsheet functions / tokens (uppercase as in docs)
    "COUNTA",
    "IF",
    "VLOOKUP",
    "HLOOKUP",
    "COUNTIF",
    "SUMIF",
    "AVERAGEIF",
    "SORTBY",
    "UNIQUE",
    "SORT",

    # layout / CSS / game terms
    "flexbox",
    "Flexbox",
    "multi-player",
    "multiplayer",

    # file extensions / media formats (upper+lower seen in reports)
    "PNG",
    "JPEG",
    "SVG",
    "PDF",
    "MP4",
    "AVI",
    "MOV",
    "mp4",
    "avi",
    "mov",
    "png",
    "jpeg",
    "svg",

    # animation / video terms
    "keyframing",
    "key framing",
}

# Merge these additional observed tokens in as well
DEFAULT_IGNORED_WORDS.update(MORE_IGNORED)

# Welsh words frequently seen in WJEC documents; add both common case variants
# and hyphenated forms found in the language report so the checker won't flag them.
DEFAULT_IGNORED_WELSH = {
    # acronyms / subject name
    "TGAU",

    # hyphenated / title strings
    "Gwneud-i-Gymru",

    # general Welsh words / proper nouns
    "Dysgu",
    "Proffesiynol",
    "proffesiynol",
    "Canolfan",
    "Bedwyr",
    "Termiadur",
    "Addysg",

    # scientific terminology examples seen in docs
    "cyflymder",
    "Cyflymder",
    "Buanedd",
    "buanedd",
    "felosedd",
    "Felosedd",
}

# Merge Welsh ignore words into the main default set (preserves case-sensitivity)
DEFAULT_IGNORED_WORDS.update(DEFAULT_IGNORED_WELSH)
