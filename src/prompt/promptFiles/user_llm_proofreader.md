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
- Check the "Pre-existing issues" table in the user prompt. Never output any error that appears in that table.
{{/has_any_existing_issues}}
- Ignore intentional errors in context, such as non-examples, code blocks or exercises where that is the purpose.
- Ignore PDF conversion artifacts as specified in the guidelines.
- Always return a valid JSON array.
