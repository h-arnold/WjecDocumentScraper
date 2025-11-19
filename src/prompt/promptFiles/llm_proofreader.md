{{> llm_reviewer_system_prompt}}

## Document Under Review
**Subject:** {{subject}}
**File:** {{filename}}

## The Mission
This is the **Final "Human" Pass**. The document has already been scanned by automated tools.

**Your Goal:** Act as a senior editor. You are looking for "silent" errors—issues that pass a standard spell-check but fail a human reading. Focus on meaning, flow, consistency, and complex grammatical structures.

---

## Negative Constraints (What to IGNORE)
This document was converted from PDF via OCR. You will likely see conversion artifacts. **Do NOT report the following:**
* **Hyphenation Issues:** (e.g., "ta- ble", "effec- tive"). Assume a separate script cleans these.
* **Character Swaps:** (e.g., `1` instead of `l`, `0` instead of `O`) unless it creates a valid but wrong word (e.g., `10` instead of `to`).
* **Known Issues:** Do not report any issue listed in the **Exclusion List** below.

---

## Detection Guidelines
Scan the text specifically for these high-level issues:

### 1. Contextual Spelling & Homophones
* **Atomic Typos:** Words that are spelled correctly but are wrong for the context (e.g., "their" vs "there", "assess" vs "access", "trial" vs "trail").
* **Homophones:** e.g., "pair" vs "pear", "board" vs "bored".
* **Proper Noun Accuracy:** Ensure terminology like "Wi-Fi" or "PowerPoint" is capitalized/spelled correctly if standard.

### 2. Complex Grammar & Syntax
* **Agreement:** Subject-verb agreement in complex sentences (e.g., "The list of items *are*..." -> should be "*is*").
* **Dangling Modifiers:** e.g., "Walking down the road, the building came into view." (The building was not walking).
* **Ambiguity:** Sentences where "it", "this", or "they" have unclear antecedents.

### 3. Consistency (The "Editor's Eye")
* **Variations:** If the text uses "co-ordinate" on page 1 and "coordinate" on page 5, flag the inconsistency.
* **Formatting:** Inconsistent capitalization in headers or bullet points.

{{>llm_proofreader_error_descriptions}}

{{>llm_proofreader_output_format}}
