"""Hand-written guidance for the chart widget type."""

CHART_GUIDANCE = """### Chart Type Selection

| Data pattern | Best type | Key options | Max width |
|---|---|---|---|
| Categories < 8 | bar or pie | `sortBy: "value"` | w=6 or w=8 |
| Categories 8-20 | bar | `indexAxis: "y"` (horizontal) | w=6 or w=8 |
| Categories > 20 | bar | `sortBy: "value"` | w=6 or w=8 |
| Composition (part-of-whole) | bar | `stacked: "standard"` | w=6 or w=8 |
| 100% composition | bar | `stacked: "percentage"` | w=6 or w=8 |
| Trend over time | line or area | `xAxisMode: "date"` | w=6, w=8, or w=12 |
| Part-of-whole < 8 | pie or doughnut | `showValues: true` | w=4 or w=6 (NEVER w=12) |
| Correlation (x vs y) | scatter | `showLegend: true` for grouped scatter | w=6 or w=8 |
| Multiple metrics, mixed types | line (combo) | `seriesType` per dataset | w=8 or w=12 |
| Sequential stages / conversion drop-off | funnel | `funnelLabelMode: "numberPercentage"` | w=4 or w=6 |
| Events/phases with start + end dates | timeline | `timelineColorBy: "row"` | w=8 or w=12 |

### Layout Rules

- Use **at least 2-3 different chart types** per dashboard
- Pie/doughnut charts are **NEVER full-width** — max w=6
- Default to w=6 and pair charts side-by-side at the same y row
- w=12 ONLY for time-series line/area charts
- Place charts in Section 3 (Analysis & Trends, y=5 to y=14)

### Options Best Practices

- **Bar charts**: set `sortBy: "value", sortDirection: "desc"` unless x-axis is temporal
- **Horizontal bars**: use `indexAxis: "y"` for long category labels or 8+ categories
- **Pie/doughnut**: always set `sliceLabel: "percentage"` so each slice shows its share (preferred over `showValues`)
- **Single-dataset charts**: hide legend with `showLegend: false` to reduce clutter
- **Stacked composition**: use `stacked: "standard"` — NOT `stacked: true`
- **100% stacked**: use `stacked: "percentage"` to normalise each bar/area to 100%
- **Time-series**: always set `xAxisMode: "date"` when the x-axis is a date/datetime column
- **Noisy daily time-series**: add a trendline on the main series — `{"trendline": {"type": "movingAverage", "period": 7}}` in its datasetColumns entry
- **Known target/threshold** (quota, SLA, goal mentioned by the user): add ONE entry to `options.referenceLines`, e.g. `{"value": 10000, "label": "Target"}`
- **Cumulative questions** ("running total", "growth to date"): set `cumulative: true` on the dataset column instead of writing window-function SQL
- **Data labels**: `showDataLabels: true` on at most the single headline series — labels on every series clutter the chart
- Skip animation config unless specifically requested — defaults are sensible

### Per-Series Aggregation (datasetColumns.aggregation)

When the SQL returns **pre-aggregated data** (one row per label), `aggregation` can be omitted or set to `"none"`.

When the SQL returns **raw/unaggregated rows** with repeated label values, set `aggregation` on each dataset column so the transform groups-by `labelColumn` and aggregates. Available values: `sum`, `avg`, `count`, `countDistinct`, `min`, `max`, `first`, `last`, `none`.

Example — daily rows aggregated to monthly totals:
```sql
SELECT date_trunc('month', created_at) AS month, amount, region
FROM orders
ORDER BY month
```
Mapping:
```json
{"type": "chart", "labelColumn": "month", "datasetColumns": [{"column": "amount", "label": "Revenue", "aggregation": "sum"}], "options": {"xAxisMode": "date"}}
```

### Combo Charts (mixed Line + Bar series)

Use a single chart widget with `seriesType` per dataset column when you want one metric as bars and another as a line (e.g. revenue as bars, growth rate as line):
```json
{"type": "chart", "labelColumn": "month",
 "datasetColumns": [
   {"column": "revenue", "label": "Revenue", "aggregation": "sum", "seriesType": "bars"},
   {"column": "growth_rate", "label": "Growth %", "aggregation": "avg", "seriesType": "line", "yAxisID": "right"}
 ]}
```
With a second Y-axis, add `yAxisRight: {"title": "Growth %"}` to options and set `alignBothAxesToZero: true` if both axes should start at 0.

### Time-series Drill-down & Category Breakdown (mapping-driven — preferred)

The transform buckets dates and pivots breakdown series **in Python**, so the SQL can return
RAW timestamp/category/metric rows — you do **not** need `DATE_TRUNC` or a pivot. Set the
mapping keys instead:

- **`dateGranularity`** buckets the `labelColumn` timestamp: `year | quarter | month | week | day | hour`
  (chronological periods) or `hour_of_day | day_of_week | month_of_year` (repeating "part" slices for
  seasonality). When you set `dateGranularity`, do NOT also set `options.xAxisMode: "date"` — the
  bucketed labels are pre-formatted categories.
- **`breakdownColumn`** splits the FIRST metric into one series per distinct value. Combine with
  `options.stacked: "standard"` (stacked) or `"percentage"` (100%-stacked) for composition over time.

When a timestamp dimension AND a category both exist, prefer this multi-series form over a single
aggregated line. Pick granularity from the date min/max span (hour/day for short ranges, month/quarter
for multi-year). Use a "part" bucket when the user asks about timing patterns ("what hour sells best").

**Best sales hour (hour_of_day part bucket):**
```sql
SELECT s.datetime, s.money
FROM sales s
```
Mapping:
```json
{"type": "chart", "labelColumn": "datetime", "dateGranularity": "hour_of_day",
 "datasetColumns": [{"column": "money", "label": "Sales", "aggregation": "sum"}]}
```

**Sales per product over months (multi-series / stacked):**
```sql
SELECT s.date, s.product_name, s.money
FROM sales s
```
Mapping:
```json
{"type": "chart", "labelColumn": "date", "dateGranularity": "month",
 "breakdownColumn": "product_name",
 "datasetColumns": [{"column": "money", "label": "Sales", "aggregation": "sum"}],
 "options": {"stacked": "standard"}}
```
Set `options.stacked: "percentage"` for a 100%-stacked share-over-time chart, or omit `stacked` for
multi-line / grouped bars.

### SQL Patterns (use baseJoin from data context)

IMPORTANT: Every chart must include the baseJoin from the dashboard data context so that
dashboard filters can reach all dimensions. Use table aliases from the baseJoin.

**Bar/pie (categorical) with baseJoin:**
```sql
SELECT o.category, COUNT(*) AS count
FROM orders o
LEFT JOIN payments p ON o.id = p.order_id
GROUP BY o.category
ORDER BY count DESC
```
Mapping: `{"type": "chart", "labelColumn": "category", "datasetColumns": [{"column": "count", "label": "Orders"}]}`

**Line/area (time-series) with baseJoin — always use xAxisMode: "date":**
```sql
SELECT DATE_TRUNC('month', o.created_at) AS month,
       SUM(o.revenue) AS revenue,
       SUM(o.costs) AS costs
FROM orders o
LEFT JOIN payments p ON o.id = p.order_id
GROUP BY month
ORDER BY month
```
Mapping:
```json
{"type": "chart", "labelColumn": "month",
 "datasetColumns": [
   {"column": "revenue", "label": "Revenue", "aggregation": "sum"},
   {"column": "costs", "label": "Costs", "aggregation": "sum"}
 ],
 "options": {"xAxisMode": "date", "sortBy": "none"}}
```
NOTE: always set `sortBy: "none"` for time-series so chronological order is preserved.

**Multi-dataset stacked (standard) with baseJoin:**
```sql
SELECT o.region, o.product_type, SUM(o.sales) AS sales
FROM orders o
LEFT JOIN payments p ON o.id = p.order_id
GROUP BY o.region, o.product_type
```
Use one datasetColumn per series. Set `options.stacked: "standard"` (not `true`).

**100% stacked bar:**
Same SQL as above; set `options.stacked: "percentage"`.

**Scatter (correlation) with xMetricColumn/yMetricColumn — PREFERRED:**
```sql
SELECT metric_x, metric_y
FROM orders
WHERE metric_x IS NOT NULL AND metric_y IS NOT NULL
```
Mapping:
```json
{"type": "chart",
 "xMetricColumn": "metric_x",
 "yMetricColumn": "metric_y"}
```
Use `xAggregation`/`yAggregation` when you need to group scatter points (e.g. average per category):
```sql
SELECT category, AVG(spend) AS avg_spend, AVG(conversion_rate) AS avg_conversion
FROM campaigns
GROUP BY category
```
Mapping:
```json
{"type": "chart",
 "xMetricColumn": "avg_spend",
 "yMetricColumn": "avg_conversion"}
```

**Scatter (legacy fallback — only if grouping by a dimension is needed):**
```sql
SELECT o.metric_x, o.metric_y, o.category
FROM orders o
LEFT JOIN payments p ON o.id = p.order_id
WHERE o.metric_x IS NOT NULL AND o.metric_y IS NOT NULL
```
Scatter mapping rules for legacy path:
- `labelColumn`: the grouping column (e.g. category/team) — points are grouped into one dataset per unique value
- `datasetColumns`: exactly 2 entries — label them with `(X)` and `(Y)` suffixes so the backend maps axes correctly
- `chartType`: **must** be set to `"scatter"` in the mapping

Mapping: `{"type": "chart", "chartType": "scatter", "labelColumn": "category", "datasetColumns": [{"column": "metric_x", "label": "Metric X (X)"}, {"column": "metric_y", "label": "Metric Y (Y)"}]}`

**Funnel (sequential stages / conversion drop-off):**
Use when one categorical dimension represents ordered stages whose counts shrink
from first to last (sales pipeline, signup→purchase conversion). Rows MUST be ordered
largest→smallest — the renderer draws stages in row order, so ORDER BY an explicit
stage rank, NOT by value.
```sql
SELECT stage, opportunities
FROM sales_pipeline
ORDER BY stage_order
```
Mapping:
```json
{"type": "chart", "chartType": "funnel", "labelColumn": "stage",
 "datasetColumns": [{"column": "opportunities", "label": "Opportunities"}],
 "options": {"funnelLabelMode": "numberPercentage", "funnelPercentType": "max"}}
```
When the stages live in a raw events table, GROUP BY the stage and rank in SQL
(e.g. a CASE expression) so the ORDER BY produces the funnel sequence.

**Timeline (events/phases with start + end dates):**
Use when each row has BOTH a start date and an end date (campaigns, projects, tasks).
Returns raw rows — one per event, NO GROUP BY. Needs `startColumn` + `endColumn`.
```sql
SELECT campaign_name, channel, start_date, end_date
FROM marketing_campaigns
ORDER BY start_date
```
Mapping:
```json
{"type": "chart", "chartType": "timeline", "labelColumn": "campaign_name",
 "startColumn": "start_date", "endColumn": "end_date", "barLabelColumn": "channel",
 "options": {"timelineColorBy": "row"}}
```
"""
