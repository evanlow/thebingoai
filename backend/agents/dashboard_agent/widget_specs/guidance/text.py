"""Hand-written guidance for the text widget type."""

TEXT_GUIDANCE = """### Usage

Text widgets are for **narrative prose** — commentary, methodology notes,
caveats. Section headers are the `section` widget type, NOT text widgets.

### Example (lean)

```json
{"type": "text", "content": "Figures exclude cancelled orders."}
```

### Best Practices

- Use sparingly — most dashboards need zero text widgets
- Markdown supported; keep content concise
- Do NOT use `## Heading` text widgets as section headers — emit a
  `section` widget instead
- No dataSource needed — text is static content
"""
