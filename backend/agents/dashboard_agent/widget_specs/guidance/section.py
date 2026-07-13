"""Hand-written guidance for the section widget type."""

SECTION_GUIDANCE = """### Usage

Section widgets are the dashboard's **section headers**: a slim colored bar
whose title labels the group of widgets below it (until the next section).

### Example (lean)

```json
{"type": "section", "title": "Trends & Breakdown"}
```

### Best Practices

- `title` is plain text — no markdown, no `##`
- Place one before the charts section and one before the tables section
- Full-width (w=12, h=1) — the backend handles sizing
- No dataSource — sections are structural
- Optional `sectionColor` (default|violet|blue|green|amber|rose); omit unless
  the user asks for colored sections
"""
