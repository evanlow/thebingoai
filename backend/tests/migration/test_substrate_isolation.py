"""End-to-end checks that a migrated SQLite connection owns an isolated set of
DataPlane tables, and that the metadata left behind names what the plane holds.

Uses a real `LocalFilesystemDataPlane` over a tmp dir — the point of these tests
is what actually lands on disk and comes back out of a query, which a mocked
plane cannot show.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from backend.data_plane.local_filesystem import LocalFilesystemDataPlane
from backend.data_plane.scope import OwnerScope
from backend.migration.substrate import migrate_connection

from .test_substrate import _make_fresh_db, _make_mock_connection, make_sqlite_db


@pytest.fixture
def plane(tmp_path):
    return LocalFilesystemDataPlane(root_path=str(tmp_path))


def _migrate(connection, blob, plane):
    """Run a migration of `blob` for `connection` against a real plane."""
    db = _make_fresh_db(connection=connection, journal=None)
    with patch("backend.services.object_storage.download_bytes", return_value=blob), \
         patch("backend.services.object_storage.delete_object"), \
         patch("backend.services.data_plane_service.get_default_plane", return_value=plane):
        return migrate_connection(connection.id, dry_run=False, db=db)


def test_two_sqlite_uploads_by_one_user_do_not_overwrite_each_other(plane):
    """Both connections share an owner scope, and both .sqlite files contain an
    `orders` table. Without per-connection table names the second migration
    replaces the first one's data."""
    north = _make_mock_connection(connection_id=1, dataset_table_name="legacy/north.sqlite")
    south = _make_mock_connection(connection_id=2, dataset_table_name="legacy/south.sqlite")
    assert OwnerScope.from_connection(north) == OwnerScope.from_connection(south)

    assert _migrate(north, make_sqlite_db({"orders": [{"city": "oslo"}]}), plane).status == "migrated"
    assert _migrate(south, make_sqlite_db({"orders": [{"city": "lima"}]}), plane).status == "migrated"

    scope = OwnerScope.from_connection(north)
    assert sorted(plane.list_tables(scope)) == ["sqlite_1_orders", "sqlite_2_orders"]
    assert plane.query(scope, "SELECT city FROM sqlite_1_orders").rows[0][0] == "oslo"
    assert plane.query(scope, "SELECT city FROM sqlite_2_orders").rows[0][0] == "lima"


def test_migrated_connector_sees_only_its_own_tables(plane):
    """`get_tables` on a shared owner scope must not leak other connections'
    tables into this connection's schema discovery."""
    from backend.connectors.data_plane import DataPlaneConnector

    one = _make_mock_connection(connection_id=1, dataset_table_name="legacy/one.sqlite")
    two = _make_mock_connection(connection_id=2, dataset_table_name="legacy/two.sqlite")
    _migrate(one, make_sqlite_db({"orders": [{"city": "oslo"}]}), plane)
    _migrate(two, make_sqlite_db({"invoices": [{"city": "lima"}]}), plane)

    scope = OwnerScope.from_connection(one)
    assert DataPlaneConnector(plane, scope, "sqlite_1_").get_tables() == ["sqlite_1_orders"]
    assert DataPlaneConnector(plane, scope, "sqlite_2_").get_tables() == ["sqlite_2_invoices"]
    # No prefix (a plane-as-a-connection, or a pre-prefix migration) still sees everything.
    assert len(DataPlaneConnector(plane, scope).get_tables()) == 2


def _blob_with_awkward_columns() -> bytes:
    """A .sqlite whose column names BigQuery rejects verbatim."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        path = tmp.name
    try:
        conn = sqlite3.connect(path)
        try:
            conn.execute('CREATE TABLE orders ("order-id" TEXT PRIMARY KEY, "Order Total" REAL)')
            conn.execute('INSERT INTO orders VALUES (?, ?)', ("a1", 12.5))
            conn.commit()
        finally:
            conn.close()
        with open(path, "rb") as f:
            return f.read()
    finally:
        os.unlink(path)


def test_sanitized_columns_are_reflected_in_schema_and_data_context(plane):
    """The dashboard agent generates SQL from `data_context`, so a column the
    plane renamed on write has to be renamed there too — otherwise every
    generated query names a column that doesn't exist."""
    connection = _make_mock_connection(dataset_table_name="legacy/orders.sqlite")
    connection.schema_json = {
        "schemas": {"main": {"tables": {"orders": {"row_count": 1, "columns": [
            {"name": "order-id", "type": "TEXT", "primary_key": True},
            {"name": "Order Total", "type": "DOUBLE PRECISION", "primary_key": False},
        ]}}}},
        "table_names": ["orders"],
        "relationships": [],
    }
    connection.data_context = {
        "tables": {"orders": {"schema": "main", "rowCount": 1, "columns": {
            "order-id": {"type": "TEXT", "role": "key"},
            "Order Total": {"type": "DOUBLE PRECISION", "role": "measure"},
        }}},
        "relationships": [
            {"from": "orders.order-id", "to": "orders.order-id", "inferred": True},
        ],
    }

    assert _migrate(connection, _blob_with_awkward_columns(), plane).status == "migrated"

    table = connection.schema_json["schemas"]["main"]["tables"]["sqlite_1_orders"]
    assert [c["name"] for c in table["columns"]] == ["order_id", "Order_Total"]
    # Re-discovery from Parquet would have lost this — Parquet carries no PK.
    assert table["columns"][0]["primary_key"] is True
    assert connection.schema_json["table_names"] == ["sqlite_1_orders"]

    context_table = connection.data_context["tables"]["sqlite_1_orders"]
    assert set(context_table["columns"]) == {"order_id", "Order_Total"}
    rel = connection.data_context["relationships"][0]
    assert rel["from"] == "sqlite_1_orders.order_id"
    assert rel["inferred"] is True  # non-endpoint keys survive the rewrite

    # The names in data_context are the names the plane answers to.
    scope = OwnerScope.from_connection(connection)
    result = plane.query(scope, 'SELECT "Order_Total" FROM sqlite_1_orders')
    assert result.rows[0][0] == 12.5


def test_journal_records_the_prefix(plane):
    """The connector reads the prefix back off the journal to scope its table
    list; NULL there means a pre-prefix migration with bare table names."""
    connection = _make_mock_connection(dataset_table_name="legacy/orders.sqlite")
    db = _make_fresh_db(connection=connection, journal=None)
    added = []
    db.add = MagicMock(side_effect=added.append)

    with patch("backend.services.object_storage.download_bytes",
               return_value=make_sqlite_db({"orders": [{"city": "oslo"}]})), \
         patch("backend.services.object_storage.delete_object"), \
         patch("backend.services.data_plane_service.get_default_plane", return_value=plane):
        migrate_connection(connection.id, dry_run=False, db=db)

    journals = [o for o in added if hasattr(o, "dataplane_table_prefix")]
    assert journals and journals[0].dataplane_table_prefix == "sqlite_1_"
