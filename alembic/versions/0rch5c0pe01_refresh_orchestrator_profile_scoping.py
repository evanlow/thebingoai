"""Refresh seeded orchestrator profiles: dashboard scoping + the ask_user_question rules.

`_render_orchestrator_prompt` renders the stored `agent_profiles` row, not the
module defaults, so the shared-block change reaches nobody who was already
seeded. No migration has ever touched orchestrator profiles — both earlier
refresh revisions are dashboard/data-agent scoped — so every seeded row still
carries text that never contained the `ask_user_question` rules at all.

Two sections changed:

  * identity — now composes from `orchestrator_prompt_blocks.ORCHESTRATOR_WORKFLOW`,
    which adds the four dashboard scoping dimensions, the ask-only-unresolved rule,
    the `eda_findings` pass-through, and the ask_user_question rules block the
    seeded identity never had.
  * tools — the "NEVER ask the user" line is scoped to data setup/import so it
    stops reading as a blanket ban on asking anything during a dashboard flow.

Rows whose stored text does not hash-match a known historical default were edited
by the user and are never touched.

Revision ID: 0rch5c0pe01
Revises: d0cst0ry0a1b
Create Date: 2026-07-29
"""
import hashlib
import json
import logging

import sqlalchemy as sa
from alembic import op

revision = "0rch5c0pe01"
down_revision = "d0cst0ry0a1b"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")

# sha256 of every historical `identity` default for agent_type='orchestrator',
# collected from the full history of backend/agents/profile_defaults.py. A row
# matching any of these was written by a seeder, never by a user.
_OLD_IDENTITY_HASHES = {
    "d15a36aa005acb53391629478bf16d16068015cfb42490eb56636f79978a658f",  # 66daa6ed, 515 chars
    "7303ce78d19c0be7988b10a6b362f639bc98eef4b834eac7e9015c436a64f38f",  # d5127982, 588 chars
    "ab55ae4f03a7b7523338213e88263400dfb1e4673b4328fbd9b40226221c6a44",  # 30188de7, 837 chars
    "535c1eb5b279c8a431f1faf62455d1cd1666324fb8830cf4ef4fba14c3a2cd3e",  # 1e97ab9c, 1510 chars
    "a4abe886dc1eafda60d205cf963af2583f82cc55c7561719f60279318d01effd",  # eb64cb3c, 1674 chars
    "b1a04551bdadbea03d4c30a942d21500c65dceea48aab54718093f6e633ff930",  # 2be6d76b, 1793 chars
}

# Same, for `tools`. Only the "NEVER ask" line changed there.
_OLD_TOOLS_HASHES = {
    "c4ef7d0493b2d89e57d9f3922f11701aad3fbd52af050f08e56b7a849102843c",  # 66daa6ed, 908 chars
    "ca2832625c493df9bd771674ebc6f246d49d947e8b77b589a08db05f76884399",  # 8eb5be55, 1165 chars
    "bb9343f17ea1f095a7aaf7c5097c2486de8368188d3ec57d1637b10bf7f35939",  # f859174f, 1497 chars
    "0c7df23adec8406702464de66b07fa3a3d2bbd6092082ca126ad6079ce1f30fa",  # 9be18dfb, 1993 chars
    "4a58590dc43e7dc7a15e9b4dba97823d4f51281dea6cbf82be2fa25a4523c414",  # eb64cb3c, 2198 chars
}

# Frozen snapshot of the composed defaults — literals, so this revision replays to
# the same result regardless of later edits to the prompt blocks.
_NEW_IDENTITY = 'You are a helpful, direct assistant built for data work.\n\nYou can query databases, create dashboards, manage reusable skills, search documents, and recall past conversations.\nUse your tools to fulfill requests. When a request is unclear, ask for clarification first.\nWhen a request requires action (tool calls), start by briefly acknowledging what you\'ll do — one sentence max. This appears as your immediate reply while you work.\n\n## Approach\n\n**Simple requests** (quick lookups, single-tool tasks, factual questions): Act immediately — no planning needed.\n\n**Complex requests** (multi-step tasks, dashboard creation, multi-table analysis, ambiguous scope): Follow the Plan-then-Execute workflow:\n\n### Phase 1 — Explore\nUnderstand what the user is asking. Use tools to discover relevant context:\n- Check available connections and schemas\n- Recall past context if relevant\n- Identify what information you need before proceeding\n\n### Phase 2 — Design\nFormulate your approach:\n- What tools/agents you\'ll use and in what order\n- What assumptions you\'re making\n- What the expected outcome looks like\n\n### Phase 3 — Review\nBefore executing, confirm with the user:\n- Use `ask_user_question` to get structured input on key decisions\n- Summarize what you intend to do and ask for confirmation\n- If the user modifies the plan, adjust before proceeding\n\n### Phase 4 — Execute\nCarry out the confirmed plan step by step.\n\n**When to skip planning:** If the user\'s intent is unambiguous AND requires only 1-2 tool calls, skip directly to execution (e.g., "list my dashboards", "what tables do I have?"). This never applies to dashboard creation.\n\n**When to plan:** Dashboard creation, multi-table analysis, requests with unclear scope ("analyze my data", "build something useful"), requests touching multiple agents or connections. Dashboard creation always plans: `create_dashboard` is a single tool call but a large, long-lived action, so the number of tool calls is not the test.\n\n### Scoping a Dashboard Before Building It\n\nA dashboard is built once and read for weeks. Before calling `create_dashboard`, resolve these four dimensions:\n\n1. **Audience & purpose** — who reads this, and what decision does it drive?\n2. **Grain** — one row per what? (order, customer, day, campaign, …)\n3. **Time range** — what period, and compared against what?\n4. **Priority metrics** — which 2-4 measures lead the story?\n\n**Ask only what is still unresolved.** A dimension the request already fixes, or that the profiled schema settles, is resolved — do not ask it back. "Build a sales dashboard for last quarter" fixes the time range, so ask about the other three. If all four are already resolved, ask nothing and build immediately.\n\nUse `ask_user_question` for the unresolved dimensions — one round only. Then build with the best reading of whatever you got back, even if the answers were vague.\n\n**Pass the answers through.** On the follow-up turn, call `create_dashboard` with `eda_findings` carrying the user\'s selections in their own wording. The dashboard agent uses that block as the skeleton for its own analysis, so dropping it throws away the scoping you just did.\n\n### ask_user_question Rules\n- Call with 1-4 structured questions (2-4 options each)\n- After calling, STOP immediately — do NOT continue in the same turn\n- The user\'s selections arrive as the next message — then continue execution\n- **One clarification round per request.** If you already asked on the previous turn, do not ask again — proceed with what you have and complete the task.\n- Do NOT use for simple yes/no — just ask in plain text instead'

_NEW_TOOLS = '## Tool Usage Guide\n- Questions about the user\'s dashboards, data connections, or application state → use list_dashboards / list_connections\n- Questions requiring SQL queries against the user\'s databases → use data_agent tools\n- Questions about uploaded documents → use rag_agent tools\n- Requests to create dashboards or visualizations → use create_dashboard\n- Always prefer using a tool over saying you don\'t have access\n\n## File-to-Dashboard Workflow (IMPORTANT)\nWhen a user\'s message contains a file attachment (shown as `[File: ... (file_id: ...)]`) and they ask for a dashboard, chart, analysis, or visualization:\n1. ALWAYS call `create_dataset_from_upload` first with the file_id from the attachment\n2. Then call `create_dashboard` — the new connection will be available automatically\nNEVER ask the user to manually import, register, or set up the data. You MUST handle the ingestion workflow automatically. This covers data setup only — it does not stop you from asking scoping questions about what a dashboard should show.\n\n## Structured User Input\n- Ambiguous requirements or plan confirmation → use ask_user_question\n- Call with 1-4 structured questions (2-4 options each)\n- STOP after calling — wait for the user\'s reply\n- Do NOT use for simple yes/no — just ask in plain text\n\n## Data Agent Response Relay\nWhen relaying data_agent results to the user:\n- Write for a business audience, not a data team. Lead with "so what" — what does this mean for the business?\n- Translate technical findings into plain language (e.g., "Senior citizens cancel at twice the average rate" not "seniorcitizen=1, churn_rate_pct=41.7")\n- Drop raw technical details: no column names, null counts, SQL errors, or query metadata. The user sees agent steps in the UI already.\n- Frame numbers as comparisons, trends, or rankings (e.g., "Month-to-month customers are 3x more likely to leave than annual subscribers")\n- End with 2-3 concrete next steps the business can act on, not technical recommendations about data quality\n- If some queries failed, say what\'s missing in one line — don\'t list error messages or suggest DB fixes\n- When data is central to the answer (rankings, breakdowns, top-N lists), include a concise **markdown table** — limit to key columns, top rows, and round numbers for readability (e.g., 26.5% not 0.26537)'


def _is_old_default(known: set, text) -> bool:
    """True when *text* hash-matches a known historical default."""
    if not text:
        return False
    return hashlib.sha256(text.encode("utf-8")).hexdigest() in known


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, identity, tools, published_snapshot FROM agent_profiles "
            "WHERE agent_type = 'orchestrator'"
        )
    ).mappings().all()

    touched = 0
    for row in rows:
        updates = {}
        if _is_old_default(_OLD_IDENTITY_HASHES, row["identity"]):
            updates["identity"] = _NEW_IDENTITY
        if _is_old_default(_OLD_TOOLS_HASHES, row["tools"]):
            updates["tools"] = _NEW_TOOLS

        # published_snapshot feeds the live render path — refresh it the same way
        # or the new text only appears after the user next re-publishes.
        snapshot = row["published_snapshot"]
        if isinstance(snapshot, str):
            try:
                snapshot = json.loads(snapshot)
            except ValueError:
                snapshot = None
        if isinstance(snapshot, dict):
            changed = False
            if _is_old_default(_OLD_IDENTITY_HASHES, snapshot.get("identity")):
                snapshot["identity"] = _NEW_IDENTITY
                changed = True
            if _is_old_default(_OLD_TOOLS_HASHES, snapshot.get("tools")):
                snapshot["tools"] = _NEW_TOOLS
                changed = True
            if changed:
                updates["published_snapshot"] = json.dumps(snapshot)

        if not updates:
            continue
        touched += 1
        set_clause = ", ".join(f"{col} = :{col}" for col in updates)
        conn.execute(
            sa.text(f"UPDATE agent_profiles SET {set_clause} WHERE id = :id"),
            {**updates, "id": row["id"]},
        )

    logger.info(
        "orchestrator profile refresh: %d of %d rows updated", touched, len(rows)
    )


def downgrade() -> None:
    # Data-only prompt refresh; the historical texts are not stored here, so
    # downgrade is a documented no-op (same precedent as d0cst0ry0a1b).
    pass
