"""Semantic layer — load/save + read-time merge of human-curated meaning.

The semantic layer (glossary / relationships / definitions) lives in its own
table (`connection_semantic_layers`) so it survives the full rebuild of
`database_connections.data_context` on every profiling run. This module overlays
it onto the profiled context at read time via ``merge_semantics_into_context``.

Description precedence (highest first): human > confirmed-LLM > DB comment. Draft
(unconfirmed) LLM glossary entries are returned to the UI but are NEVER merged
into agent-facing context — only ``status == "confirmed"`` entries win.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load_semantic_layer(db, connection_id: int) -> Optional[Dict[str, Any]]:
    """Return ``{glossary, relationships, definitions}`` or None if absent."""
    from backend.models.connection_semantics import ConnectionSemanticLayer

    row = (
        db.query(ConnectionSemanticLayer)
        .filter(ConnectionSemanticLayer.connection_id == connection_id)
        .first()
    )
    if row is None:
        return None
    return {
        "glossary": row.glossary or {},
        "relationships": row.relationships_data or [],
        "definitions": row.definitions or [],
    }


def upsert_semantic_layer(
    db,
    connection_id: int,
    *,
    glossary: Optional[Dict[str, Any]] = None,
    relationships: Optional[List[Dict[str, Any]]] = None,
    definitions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Create or update a connection's semantic layer (section-level replace).

    Only the sections passed (non-None) are replaced; others are left as-is.
    Caller commits the session.
    """
    from backend.models.connection_semantics import ConnectionSemanticLayer

    row = (
        db.query(ConnectionSemanticLayer)
        .filter(ConnectionSemanticLayer.connection_id == connection_id)
        .first()
    )
    if row is None:
        row = ConnectionSemanticLayer(
            connection_id=connection_id, glossary={}, relationships_data=[], definitions=[]
        )
        db.add(row)

    if glossary is not None:
        row.glossary = glossary
    if relationships is not None:
        row.relationships_data = relationships
    if definitions is not None:
        row.definitions = definitions

    db.flush()
    return {
        "glossary": row.glossary or {},
        "relationships": row.relationships_data or [],
        "definitions": row.definitions or [],
    }


# ---------------------------------------------------------------------------
# Read-time merge (pure)
# ---------------------------------------------------------------------------

def _resolve_description(glossary_entry: Optional[Dict[str, Any]], db_comment: Optional[str]) -> Optional[str]:
    """Description precedence: human > confirmed-LLM > DB comment.

    Draft LLM entries do NOT contribute a description (only display in UI).
    """
    if glossary_entry:
        source = glossary_entry.get("source")
        status = glossary_entry.get("status")
        desc = glossary_entry.get("description")
        if desc and (source == "human" or status == "confirmed"):
            return desc
    return db_comment or None


def merge_semantics_into_context(
    context: Optional[Dict[str, Any]],
    semantics: Optional[Dict[str, Any]],
    schema_json: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Overlay the semantic layer onto a profiled data_context (non-destructive).

    Returns a deep copy of ``context`` with, per column: resolved ``description``
    (precedence above), ``displayName``, and ``sensitive`` flags; relationships =
    (existing FK/naming-inferred − rejected) + confirmed/data entries; and a
    top-level ``definitions`` list. ``schema_json`` is accepted for signature
    stability (table comments already flow into context.description) and unused today.
    """
    if context is None:
        return None
    out = copy.deepcopy(context)
    semantics = semantics or {}
    glossary: Dict[str, Any] = semantics.get("glossary") or {}
    sem_rels: List[Dict[str, Any]] = semantics.get("relationships") or []
    definitions: List[Dict[str, Any]] = semantics.get("definitions") or []

    # --- columns: descriptions, display names, sensitivity ------------------
    for tname, tdata in (out.get("tables") or {}).items():
        # table-level glossary entry (description only)
        t_entry = glossary.get(tname)
        t_desc = _resolve_description(t_entry, tdata.get("description"))
        if t_desc:
            tdata["description"] = t_desc

        for cname, cdata in (tdata.get("columns") or {}).items():
            key = f"{tname}.{cname}"
            entry = glossary.get(key)
            desc = _resolve_description(entry, cdata.get("description"))
            if desc:
                cdata["description"] = desc
            if entry:
                if entry.get("display_name"):
                    cdata["displayName"] = entry["display_name"]
                if entry.get("sensitive"):
                    cdata["sensitive"] = True

    # --- relationships: drop rejected, add confirmed/data -------------------
    rejected = {
        (r.get("from"), r.get("to"))
        for r in sem_rels
        if r.get("status") == "rejected"
    }
    base_rels = [
        r for r in (out.get("relationships") or [])
        if (r.get("from"), r.get("to")) not in rejected
    ]
    existing_pairs = {(r.get("from"), r.get("to")) for r in base_rels}
    for r in sem_rels:
        if r.get("status") == "rejected":
            continue
        pair = (r.get("from"), r.get("to"))
        if pair not in existing_pairs:
            base_rels.append(r)
            existing_pairs.add(pair)
    out["relationships"] = base_rels

    # --- business definitions ----------------------------------------------
    if definitions:
        out["definitions"] = definitions

    return out


def load_enriched_context(db, connection_id: int) -> Optional[Dict[str, Any]]:
    """Load the profiled data_context and overlay the semantic layer.

    Returns None when no data_context exists yet (unprofiled connection).
    """
    from backend.services.connection_context import load_connection_context

    context = load_connection_context(db, connection_id)
    if context is None:
        return None
    semantics = load_semantic_layer(db, connection_id)
    return merge_semantics_into_context(context, semantics)
