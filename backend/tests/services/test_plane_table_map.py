"""Tests for `plane_table_map` — source-table → pipeline target_table mapping
used by the DuckDB-over-DataPlane read/warm paths to resolve widget SQL written
against source table names to their materialized plane tables."""
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.services.data_plane_service import plane_table_map


def _db(pipelines):
    """Fake Session whose Pipeline query `.all()` returns *pipelines*."""
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = pipelines
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
