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
    # --- Prominent names / proper nouns ---
    "WJEC", "CBAC", "Fitzalan", "Llanwern", "GCSE", "tkinter", "TKINTER",

    # --- Hardware / acronyms ---
    "CPU", "GPU", "RAM", "NIC", "NICs", "HDD", "SSD", "SD", "DVD", "PC", "SCSI", "USB", "HDMI", "RCA",

    # --- Networking / bandwidth ---
    "LAN", "WAN", "Ethernet", "Wi-Fi", "kbps", "mbps", "gbps", "bps", "MITM",

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
    "Rygbi", "Annwyl", "Fearghus", "Conchúir", "Conchuir", "ZooNation", "Avant-Garde", "Chor", "Chór", "Adigun", "Vardimon", "Xin", "Boyz", "Motionhouse", "rond de jambe", "jambe", "ABACADA",

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
    "GymShark", "McDonald's",

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
    "Salvador Dalí", "Dali", "Paul Peter Piech",

    # Layout / UI / design terms and variants
    "Wayfinding", "mockups",
    "two-dimensional", "three-dimensional",

    # Sport / disability sport terms seen in specs
    "Powerchair", "Powerchair Football",

    # Photography / film / animation terms seen in reports
    "time-lapse",

    # --- French words / common French tokens (flagged by MORFOLOGIK) ---
    "acheter", "adorer", "aimer", "allais", "avec", "bien", "Bienvenue", "célébrer",
    "commencer", "danser", "débarquement", "détester", "dix", "écouter", "entier",
    "épinards", "époque", "espérer", "essayer", "est-ce", "faire", "française", "jeunes",
    "le", "manger", "moins", "nager", "parler", "partager", "parisien", "préférer",
    "protéger", "pu", "puissant", "qu'", "que", "regarder", "répéter", "savoir", "se",
    "sûr", "tâche", "tien", "travailler", "visiter", "voyager",
    # Additional French tokens requested to be ignored
    "bain", "marie", "bain-marie", "patissière", "bâton", "brunoise",

    # --- Additional false-positives / capitalised French words requested by user ---
    # examples and commonly-flagged tokens (keeps both lower and capitalised forms where useful)
    "oracy", "Oracy",  # reported in language-check outputs
    "timetabled",  # British English word flagged by spellchecker in some reports
    "Cymraeg",  # Welsh language name (seen in reports)

    # Capitalised / correctly-spelled French tokens to ignore (examples from reports)
    "Il", "Je", "Moi", "Lucien", "Béatrice", "Béa", "étranger", "expérience",
    "compétences", "informatiques", "employeurs", "emploi", "université", "Quelquefois",
    "passe-temps",

    # --- Sports / arts / media terms ---
    "Boccia", "Camogie", "Goalball", "Trampolining", "storyboarding", "livestreamed", "food-related",

    # --- Authors / people / proper names ---
    "Crossan", "Haddon", "Kay", "Laird", "Magorian", "Morpurgo", "Newbery", "Sherald", "Swindells",
    "Sirkka-Liisa",
    # --- Additional proper nouns requested by user ---
    "Achebe", "Abse", "Acevedo", "Aitchison", "Bazin", "Christelle", "Chetty", "Fugard", "Fitzgeralds", "Forna", "Fraillon", "Heppenstall", "Kalhan", "Kelman", "Lefteri", "Lemn", "Maarten", "Macnamara", "McElhenney", "Meera", "Melhuish", "Mistry", "Monisha", "Nagra", "Parminder", "Pixley", "Reay", "Sathnam", "Syal", "Trivedy", "Troost", "Wilcock", "Yoon", "Zojceska",
    # Characters / literary / mythical
    "Birlings", "Egeus", "Pyramus", "Tsotsi",
    # Places
    "Copperopolis", "Deir Yassin", "Eynsford", "Ladbroke", "Malekula", "Nollywood",
    # Publishers, Orgs & Brands
    "Bloodaxe", "OpenLearn", "TalentLyft", "Transworld", "TriQuarterly",

    # --- Welsh language words & names requested by user ---
    "Clwb", "Dydd", "Gyda", "Helo", "Miwsig", "Taid", "Tyrd",
    "Dafydd", "Efa", "Fforestfach", "Ifor", "Nain", "Radyr", "Senedd", "Urdd", "Ymlaen",

    # --- Technical, literary and compound terms ---
    "griots", "micropause", "obeah", "Sikhi", "translanguaging",

    # --- Poetic / archaic / colloquial spellings ---
    "faery", "gapèd", "gloam", "lullèd", "shoulda", "wert", "withereth",

    # --- Acronyms / abbreviations ---
    "Aos", "JCQ", "TNCs",

    # --- Technical / other terms ---
    "creditworthy", "De Morgan's", "microfinance", "nonexamination", "pseudocode", "Raspbian",
    "Translanguage",

    # --- Drama: proper nouns (practitioners, writers, companies) ---
    "Adelayo", "Adedayo", "Artaud", "Artaudian", "Ayling", "Berkoff", "Berkoffian", "Boal", "Brecht", "Brechtian", "Buether", "Chickenshed", "Complicité", "Goch", "Habte", "Hijinx", "Kizer", "Lionboy", "Lolfa", "Macmillian", "Peakes", "Rafi", "RashDash", "Ravenhill", "Stanislavski", "Theatr", "Trezise", "Tsion", "Tunley", "Vickery", "Woyzeck", "Woza", "Wyddfa", "Zizou",

    # --- Drama: technical / production terms ---
    "arte", "berliner-ensemble", "crossfade", "Dramaturg", "freezeframes", "gestus", "gobo", "gobos", "multi-roling", "realia",

    # --- History: people and places seen in reports ---
    "Glyndwr", "Gruffudd", "Süleyman", "Sonni", "Jahan", "Askia", "Temujin", "Tyerman", "Babur", "Hardrada", "Llywelyn", "Cnut", "Nur", "Gruffydd", "Turvey", "Culpin", "Hanmer", "Breverton", "Genghis", "Swayer", "Deheubarth", "Songhai", "Harlech", "Khwarazmian", "Tondibi",
    # --- Additional history tokens discovered in later report chunks ---
    # Crusades / Middle East / Anatolia
    "Western Europe", "Byzantine Empire", "Alexius", "Alexios", "Komnenos", "Zengi", "Zengid", "Hattin", "Nur ad-Din", "Nurad", "Imad al-Din", "al-Din",
    # Ayyubid / Mamluk / related names and places
    "Ayyubid", "Ayyubids", "Mamluk", "Mamluks", "Baybars", "Baibars", "Akko",
    # Central Asian / West African names seen in reports
    "Central Asia", "Songhay", "Djenné", "Djenne", "Djinguereber", "Sankoré", "Mansa", "Mansa Munsa",
    # Mughal / South Asian tokens
    "Baburnama", "Babur", "Humayun", "Humayan", "Sher Shah", "Sher Shah Suri", "Suri", "Kannauj", "Akbarnama", "Fatehpur", "Fatehpur Sikri", "Mansabdars", "Zamindars", "Abul Fazl", "Abul", "Ibadat Khana", "Ustad Mansur", "Mansur", "Chittorgarh", "Akbar", "Taj", "Taj Mahal", "Shikoh", "Shikoh",
    # Scholars / modern authors
    "Truschke",
    # --- Additional proper nouns / place names discovered in recent language-check reports ---
    "Ghengis", "Gwenllian", "Tewdwr", "Hefin", "Dinefwr", "Kidwelly", "Crogen", "Ewloe", "Crug", "Crug Mawr", "Tenby", "Cadwaladr", "Maredudd", "Maelgwn", "Gryg", "Gethin", "Iorwerth", "Llansteffan", "Haverfordwest", "Laugharne", "Nevern", "Painscastle", "Colwyn", "Rhys", "Owain", "Anarawd", "Historynet", "Wiston", "Llandeilo", "Jamukha", "Ong", "Naiman", "Togrul", "Toghrul", "Anda", "Börte", "Borte", "Chinggis", "Merkit", "Kuchlug", "Ögodei", "Ogodei", "Baljuna", "Chakirmaut", "Kurultai", "Burkhan", "Yassa", "Kheshig", "Nokor", "Nökör", "Khitai", "Xianzong", "Zhangzong", "Tangut", "Tumen", "Mingghan", "Khwarazmians", "Khwarazm",
    # --- Additional Welsh historical names and variants requested from recent reports ---
    "Brough", "Pwll", "Melyn", "Ddu", "Dafydd", "Gam", "Hanmers", "Darogan", "Cadw", "Pennal", "Tywysog", "Mid Wales", "Mid-Wales",
    # --- Further tokens from recent language-check outputs (history / place names) ---
    "Hyddgen", "Ruthin", "Chevauchée", "Chevauchee", "Mynydd", "Glas", "Bryn Glas", "Brynglas", "Pilleth", "Ferch", "Triparte", "Elwyn", "Veysey", "Herberts", "Magor", "Glanmor", "Henrician", "Tintern", "Tretower", "Plas", "Mawr", "Plas Mawr", "Artemus", "Hywel", "Dda",
    # --- Additional historical / place names requested to be ignored ---
    "Forkbeard", "Harthacnut", "Jorvik", "Djenne", "Panipat", "Byrom", "Woff",

    # --- Food-and-Nutrition ---
    "Yn", "yn", "bwyd", "Gymru", "arbennig", "ddefnyddiol", "eu", "ardystio", "gan", "ond", "efallai", "byd", "Bwyd", "barod", "ar", "Adnoddau", "Gwyddor", "Eatwell",
    "wholewheat", "Wholewheat", "roux", "Shortcrust", "trialing", "zesting", "Zesting", "dextrinization", "prereleased", "sucrée", "griddling", "spatchcock", "deseeding", "chiffonade",

    # --- English-Language-and-Literature ---
    "Alem", "Birling", "Iola", "Pinnock", "Meggarty", "Packham", "Conran", "Miquita", "Riz", "Atta", "Sissay", "Brumley", "Dharker", "Imtiaz", "Muffet", "Catrin", "Killay", "Miz", "Alys", "Taffia", "aloo", "parathas", "longlist", "coversheet", "PRUs",

    # --- Geography ---
    "Borth", "Abermule", "Forden", "Berriew", "Twyni", "Rheidol", "Conwy", "Hina", "Blaenau", "Hafren", "Ystwyth", "Bannau", "Teleférico", "Ferrel", "Digimap",
    "LICs", "HICs", "Groynes", "OEBPS", "UNHDR", "isoline", "Throughflow", "skillset", "cumecs", "quadrats", "housebuilding", "socio-cultural", "skillfully", "Lasagne", "coginio",

    # --- Additions from language-check-report (chunk lines 1501-2000) ---
    # Proper nouns and tokens found in the report that should not be flagged
    "Wolgemut", "Stigand", "Eadmer", "Rubenstein", "Tinchebrai", "Patcham",
    "Warenne", "Cutestornes", "Phillipa", "Domesday", "Gytha", "Thorkilsdottir",
    "Malet", "Orderic", "Vitalis", "Orderic Vitalis", "Historia Ecclesiastica",
    "Brynmawr", "NUWSS", "WSPU", "Newsround", "Radway", "Whiskerd", "Pankhursts",
    "Kilkeel", "Bygott", "Hereward", "Malcom", "Leyser", "Seebohm", "Whyman",
    "Wykes", "Vreeland", "Econlib", "Pathé",

    # --- Additions from language-check-report (chunk lines 2001-EOF) ---
    # Proper nouns and tokens found in the final chunk of the report
    "Jizya", "Ilahi", "llahi", "Ibadat", 
    "McLynn", "Godwinson", "Sheppey", "Manzikert", "Ivar", "Ubba",
    "Halfdan", "Ragnarsson", "Lodbrok", "Lionheart", "WASPs", "Duranty",
    "Trueman", "Franklin D Roosevelt", "Kornilov", "Moorhouse", "Nimni", "OAAU",
}