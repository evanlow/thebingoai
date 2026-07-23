"""Hand-written guidance for the section widget type."""

SECTION_GUIDANCE = """### Usage

Section widgets are the dashboard's **section headers**: a slim colored bar
whose title labels the group of widgets below it (until the next section).
They are the ONLY way to title a section — never use a text widget as a header.

### Example (lean)

```json
{"type": "section", "title": "Revenue Trends & Seasonality", "sectionColor": "blue"}
```

### Best Practices

- `title` is plain text — no markdown, no `##`
- Emit one section widget per analysis theme (at least 2 analysis sections),
  plus one before the detail tables — every dashboard has 3+ section widgets
- Titles name the insight theme from your EDA questions ("Customer
  Concentration", "Conversion Funnel"), not the widget type; fall back to
  "Analysis & Trends" / "Breakdown & Composition" / "Detail & Records" only
  when the data offers no specific theme
- NEVER emit a section widget above the KPI band — the layout engine pins
  filters and KPIs to the top, so a header emitted there lands below the KPIs
- Full-width (w=12, h=1) — the backend handles sizing
- No dataSource — sections are structural
- Optional `sectionColor` (default|violet|blue|green|amber|rose) — give each
  analysis section a distinct color to aid visual scanning
"""
