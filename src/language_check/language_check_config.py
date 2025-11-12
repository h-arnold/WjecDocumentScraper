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
    "DASH_RULE"


}


# Default words to ignore (case-sensitive; can be extended via command-line)
# The set below intentionally preserves casing because many entries are
# case-specific (e.g. organisation names, acronyms, product names).
DEFAULT_IGNORED_WORDS = {
    # --- Prominent names / proper nouns ---
    "WJEC", "CBAC", "Fitzalan", "Llanwern", "GCSE", "tkinter",

    # --- Hardware / acronyms ---
    "CPU", "GPU", "RAM", "NIC", "NICs", "HDD", "SSD", "SD", "SDS", "DVD", "PC", "SCSI", "USB", "HDMI", "RCA",

    # --- Networking / bandwidth ---
    "LAN", "WAN", "Ethernet", "Wi-Fi", "kbps", "mbps", "gbps", "bps", "MiTM", "MITM",

    # --- Audio / connectors / formats ---
    "SPDIF", "S/PDIF", "TOSLINK",

    # --- Core / CPU descriptors ---
    "quad-core", "hexa-core", "octa-core", "deca-core",

    # --- Image / bit-depth / throughput ---
    "BPC", "BPP", "bits-per-channel", "bit-depth",

    # --- Hyphen / multi-word variants ---
    "multitasking", "multi-tasking", "high-speed",

    # --- Misc ---
    "white-hat", "whitehat", "nano",

    # --- Welsh / domain-specific ---
    "cynefin", "Cynefin",

    # --- Education / resource names ---
    "Bitesize", "Eduqas",

    # --- Museums / organisations and acronyms seen in reports ---
    "MoMA", "MOMA", "Mostyn", "Presteigne", "UWTSD", "NSEAD",

    # --- People / names encountered ---
    "Lubaina", "Himid", "Yinka", "Shonibare",

    # --- Dance subject proper nouns and technical terms (added from report) ---
    "Rygbi", "Annwyl", "Fearghus", "Conchúir", "ZooNation", "Avant", "Garde", "Chor", "Adigun", "Vardimon", "Xin", "Boyz", "Motionhouse", "ronde", "jambe", "ABACADA", "choreographics",

    # --- Other acronyms and subject-specific tokens ---
    "CWRE", "AOs", "SAMs", "SAM",

    # --- Vendor / product names ---
    "kitronik", "Kitronik",

    # --- Place names, people and tokens seen in language-check reports ---
    "Machynlleth", "Hwb", "Cynon", "Piech", "Bracewell", "Heatherwick", "Kéré", "Tregwynt", "Melin", "Haf", "Weighton", "Blant", "Byd", "Fairey", "Hickman", "Delita", "Rego", "Ekta", "Kaul", "Adfer", "Felin", "Fons",

    # --- Release / build terms ---
    "prerelease", "pre-release",

    # --- Security / cyber terms (variants seen in reports) ---
    "DoS", "DOS", "cybersecurity", "cyber security", "cyberattacks", "cyber attacks", "cyberattack", "cyber attack",

    # --- UK term seen in docs ---
    "Centres",

    # --- Website / multipage variants ---
    "multipage", "multi-page", "multi page",

    # --- Common long-form / product names ---
    "HyperText Markup Language", "Hypertext Markup Language",

    # --- Tools / acronyms / UI terms ---
    "HUDs", "rotoscoping", "tweening", "AutoFilter",

    # --- Spreadsheet functions / tokens (uppercase as in docs) ---
    "COUNTA", "IF", "VLOOKUP", "HLOOKUP", "COUNTIF", "SUMIF", "AVERAGEIF", "SORTBY", "UNIQUE", "SORT",

    # --- Layout / CSS / game terms ---
    "flexbox", "Flexbox", "multi-player", "multiplayer",

    # --- File extensions / media formats (upper+lower seen in reports) ---
    "PNG", "JPEG", "SVG", "PDF", "MP4", "AVI", "MOV", "mp4", "avi", "mov", "png", "jpeg", "svg",

    # --- Animation / video terms ---
    "keyframing", "key framing",

    # --- People / names / proper nouns seen in Business docs ---
    "Elkington",

    # --- Internal resource / acronym forms seen in reports ---
    "GfT", "NEA", "NEAs", "IAMIS",

    # --- Organisations / program names ---
    "Technocamps", "ActionAid", "GlobalWelsh",

    # --- Subject / curriculum tokens ---
    "AoLE", "BAME",

    # --- Brands / product names used in documents ---
    "GymShark", "McDonalds",

    # --- Service / platform tokens flagged but valid in docs ---
    "YouTube",

    # --- Place names and local variants (add common forms) ---
    "Merthyr Tydfil",

    # --- Common editorial token from reports ---
    "fayre",

    # --- Welsh: acronyms / subject name ---
    "TGAU",

    # --- Welsh: hyphenated / title strings ---
    "Gwneud-i-Gymru",

    # --- Welsh: general Welsh words / proper nouns ---
    "Dysgu", "Proffesiynol", "proffesiynol", "Canolfan", "Bedwyr", "Termiadur", "Addysg",

    # --- Welsh: scientific terminology examples seen in docs ---
    "cyflymder", "Cyflymder", "Buanedd", "buanedd", "felosedd", "Felosedd",

    # --- Additional validated names and technical tokens discovered in
    #     recent language-check reports. These are correct terms or proper
    #     nouns that should not be flagged as misspellings or style issues.
    # Art & design: artists, designers and common proper nouns
    "Gauguin", "Paul Gauguin", "Herbert Bayer", "Amy Sherald", "Bridget Riley", "Banksy",
    "Salvador Dalí", "Salvador Dali", "Dali", "Paul Peter Piech",

    # Layout / UI / design terms and variants
    "Wayfinding", "mock-ups", "mockups", "mock ups",
    "two-dimensional", "three-dimensional", "2-dimensional",

    # Sport / disability sport terms seen in specs
    "Powerchair", "Powerchair Football",

    # Photography / film / animation terms seen in reports
    "time-lapse", "rotoscoping", "tweening",
}