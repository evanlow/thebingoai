"""Celery task for LLM-drafted glossary descriptions.

On-demand only (UI "Generate docs" button, never automatic — costs LLM calls).
For each requested table it sends the profiled schema (column name/type/role +
derived stats; real values only when the org privacy flag is off) to the LLM and
writes back draft glossary entries ``{source: "llm", status: "draft"}``. Drafts
are shown in the catalog for review but never reach agent prompts until a human
confirms them (``merge_semantics_into_context`` only merges confirmed entries).

Human-authored or already-confirmed entries are never overwritten.

Progress is tracked in Redis (``semantic_gen:{connection_id}``) rather than a DB
column, because the ``connection_semantic_layers`` row may not exist yet.
"""

import asyncio
import json
import logging
import re

import redis
from celery import shared_task

from backend.config import settings

logger = logging.getLogger(__name__)

_redis = redis.from_url(settings.redis_url, decode_responses=True)
_STATUS_PREFIX = "semantic_gen:"
_STATUS_TTL = 3600  # 1h

# Cap per-table columns sent to the LLM (mirrors table_profiler MAX_COLUMNS).
_MAX_COLUMNS = 30


def _status_key(connection_id: int) -> str:
    return f"{_STATUS_PREFIX}{connection_id}"


def set_generation_status(connection_id: int, **fields) -> None:
    _redis.setex(_status_key(connection_id), _STATUS_TTL, json.dumps(fields))


def get_generation_status(connection_id: int) -> dict:
    raw = _redis.get(_status_key(connection_id))
    if not raw:
        return {"status": "idle"}
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return {"status": "idle"}


def _build_prompt(table_name: str, tdata: dict, meta_only: bool, existing_glossary: dict) -> str:
    """One prompt per table describing its columns, asking for JSON descriptions."""
    row_count = tdata.get("rowCount")
    lines = [
        f"You are documenting a database table for a business-intelligence catalog.",
        f'Table: "{table_name}"' + (f" ({row_count} rows)" if row_count is not None else ""),
        "",
        "Columns (name, type, role, stats):",
    ]
    columns = tdata.get("columns") or {}
    for cname, cdata in list(columns.items())[:_MAX_COLUMNS]:
        parts = [f"- {cname}", str(cdata.get("type", "?"))]
        role = cdata.get("role")
        if role:
            parts.append(role)
        # Existing human/confirmed meaning gives the model helpful context.
        key = f"{table_name}.{cname}"
        entry = existing_glossary.get(key) or {}
        if entry.get("description") and (entry.get("source") == "human" or entry.get("status") == "confirmed"):
            parts.append(f'known meaning: "{entry["description"]}"')
        elif cdata.get("description"):
            parts.append(f'db comment: "{cdata["description"]}"')
        # Real values only when privacy flag off and column not marked sensitive.
        if not meta_only and not entry.get("sensitive"):
            if cdata.get("min") is not None and cdata.get("max") is not None:
                parts.append(f"range {cdata['min']}–{cdata['max']}")
            top = cdata.get("topValues")
            if top:
                parts.append("e.g. " + ", ".join(str(v) for v in top[:3]))
        cardinality = cdata.get("cardinality")
        if cardinality is not None:
            parts.append(f"{cardinality} distinct")
        lines.append("  ".join(parts))

    lines += [
        "",
        "For each column infer a concise business meaning and a human-friendly "
        "display name. Expand cryptic abbreviations (e.g. 'cust_nm' -> 'Customer "
        "Name', 'of' -> could be 'Offensive Fouls' in a sports table). If a column "
        "is genuinely ambiguous, give your best guess.",
        "",
        "Return ONLY a JSON object with this exact structure (no markdown, no extra text):",
        '{"table_description": "...", "columns": {"<column_name>": '
        '{"description": "...", "display_name": "..."}}}',
    ]
    return "\n".join(lines)


def _call_llm(prompt: str) -> dict:
    """Run one LLM chat call and parse a JSON object from the response."""
    from backend.llm.factory import get_provider

    provider = get_provider(settings.default_llm_provider)
    messages = [{"role": "user", "content": prompt}]
    response = asyncio.run(provider.chat(messages, temperature=0.2))
    content = response.strip()
    if content.startswith("```"):
        content = re.sub(r"^```[a-z]*\n?", "", content)
        content = re.sub(r"\n?```$", "", content)
        content = content.strip()
    return json.loads(content)


@shared_task(name="generate_glossary_drafts")
def generate_glossary_drafts(connection_id: int, table_names: list):
    """Draft glossary descriptions for the given tables via the LLM."""
    from backend.database.session import SessionLocal
    from backend.models.database_connection import DatabaseConnection
    from backend.services.connection_context import load_connection_context
    from backend.services.semantic_layer import load_semantic_layer, upsert_semantic_layer
    from backend.services.llm_privacy import metadata_only_for_connection

    db = SessionLocal()
    try:
        connection = db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id
        ).first()
        if not connection:
            set_generation_status(connection_id, status="failed", error="Connection not found")
            return

        context = load_connection_context(db, connection_id)
        if not context:
            set_generation_status(connection_id, status="failed", error="Connection not profiled yet")
            return

        meta_only = metadata_only_for_connection(connection)
        tables = context.get("tables") or {}
        existing = (load_semantic_layer(db, connection_id) or {}).get("glossary") or {}
        glossary = dict(existing)

        total = len(table_names)
        set_generation_status(connection_id, status="running", progress=f"0/{total}")

        for i, tname in enumerate(table_names):
            tdata = tables.get(tname)
            if not tdata:
                logger.warning("generate_glossary_drafts: table %s not in context", tname)
                set_generation_status(connection_id, status="running", progress=f"{i + 1}/{total}")
                continue
            try:
                prompt = _build_prompt(tname, tdata, meta_only, existing)
                parsed = _call_llm(prompt)
                _merge_drafts(glossary, tname, tdata, parsed, existing)
            except Exception as exc:  # one bad table must not kill the run
                logger.warning("generate_glossary_drafts: table %s failed: %s", tname, exc)
            set_generation_status(connection_id, status="running", progress=f"{i + 1}/{total}")

        upsert_semantic_layer(db, connection_id, glossary=glossary)
        db.commit()
        set_generation_status(connection_id, status="done", progress=f"{total}/{total}")
        logger.info("generate_glossary_drafts: connection %d done (%d tables)", connection_id, total)
    except Exception as exc:
        logger.exception("generate_glossary_drafts: connection %d failed", connection_id)
        set_generation_status(connection_id, status="failed", error=str(exc))
    finally:
        db.close()


def _merge_drafts(glossary: dict, table_name: str, tdata: dict, parsed: dict, existing: dict) -> None:
    """Write LLM drafts into ``glossary`` without overwriting human/confirmed entries."""
    def _keep(entry: dict) -> bool:
        return bool(entry) and (entry.get("source") == "human" or entry.get("status") == "confirmed")

    table_desc = parsed.get("table_description")
    if table_desc and not _keep(existing.get(table_name) or {}):
        glossary[table_name] = {
            "description": table_desc,
            "source": "llm",
            "status": "draft",
        }

    valid_cols = set(tdata.get("columns") or {})
    for cname, cfields in (parsed.get("columns") or {}).items():
        if cname not in valid_cols or not isinstance(cfields, dict):
            continue
        key = f"{table_name}.{cname}"
        if _keep(existing.get(key) or {}):
            continue
        desc = cfields.get("description")
        display = cfields.get("display_name")
        if not desc and not display:
            continue
        entry = {"source": "llm", "status": "draft"}
        if desc:
            entry["description"] = desc
        if display:
            entry["display_name"] = display
        glossary[key] = entry
