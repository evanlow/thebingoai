"""Hand-written guidance for the pivot_table widget type."""

PIVOT_TABLE_GUIDANCE = """### When to use a Pivot Table

Use a pivot table to summarize a metric across TWO categorical breakdowns at once —
one down the rows, one across the columns — so relationships that a flat table hides
become obvious (e.g. revenue by Country × Quarter). Prefer it over a standard table
when the question is "metric by A and by B".

### How it works

- **Row dimensions**: break down the rows. Order = hierarchy, outer→inner. Always go
  general→specific (e.g. `region` then `city`, NOT `city` then `region`). Up to 10.
- **Column dimensions**: break down the columns (max 2). Each distinct value becomes a
  column group.
- **Values (metrics)**: aggregated in each row×column cell. Up to 20. Set `aggregation`
  on every value (sum/average/count/countDistinct/min/max/median/stdDev/variance).
- The SQL returns GRANULAR rows; the pivot grouping + aggregation is done by the widget.
  Do NOT pre-aggregate with GROUP BY unless the data is already at the needed grain.

### SQL pattern

```sql
SELECT region, quarter, revenue
FROM sales
WHERE region IS NOT NULL
```

Widget config + mapping:
```json
{
  "type": "pivot_table",
  "config": {
    "title": "Revenue by Region and Quarter",
    "rowDimensions": [{"column": "region", "label": "Region"}],
    "columnDimensions": [{"column": "quarter", "label": "Quarter"}],
    "values": [{"column": "revenue", "label": "Revenue", "aggregation": "sum", "format": "currency"}],
    "expandCollapse": true,
    "showRowTotals": true,
    "showColumnTotals": true
  }
}
```
Mapping lists the UNION of every referenced column:
```json
{
  "type": "pivot_table",
  "columnConfig": [
    {"column": "region", "label": "Region"},
    {"column": "quarter", "label": "Quarter"},
    {"column": "revenue", "label": "Revenue"}
  ]
}
```

### Best Practices

- Place pivot tables in Section 4 (Detail & Drill-Down, y=16+). Default w=8, h=5.
- Keep column dimensions to 1 (2 max) — wide pivots are hard to read.
- Use a hierarchy for row dimensions when there's a natural drill path; viewers expand/collapse it.
- Always set `config.title`; do not add a separate Text widget to title the pivot.
- Set `format` on currency/percent metrics for readability.
- Limits: ≤2 column dimensions, ≤10 row dimensions, ≤20 metrics.
"""
