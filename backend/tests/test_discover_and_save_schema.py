"""_discover_and_save_schema runs discovery inside the profiling job and sets
schema_json_path + table_count on the connection (moved out of the create request).

All external calls are patched, so no DB or live connector is needed.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.tasks import profiling_tasks

_SCHEMA_DATA = {
    "schemas": {"public": {"tables": {"a": {}, "b": {}}}},
    "table_names": ["a", "b", "c"],
    "relationships": [],
}


def _conn():
    return SimpleNamespace(
        id=1, name="prod", db_type="postgres",
        schema_json_path=None, schema_generated_at=None, table_count=None,
    )


def _patches(reg):
    return [
        patch("backend.connectors.factory.get_connector_for_connection",
              return_value=MagicMock()),
        patch("backend.connectors.factory.get_connector_registration", return_value=reg),
        patch("backend.services.schema_discovery.discover_schema", return_value=_SCHEMA_DATA),
        patch("backend.services.schema_discovery.augment_schema_with_pipelines",
              side_effect=lambda sd, conn: sd),
        patch("backend.services.schema_discovery.generate_schema_json",
              return_value={"schemas": _SCHEMA_DATA["schemas"]}),
        patch("backend.services.schema_discovery.save_schema_file", return_value="key/1"),
        patch("backend.services.schema_discovery.schema_key_for", return_value="key/1"),
    ]


def _run(reg):
    db = MagicMock()
    conn = _conn()
    ps = _patches(reg)
    for p in ps:
        p.start()
    try:
        schema_json = profiling_tasks._discover_and_save_schema(db, conn)
    finally:
        for p in ps:
            p.stop()
    return db, conn, schema_json


def test_sets_path_and_table_count_for_regular_connector():
    db, conn, schema_json = _run(reg=None)
    assert conn.schema_json_path == "key/1"
    assert conn.schema_generated_at is not None
    assert conn.table_count == 3  # len(table_names)
    assert schema_json == {"schemas": _SCHEMA_DATA["schemas"]}
    db.commit.assert_called_once()


def test_dataset_connector_counts_schemas_not_tables():
    reg = SimpleNamespace(card_meta_items=["dataset_count"])
    _db, conn, _sj = _run(reg=reg)
    assert conn.table_count == 1  # len(schemas), not tables


if __name__ == "__main__":
    test_sets_path_and_table_count_for_regular_connector()
    test_dataset_connector_counts_schemas_not_tables()
    print("ok")
