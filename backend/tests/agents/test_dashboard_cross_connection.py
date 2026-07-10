"""Cross-connection JOIN validation.

A widget whose SQL joins tables from two data-plane connections (same owner
scope) must validate clean against the UNION of their schemas — not just its own
connectionId's schema. Otherwise the sibling table reads as "unknown" and the
agent stubs the join with NULLs instead of writing a real JOIN.
"""
import backend.services.schema_discovery as sd
from backend.agents.dashboard_tools import _validate_widget_sql_schema


def _schema(table, cols):
    return {"schemas": {"s": {"tables": {table: {"columns": [{"name": c} for c in cols]}}}}}


def test_cross_connection_join_validates_clean(monkeypatch):
    schemas = {
        48: _schema("gsheets_48_sheet1", ["item_code", "buyer", "quantity"]),
        49: _schema("gsheets_49_sheet1", ["item_code", "item_name", "quantity", "price"]),
    }
    monkeypatch.setattr(sd, "load_schema_file", lambda cid: schemas[cid])
    # The join widget declares ONLY connectionId=48 and references gsheets_49_sheet1
    # (conn 49). Connection 49 is never a widget connectionId — it reaches
    # validation only via extra_connection_ids (the agent's available connections).
    widgets = [
        {"id": "table_1", "dataSource": {
            "connectionId": 48, "mapping": {},
            "sql": "SELECT i.item_name, s.buyer, s.quantity AS sold, i.price "
                   "FROM gsheets_48_sheet1 s "
                   "JOIN gsheets_49_sheet1 i ON s.item_code = i.item_code"}},
    ]
    # Without the sibling connection it would warn (regression guard)…
    assert _validate_widget_sql_schema(widgets)
    # …but with conn 49 in the accessible set the join validates clean.
    assert _validate_widget_sql_schema(widgets, extra_connection_ids=[49]) == []


def test_unknown_table_still_warns(monkeypatch):
    schemas = {48: _schema("gsheets_48_sheet1", ["item_code", "buyer"])}
    monkeypatch.setattr(sd, "load_schema_file", lambda cid: schemas[cid])
    widgets = [{"id": "w", "dataSource": {
        "connectionId": 48, "mapping": {},
        "sql": "SELECT x FROM totally_unknown_table"}}]
    # Merging schemas must not blind the validator to genuinely-absent tables.
    assert _validate_widget_sql_schema(widgets)
