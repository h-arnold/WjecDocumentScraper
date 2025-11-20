{{#issue_pages}}
### Page {{page_number}}

#### Pre-existing issues (Ignore - these have been flagged already)

| issue_id | issue | highlighted_context |
| --- | --- | --- |
{{#issues}}
| {{issue_id}} | {{issue}} | {{highlighted_context}} |
{{/issues}}

#### Page context:
```markdown
{{{page_content}}}
```

---
{{/issue_pages}}

{{^issue_pages}}
{{{issue_table}}}
{{/issue_pages}}

---

**IMPORTANT**:

1. Use the error descriptions provided to categorise each issue accurately. You are assessing a piece of formal writing where the highest spelling and grammatical standards are expected.
2. Check the "Pre-existing issues" table in the user prompt. Do not output any error that appears in that table.
3. Do not output errors found inside code blocks or intentional exam questions.
4. Always return a valid JSON array.
