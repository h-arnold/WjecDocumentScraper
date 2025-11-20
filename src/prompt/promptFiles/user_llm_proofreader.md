{{#issue_pages}}
### Page {{page_number}}

{{#has_existing_issues}}
#### Pre-existing issues (Ignore - these have been flagged already)

| issue_id | issue | highlighted_context |
| --- | --- | --- |
{{#issues}}
| {{issue_id}} | {{issue}} | {{highlighted_context}} |
{{/issues}}
{{/has_existing_issues}}

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

- Use the error descriptions provided to categorise each issue accurately. You are assessing a piece of formal writing where the highest spelling and grammatical standards are expected.
{{#has_any_existing_issues}}
- Check the "Pre-existing issues" table in the user prompt. Do not output any error that appears in that table.
{{/has_any_existing_issues}}
- Do not output errors found inside code blocks or intentional exam questions.
- Always return a valid JSON array.
