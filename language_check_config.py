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
    "PROBLEM_SOLVE_HYPHEN"
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
