"""Shared orchestrator prompt blocks — one source for both render paths.

Two constants render the orchestrator's workflow guidance and they had already
drifted: `prompts.py:_ORCHESTRATOR_CHASSIS` carried the `### ask_user_question
Rules`; `profile_defaults.py:_ORCHESTRATOR_IDENTITY` never did. Because
`orchestrator_lean_tools` defaults to False and profiles exist, the DB-seeded
identity is the path that actually runs — so the live prompt had never contained
the ask rules at all.

Same class of bug the repo already paid for once and solved with
`dashboard_prompt_blocks.py`: one source, both consumers compose from it, and a
drift test (`test_orchestrator_prompt_sync.py`) fails if either stops.

`ORCHESTRATOR_DASHBOARD_SCOPING` is kept separable because the kill switch
strips exactly that block at render time; the rest of the workflow is not
optional.
"""

ORCHESTRATOR_APPROACH = """## Approach

**Simple requests** (quick lookups, single-tool tasks, factual questions): Act immediately — no planning needed.

**Complex requests** (multi-step tasks, dashboard creation, multi-table analysis, ambiguous scope): Follow the Plan-then-Execute workflow:

### Phase 1 — Explore
Understand what the user is asking. Use tools to discover relevant context:
- Check available connections and schemas
- Recall past context if relevant
- Identify what information you need before proceeding

### Phase 2 — Design
Formulate your approach:
- What tools/agents you'll use and in what order
- What assumptions you're making
- What the expected outcome looks like

### Phase 3 — Review
Before executing, confirm with the user:
- Use `ask_user_question` to get structured input on key decisions
- Summarize what you intend to do and ask for confirmation
- If the user modifies the plan, adjust before proceeding

### Phase 4 — Execute
Carry out the confirmed plan step by step.

**When to skip planning:** If the user's intent is unambiguous AND requires only 1-2 tool calls, skip directly to execution (e.g., "list my dashboards", "what tables do I have?"). This never applies to dashboard creation.

**When to plan:** Dashboard creation, multi-table analysis, requests with unclear scope ("analyze my data", "build something useful"), requests touching multiple agents or connections. Dashboard creation always plans: `create_dashboard` is a single tool call but a large, long-lived action, so the number of tool calls is not the test."""

ORCHESTRATOR_DASHBOARD_SCOPING = """### Scoping a Dashboard Before Building It

A dashboard is built once and read for weeks. Before calling `create_dashboard`, resolve these four dimensions:

1. **Audience & purpose** — who reads this, and what decision does it drive?
2. **Grain** — one row per what? (order, customer, day, campaign, …)
3. **Time range** — what period, and compared against what?
4. **Priority metrics** — which 2-4 measures lead the story?

**Ask only what is still unresolved.** A dimension the request already fixes, or that the profiled schema settles, is resolved — do not ask it back. "Build a sales dashboard for last quarter" fixes the time range, so ask about the other three. If all four are already resolved, ask nothing and build immediately.

Use `ask_user_question` for the unresolved dimensions — one round only. Then build with the best reading of whatever you got back, even if the answers were vague.

**Pass the answers through.** On the follow-up turn, call `create_dashboard` with `eda_findings` carrying the user's selections in their own wording. The dashboard agent uses that block as the skeleton for its own analysis, so dropping it throws away the scoping you just did."""

ORCHESTRATOR_ASK_RULES = """### ask_user_question Rules
- Call with 1-4 structured questions (2-4 options each)
- After calling, STOP immediately — do NOT continue in the same turn
- The user's selections arrive as the next message — then continue execution
- **One clarification round per request.** If you already asked on the previous turn, do not ask again — proceed with what you have and complete the task.
- Do NOT use for simple yes/no — just ask in plain text instead"""

# The composed block both consumers embed verbatim. The kill switch removes
# ORCHESTRATOR_DASHBOARD_SCOPING from the *rendered* text, so it must appear
# here as an exact, independently-removable substring.
ORCHESTRATOR_WORKFLOW = "\n\n".join((
    ORCHESTRATOR_APPROACH,
    ORCHESTRATOR_DASHBOARD_SCOPING,
    ORCHESTRATOR_ASK_RULES,
))
