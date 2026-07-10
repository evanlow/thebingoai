# Charts in Chat — Design

Status: approved
Date: 2026-07-10

## Goal

Let the chat agent show a chart directly in the conversation, not just text. Two triggers:

1. **Ad-hoc question** — "show sales by region last quarter" — agent runs a query and drops a chart inline as the answer.
2. **Reference existing widget** — user `@mentions` a dashboard and asks about it ("how's @Q3-Dashboard revenue trending?") — agent renders the single best-matching existing widget inline, live.

## Why this is cheap

The app already has a near-identical feature for **Briefings** (chat digest cards): `Briefing.payload` stores widget snapshots, `message.briefing_id` FK links a chat message to structured content, `BriefingWidgetEmbed.vue` renders a dashboard widget inline in chat with a `snapshot` prop that skips live re-query. This feature reuses that plumbing instead of inventing new chart-rendering code.

## Data model

New JSON column on `Message` (mirrors the existing `attachments` column):

```python
# backend/models/message.py
chart_specs = Column(JSON, nullable=True)  # list[ChartRef], default None
```

Alembic migration: add nullable JSON column, no backfill needed (existing rows stay `NULL`).

`ChartRef` shape — one of two kinds, discriminated by `kind`:

```ts
// frontend/types/dashboard.ts
type ChartRef =
  | {
      kind: "adhoc"
      widget: DashboardWidget       // full widget config + data snapshot, same shape as Dashboard.widgets entries
      connection_id: number         // kept so "pin to dashboard" can re-attach a live data source
    }
  | {
      kind: "dashboard_widget"
      dashboard_id: number
      widget_id: string             // real widget on a real dashboard — always live
    }
```

Mirrored on the backend as a Pydantic union in `backend/schemas/chat.py`, added to `ChatMessage`:

```python
class ChartRef(BaseModel):
    kind: Literal["adhoc", "dashboard_widget"]
    widget: Optional[Dict[str, Any]] = None       # adhoc only
    connection_id: Optional[int] = None            # adhoc only
    dashboard_id: Optional[int] = None              # dashboard_widget only
    widget_id: Optional[str] = None                 # dashboard_widget only

class ChatMessage(BaseModel):
    ...
    chart_specs: Optional[List[ChartRef]] = None
```

## Backend flow

### Path A — ad-hoc chart

New orchestrator tool `generate_chat_chart(question, connection_id)`, registered alongside the existing dashboard tools in `backend/agents/orchestrator/graph.py`.

- Internally calls a **trimmed slice** of the `dashboard_agent` pipeline: reuses `backend/agents/dashboard_agent/widget_specs/guidance/*` (chart-type selection rules) and its SQL generation step, but produces **one widget spec** and runs the SQL **once**. No `Dashboard` row is created, no `dashboard_widget_verifier` retry loop (that machinery exists for multi-widget dashboard consistency, not relevant to a single ad-hoc chart).
- Mirrors `orchestrator_briefing_tool.py`'s `_post_chat_message` pattern: the tool writes directly onto the assistant `Message` row —
  ```python
  message.chart_specs = [{"kind": "adhoc", "widget": widget_config, "connection_id": connection_id}]
  ```
  The `widget_config` embeds the queried rows inline (snapshot, frozen at generation time) — same convention as a briefing embed with `autoRefresh=false`.
- Failure handling: if SQL generation or execution fails, the tool returns a plain error string and writes no `chart_specs`. The orchestrator falls back to a normal text-only answer — same behavior as existing dashboard_agent failures.

### Path B — reference existing widget

- Orchestrator already resolves `@mentions` into `ResolvedMention{type: "dashboard", id, ...}` (`backend/schemas/chat.py`).
- When a chart-relevant question includes a dashboard mention, a new tool `select_dashboard_widget(dashboard_id, widget_id)` is exposed to the model. Before the model can call it, the orchestrator fetches that dashboard's `widgets` list (id, title, type only — cheap) and includes it in context, letting the model's own reasoning pick the best-matching widget id from titles. No separate ranking/embedding logic.
- Tool writes:
  ```python
  message.chart_specs = [{"kind": "dashboard_widget", "dashboard_id": dashboard_id, "widget_id": widget_id}]
  ```
- This widget is **live** — normal dashboard widget, refresh works, no snapshot.
- Failure handling: if the widget was deleted between mention-time and render-time, `BriefingWidgetEmbed.vue` already silently drops it (`widget.value = null`) — reused as-is, no new error path needed.

## Frontend

`ChatMessageBubble.vue` — after the markdown body, loop over `message.chart_specs`:

- `kind: "dashboard_widget"` → render `<BriefingWidgetEmbed :dashboard-id :widget-id />` unmodified. It already fetches the widget and renders live.
- `kind: "adhoc"` → render new component `ChatChartEmbed.vue`:
  ```vue
  <template>
    <div class="rounded-lg border border-neutral-100 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-4">
      <DashboardWidget :widget="chartRef.widget" :auto-refresh="false" />
      <ChartPinMenu :chart-ref="chartRef" @pinned="onPinned" />
    </div>
  </template>
  ```
  No fetch — the widget config + data is already embedded in the message payload from the backend.

Both paths render through the existing `DashboardWidget.vue` → `DashboardWidgetChart.vue` chain. Zero new chart-rendering logic (no new chart types, no new `useChart` code).

## Pin to dashboard (adhoc only)

- `ChatChartEmbed.vue` gets a small `⋮` menu: "Pin to dashboard" → picker of existing dashboards, or "New dashboard".
- Selecting a target calls the existing `create_dashboard` / `update_dashboard` orchestrator tools (already used by `dashboard_agent`) with the stored `widget` config and `connection_id` from the snapshot — no new persistence endpoint.
- On success, the frontend swaps that message's `chart_specs` entry in place: `{"kind": "adhoc", ...}` → `{"kind": "dashboard_widget", "dashboard_id": ..., "widget_id": ...}`, and the embed re-renders via `BriefingWidgetEmbed` (now live). No message-update endpoint currently exists, so this adds one: `PATCH /api/chat/messages/{message_id}/chart_specs`, scoped to writing only that column (auth: message must belong to the requesting user's conversation).
- `dashboard_widget` kind entries have no pin menu — already pinned.

## Testing

- Backend:
  - Unit test for `generate_chat_chart` — mock SQL execution, assert the tool writes a well-formed single-entry `chart_specs` list and that the widget config passes `dashboard_widget_verifier`-equivalent shape checks.
  - Unit test for `select_dashboard_widget` — given a dashboard's widget list and a question, assert a valid `widget_id` from that list is returned; assert graceful no-op if the dashboard has zero widgets.
  - Unit test: SQL failure path writes no `chart_specs`, falls back to text.
- Frontend:
  - Component test for `ChatChartEmbed.vue` — renders from an embedded snapshot with no network call, matches `BriefingWidgetEmbed`'s snapshot-render test pattern.
  - Component test for `ChatMessageBubble.vue` — asserts it dispatches to the correct embed component per `chart_specs[].kind`.
  - `BriefingWidgetEmbed.vue` is untouched — no new test needed there.

## Out of scope

- Live re-query for ad-hoc charts (deferred — snapshot only, per design decision).
- Rendering more than one widget per `@dashboard` mention (deferred — single best match only).
- Streaming chart generation (chart appears once the tool call completes, not incrementally).
