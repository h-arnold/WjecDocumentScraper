## Issue Batch

{{#issue_pages}}
### Page {{page_number}}
| issue_id | issue | highlighted_context |
| --- | --- | --- |
{{#issues}}
| {{issue_id}} | {{issue}} | {{highlighted_context}} |
{{/issues}}

Page context:
```markdown
{{{page_content}}}
```

---
{{/issue_pages}}

{{^issue_pages}}
{{{issue_table}}}
{{/issue_pages}}

---

## Page Context

Review each page excerpt before making decisions. Pages appear in ascending order and always include the page marker line.

{{#page_context}}
### Page {{page_number}}
```markdown
{{{content}}}
```

{{/page_context}}

---

**REMEMBER**: Use the error descriptions provided to categorise each issue accurately. You are assessing a piece of formal writing where the highest spelling and grammatical standards are expected.

Always assume hyphenation issues are PDF conversion errors as this is a common issue with the OCR process. Do NOT report hyphenation issues.