"""Hand-written guidance for the table widget type."""

TABLE_GUIDANCE = """### Column Formatting

Always set `format` on columns that contain:
- **Monetary values**: use `"currency"` — auto-formats with currency symbol
- **Percentages/rates**: use `"percent"` — auto-applies red/green coloring based on positive/negative
- **Dates**: use `"date"` — auto-formats to readable date
- **Numbers**: use `"number"` — auto-formats with thousand separators

### SQL Patterns

**Detail table:**
```sql
SELECT name, email, created_at, total_spent, conversion_rate
FROM customers
ORDER BY total_spent DESC
LIMIT 100
```
Lean params:
```json
{
  "type": "table",
  "columns": [
    {"column": "name", "label": "Customer", "sortable": true},
    {"column": "email", "label": "Email"},
    {"column": "created_at", "label": "Joined", "sortable": true, "format": "date"},
    {"column": "total_spent", "label": "Total Spent", "sortable": true, "format": "currency"},
    {"column": "conversion_rate", "label": "Conv. Rate", "format": "percent"}
  ]
}
```

### Visual Column Features (set per entry in `columns`)

Extended display fields go on each `columns` entry (the backend lifts them into the mapping):
- **Ranking tables** (top-N by a metric): set `displayType: "bar"` + `showBarValue: true` on the key metric — in-cell bars make rank obvious at a glance
- **Dense numeric comparison** (many numeric columns): set `displayType: "heatmap"` on the metrics
- **Share-of-total questions**: set `comparisonCalc: "percentOfTotal"` on the metric
- **Cumulative views**: set `runningCalc: "runningSum"` on the metric
- Tag columns with `role`: `"dimension"` for grouping/text columns, `"metric"` for numeric values
- Set `compactNumbers: true` on metrics that can exceed ~10,000

### Best Practices

- Place tables in the detail section (after its `section` header widget)
- Tables always take a full-width row — the backend handles sizing
- Always use LIMIT in SQL to avoid sending thousands of rows
- Make key columns sortable for interactive exploration
- Set format on every column that isn't plain text — it significantly improves readability
- Always set `defaultSortKey` to the primary metric (with `defaultSortDir: "desc"`)
- For totals, set `showSummaryRow: true` and `aggregation` on each metric column
- **Always set `title`** — the table renders it as a label above the columns. Do NOT place a separate Text widget just to title a table; use `title` instead.

Example (lean) with title:
```json
{"type": "table", "title": "Availability, Bookability & Review Trends",
 "connectionId": 1, "sql": "SELECT ...",
 "columns": [{"column": "name", "label": "Customer", "sortable": true}],
 "pagination": true, "rowsPerPage": 25}
```
"""
