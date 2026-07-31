"""System prompts for Dashboard Agent.

Prompt text lives in `backend.agents.dashboard_prompt_blocks` (shared with
`profile_defaults.py` so the inline and DB-profile paths never drift). This
module only composes the blocks and injects runtime context.
"""

from backend.agents.dashboard_prompt_blocks import (
    DASHBOARD_CROSS_CONNECTION,
    DASHBOARD_DESIGN_PRINCIPLES,
    DASHBOARD_FAILURE_RECOVERY,
    DASHBOARD_IDENTITY,
    DASHBOARD_MESH_WORKFLOW,
    DASHBOARD_SQL_CHECKLIST,
    DASHBOARD_UPDATE_RULES,
    DASHBOARD_WORKFLOW,
)

DASHBOARD_AGENT_SYSTEM_PROMPT = "\n\n".join(
    [
        DASHBOARD_IDENTITY,
        DASHBOARD_WORKFLOW,
        DASHBOARD_CROSS_CONNECTION,
        DASHBOARD_FAILURE_RECOVERY,
        DASHBOARD_DESIGN_PRINCIPLES,
        DASHBOARD_SQL_CHECKLIST,
        DASHBOARD_UPDATE_RULES,
    ]
)


DASHBOARD_AGENT_MESH_PROMPT = "\n\n".join(
    [
        "You are an expert dashboard creation agent operating in a peer-to-peer agent mesh.\n"
        "You design dashboards by coordinating with the data agent for schema exploration and SQL validation.",
        DASHBOARD_MESH_WORKFLOW,
        DASHBOARD_CROSS_CONNECTION,
        DASHBOARD_FAILURE_RECOVERY,
        DASHBOARD_DESIGN_PRINCIPLES,
        DASHBOARD_SQL_CHECKLIST,
        DASHBOARD_UPDATE_RULES,
    ]
)


def build_dashboard_agent_prompt(
    available_connections: list[int],
    mesh_enabled: bool = False,
    target_connection_id: int | None = None,
    connection_metadata: list | None = None,
    org_id: str | None = None,
) -> str:
    """
    Build dynamic system prompt with user's available connections.

    Args:
        available_connections: List of connection IDs user can access
        mesh_enabled: Whether to use mesh-aware prompt
        target_connection_id: Pre-selected connection to focus on (e.g. from a CSV upload)
        connection_metadata: Optional list of ConnectionInfo with name/db_type/database
        org_id: Org whose dialect flag selects the SQL hints (DuckDB once cut over)

    Returns:
        System prompt with connection context injected
    """
    from backend.config import settings

    use_mesh = mesh_enabled or settings.agent_mesh_enabled
    base_prompt = DASHBOARD_AGENT_MESH_PROMPT if use_mesh else DASHBOARD_AGENT_SYSTEM_PROMPT

    if not available_connections:
        return base_prompt + "\n\nWARNING: No database connections available."

    if connection_metadata:
        lines = [
            f'- ID {c.id}: "{c.name}" ({c.db_type}, database: {c.database})'
            for c in connection_metadata
        ]
        connections_str = "\n".join(lines)
    else:
        connections_str = ", ".join(str(conn_id) for conn_id in available_connections)
    prompt = (
        base_prompt
        + f"\n\nAvailable database connections:\n{connections_str}"
        + "\nAlways use one of these IDs as each widget's top-level connectionId."
    )

    if target_connection_id is not None:
        prompt += (
            f"\n\nPrimary connection to use: {target_connection_id}"
            "\nFocus your schema exploration on this connection. "
            "Only explore other connections if the user explicitly asks."
        )

    prompt += build_dashboard_runtime_suffix(
        available_connections=available_connections,
        connection_metadata=connection_metadata,
        target_connection_id=target_connection_id,
        org_id=org_id,
    )

    return prompt


def _column_label(name: str, cdata: dict) -> str:
    """Render one column as `name (Display Name) — description`.

    Both halves come from the semantic layer and are optional; with neither, this
    degrades to the bare column name the prompt used before.
    """
    label = f"{name} ({cdata['displayName']})" if cdata.get("displayName") else name
    if cdata.get("description"):
        label = f"{label} — {cdata['description']}"
    return label


def build_dashboard_runtime_suffix(
    available_connections: list[int],
    connection_metadata: list | None = None,
    target_connection_id: int | None = None,
    org_id: str | None = None,
) -> str:
    """
    Build the runtime context suffix appended to every dashboard-agent prompt:
    pre-built profiled connection context, connector-specific design hints, and
    SQL dialect hints. Used by both the inline fallback prompt and the
    AgentProfile path so profile users get the same runtime context.
    """
    suffix = ""

    # Include connection context summary if available (pre-built from profiling).
    # Enriched: overlays the semantic layer so curated/generated column meanings
    # reach the agent with the schema rather than only via the chat transcript.
    from backend.database.session import SessionLocal
    from backend.services.semantic_layer import load_enriched_context

    db = SessionLocal()
    try:
        for conn_id in available_connections:
            ctx = load_enriched_context(db, conn_id)
            if not ctx:
                continue
            tables = ctx.get("tables", {})
            if not tables:
                continue
            lines = [f"\n\nPre-built data context for connection {conn_id}:"]
            lines.append(f"Tables ({len(tables)}): {', '.join(sorted(tables.keys()))}")
            for tname, tdata in tables.items():
                cols = tdata.get("columns", {})
                dims = [_column_label(c, d) for c, d in cols.items() if d.get("role") == "dimension"]
                measures = [_column_label(c, d) for c, d in cols.items() if d.get("role") == "measure"]
                # Keys carry documented meaning too ("employee_id — one row per
                # employee"); rendering only dimensions and measures dropped it.
                keys = [_column_label(c, d) for c, d in cols.items() if d.get("role") == "key"]
                if dims or measures or keys:
                    header = tname
                    if tdata.get("description"):
                        header = f"{tname} — {tdata['description']}"
                    # "; " not ", ": a description may itself contain a comma, which
                    # would read as an extra column name inside the brackets.
                    parts = [
                        f"dimensions=[{'; '.join(dims)}]",
                        f"measures=[{'; '.join(measures)}]",
                    ]
                    if keys:
                        parts.append(f"keys=[{'; '.join(keys)}]")
                    lines.append(f"  {header}: {' '.join(parts)}")
            rels = ctx.get("relationships", [])
            if rels:
                lines.append(f"Relationships: {', '.join(r['from'] + ' → ' + r['to'] for r in rels[:10])}")
            lines.append("Use `build_dashboard_context` to assemble a dashboard context from these tables.")
            lines.append(
                "If this pre-built context already covers the tables you need, "
                "skip list_tables/get_table_schema and call build_dashboard_context directly."
            )
            suffix += "\n".join(lines)
    finally:
        db.close()

    # Connector-specific dashboard design hints (e.g. GA4 recommended KPIs +
    # breakdowns + filter patterns). Plugins set this on
    # ConnectorRegistration.dashboard_design_hint. Inject one block per
    # unique connector type the user can reach so the agent has concrete
    # guidance instead of generic dashboard heuristics.
    try:
        from backend.connectors.factory import get_connector_registration
        from backend.models.database_connection import DatabaseConnection
        seen_types: set[str] = set()
        for conn in (connection_metadata or []):
            db_type = getattr(conn, "db_type", None)
            if not db_type or db_type in seen_types:
                continue
            seen_types.add(db_type)
            reg = get_connector_registration(db_type)
            hint = getattr(reg, "dashboard_design_hint", None) if reg else None
            if hint:
                suffix += (
                    f"\n\n## Connector-specific guidance — {db_type}\n{hint}"
                )
    except Exception:
        # Defensive: hint injection must never block prompt build.
        pass

    # SQL dialect hints — driven by Org flag (duckdb_widget_serving) and
    # target connection db_type. New dashboards now emit source-native SQL
    # instead of always defaulting to BigQuery.
    from backend.agents.profile_defaults import _dialect_hints_for_target
    target_db_type: str | None = None
    if target_connection_id is not None and connection_metadata:
        for c in connection_metadata:
            if c.id == target_connection_id:
                target_db_type = getattr(c, "db_type", None)
                break
    suffix += _dialect_hints_for_target(org_id, target_db_type)

    return suffix
