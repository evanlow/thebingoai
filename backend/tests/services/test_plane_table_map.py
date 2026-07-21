"""Tests for `plane_table_map` — source-table → pipeline target_table mapping
used by the DuckDB-over-DataPlane read/warm paths to resolve widget SQL written
against source table names to their materialized plane tables."""
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.services.data_plane_service import plane_table_map


def _db(pipelines):
    """Fake Session whose Pipeline query `.all()` returns *pipelines*.

    The query is `query(...).filter(...).order_by(...).all()`; the mock returns
    *pipelines* in the order given (order_by is a no-op on the mock, so callers
    that need to assert collision precedence should pass the winning pipeline
    first).
    """
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = pipelines
    return db


def _conn():
    return SimpleNamespace(id=1)


def test_single_table_pipeline_maps():
    p = SimpleNamespace(extraction_config={"tables": ["orders"]}, target_table="acme__orders")
    assert plane_table_map(_conn(), _db([p])) == {"orders": "acme__orders"}


def test_multi_table_pipeline_skipped():
    # Ambiguous many→one mapping → skip (avoid mapping both to one target).
    p = SimpleNamespace(extraction_config={"tables": ["a", "b"]}, target_table="acme__ab")
    assert plane_table_map(_conn(), _db([p])) == {}


def test_no_pipelines_empty():
    assert plane_table_map(_conn(), _db([])) == {}


def test_key_is_lowercased():
    p = SimpleNamespace(extraction_config={"tables": ["Orders"]}, target_table="acme__orders")
    assert plane_table_map(_conn(), _db([p])) == {"orders": "acme__orders"}


def test_empty_or_missing_extraction_config_skipped():
    p1 = SimpleNamespace(extraction_config=None, target_table="acme__orders")
    p2 = SimpleNamespace(extraction_config={}, target_table="acme__orders")
    p3 = SimpleNamespace(extraction_config={"tables": []}, target_table="acme__orders")
    assert plane_table_map(_conn(), _db([p1, p2, p3])) == {}


def test_multiple_single_table_pipelines_merge():
    p1 = SimpleNamespace(extraction_config={"tables": ["orders"]}, target_table="acme__orders")
    p2 = SimpleNamespace(extraction_config={"tables": ["customers"]}, target_table="acme__customers")
    assert plane_table_map(_conn(), _db([p1, p2])) == {
        "orders": "acme__orders",
        "customers": "acme__customers",
    }


def test_collision_keeps_first_and_does_not_overwrite():
    # Two pipelines materialize the same source table to different targets.
    # The query orders enabled-first; the mock preserves list order, so the
    # first (enabled) pipeline's target must win — no silent overwrite.
    enabled = SimpleNamespace(
        extraction_config={"tables": ["orders"]}, target_table="acme__orders", enabled=True,
    )
    disabled = SimpleNamespace(
        extraction_config={"tables": ["orders"]}, target_table="stale__orders", enabled=False,
    )
    assert plane_table_map(_conn(), _db([enabled, disabled])) == {"orders": "acme__orders"}


def test_collision_same_target_is_idempotent():
    # Same source table → same target on two pipelines: not a real conflict,
    # mapping is stable and no collision warning logic trips.
    p1 = SimpleNamespace(extraction_config={"tables": ["orders"]}, target_table="acme__orders", enabled=True)
    p2 = SimpleNamespace(extraction_config={"tables": ["orders"]}, target_table="acme__orders", enabled=True)
    assert plane_table_map(_conn(), _db([p1, p2])) == {"orders": "acme__orders"}


# --- v2 model: one pipeline per connection, per-table specs on its schedules --


def _v2(specs, **kw):
    """New-model pipeline: no target_table / extraction_config; specs live on a schedule."""
    return SimpleNamespace(
        extraction_config={}, target_table=None,
        schedules=[SimpleNamespace(tables=specs)], **kw,
    )


def test_schedule_specs_map():
    p = _v2([
        {"source_table": "orders", "target_table": "acme__orders"},
        {"source_table": "customers", "target_table": "acme__customers"},
    ])
    assert plane_table_map(_conn(), _db([p])) == {
        "orders": "acme__orders",
        "customers": "acme__customers",
    }


def test_schedule_spec_disabled_excluded():
    p = _v2([
        {"source_table": "orders", "target_table": "acme__orders"},
        {"source_table": "archived", "target_table": "acme__archived", "enabled": False},
    ])
    assert plane_table_map(_conn(), _db([p])) == {"orders": "acme__orders"}


def test_schedule_spec_key_lowercased_and_partial_skipped():
    p = _v2([
        {"source_table": "Orders", "target_table": "acme__orders"},
        {"source_table": "no_target"},          # missing target_table → skip
        {"target_table": "acme__no_source"},    # missing source_table → skip
    ])
    assert plane_table_map(_conn(), _db([p])) == {"orders": "acme__orders"}


def test_legacy_pipeline_wins_over_schedule_spec():
    # Legacy row is written first by the loop; setdefault must not let a
    # schedule spec for the same source table overwrite it.
    legacy = SimpleNamespace(
        extraction_config={"tables": ["orders"]}, target_table="acme__orders", enabled=True,
    )
    v2 = _v2([{"source_table": "orders", "target_table": "other__orders"}], enabled=True)
    assert plane_table_map(_conn(), _db([legacy, v2])) == {"orders": "acme__orders"}


def test_pipeline_without_schedules_attribute_is_safe():
    # Legacy fixtures / ORM rows with no `schedules` loaded must not blow up.
    p = SimpleNamespace(extraction_config={"tables": ["orders"]}, target_table="acme__orders")
    assert plane_table_map(_conn(), _db([p])) == {"orders": "acme__orders"}
