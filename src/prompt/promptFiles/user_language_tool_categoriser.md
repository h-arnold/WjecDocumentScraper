<!-- Document header (header, inputs, task) is defined in the system prompt
	to keep static role instructions separate from per-batch content. -->

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

