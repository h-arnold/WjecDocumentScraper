
#### Step 1: Document Conversion & Clean-up
* **Action:** Run your initial language check.
* **LLM Task (Optional):** Use the LLM to perform a classification task on the error report.
* **Prompt:** "Given this list of errors from a language tool, score each one from 1-5 on its likelihood of being a *document conversion error* (e.g., `combinedwords`, `missin g spaces`, missing hyphens) vs. a *human writing error*."
* **Goal:** To help you prioritise clean-up before the real checks begin.

---

#### Step 2: Detailed Contextual Language Review (Chunked)
* **Action:** Break the cleaned document into 10-20 page chunks.
* **LLM Task:** Perform a high-level "copyedit."
* **Prompt:** "You are an expert proofreader for an exam board. Review the following text for these specific issues **only**:
    1.  **Contextual Spelling Errors:** Words that are spelled correctly but used incorrectly (e.g., `leaner` vs. `learner`, `principal` vs. `principle`).
    2.  **Style Guide Violations:** Check against the provided [Your Style Guide Rules] (e.g., 'learner' is always used, not 'student'; 'Key Stage 4' is always capitalised).
    3.  **Clunky Phrasing:** Identify any sentences that are ambiguous, overly complex, or grammatically awkward. Suggest a clearer alternative."
* **Goal:** To catch the subtle errors traditional spellcheckers miss.

---

#### Step 3: Grounded Factual Verification (RAG)
* **Action:** This step **requires a "Source of Truth" (SoT)** file. This is a separate, human-vetted document you provide, containing all known-correct facts (e.g., correct regulator names, qualification titles, key dates, scientific constants).
* **LLM Task:** Compare the document's claims against the SoT.
* **Prompt:** "You will be given a document and a 'Source of Truth' file.
    1.  First, extract all factual claims from the main document (e.g., 'Qualifications Wales is the regulator,' 'The exam is 80 marks').
    2.  Second, for each claim, check if it is **directly supported by** or **contradicted by** the 'Source of Truth' file.
    3.  Output a JSON report listing all claims, their status ('Supported', 'Contradicted', or 'Not Found in SoT'), and the source text from both documents."
* **Goal:** To check facts *without* allowing the LLM to use its own (potentially wrong) knowledge.

---

#### Step 4: Internal Consistency (Extract-then-Validate)
* **Action:** Use the LLM to parse the entire document and extract key data.
* **LLM Task:** Data extraction.
* **Prompt:** "Scan the entire document and extract the following entities into a single JSON object:
    * The total marks listed on the cover page.
    * A list of all individual questions and their associated marks (e.g., `{'question': '1a', 'marks': 6}`).
    * A list of all Assessment Objectives and their stated weightings (e.g., `{'ao': 'AO1', 'weighting': '15%'}`).
    * A list of all internal cross-references (e.g., `{'source': 'Page 5', 'text': 'see section 3.4'}`).
    * A list of all section headings and their numbers (e.g., `{'number': '3.4', 'title': 'Assessment Details'}`)."
* **Validation (Code, not LLM):** Write a simple script (e.g., in Python) to:
    1.  Sum the marks from the question list and check if it equals the `total_marks` from the cover.
    2.  Check for duplicate or skipped question numbers.
    3.  Check that every cross-reference (e.g., "section 3.4") points to a section number that actually exists in the extracted list.
* **Goal:** To reliably and auditably check the document's internal structure and arithmetic.

---

#### Step 5: Cross-Document Consistency (Extract-then-Validate)
* **Action:** You've already done the hard part.
* **LLM Task:** None.
* **Validation (Code, not LLM):**
    1.  Run the **Step 4 (Extract)** process on *every document in the suite* (Spec, SAM, Teacher Guide), saving each as `spec.json`, `sam.json`, etc.
    2.  Write a master validation script that loads all these JSON files.
    3.  Compare the data points that *must* be identical.
    * `if spec.json[qual_code] != sam.json[qual_code]:` -> **FLAG ERROR**
    * `if spec.json[ao_weightings.AO1] != sam.json[ao_weightings.AO1]:` -> **FLAG ERROR**
    * `if spec.json[total_marks] != sam.json[total_marks]:` -> **FLAG ERROR**
* **Goal:** To ensure the entire qualification suite is perfectly synchronised.