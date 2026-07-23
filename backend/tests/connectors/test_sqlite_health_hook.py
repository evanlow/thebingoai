"""_check_sqlite_health is the `on_test` hook behind POST /connections/{id}/test.

It must return the {success, message} mapping the route splats into
ConnectionTestResponse, and must route migrated connections at the DataPlane —
migration deletes the blob and clears dataset_table_name, so a blob-only check
reports every migrated connection as broken.
"""
from unittest.mock import MagicMock, patch


def _session_local_yielding(journal):
    session_local = MagicMock()
    db = session_local.return_value.__enter__.return_value
    db.query.return_value.filter.return_value.first.return_value = journal
    return session_local


def test_returns_mapping_not_bool():
    """The route does ConnectionTestResponse(**result) — a bool raises TypeError."""
    from backend.connectors.factory import _check_sqlite_health

    conn = MagicMock(id="c1", dataset_table_name="orgs/1/db.sqlite")
    with patch("backend.database.session.SessionLocal", _session_local_yielding(None)), \
         patch("backend.services.sqlite_blob_storage.blob_exists", return_value=True):
        result = _check_sqlite_health(conn)

    assert isinstance(result, dict)
    assert result["success"] is True
    assert isinstance(result["message"], str)


def test_migrated_connection_tests_the_data_plane():
    from backend.connectors.factory import _check_sqlite_health

    conn = MagicMock(id="c1", dataset_table_name=None)  # post-migration state
    journal = MagicMock(status="migrated")
    with patch("backend.database.session.SessionLocal", _session_local_yielding(journal)), \
         patch("backend.connectors.factory._test_data_plane",
               return_value={"success": True, "message": "DataPlane is reachable"}) as plane_test:
        result = _check_sqlite_health(conn)

    plane_test.assert_called_once_with(conn)
    assert result["success"] is True


def test_unmigrated_connection_without_blob_fails():
    from backend.connectors.factory import _check_sqlite_health

    conn = MagicMock(id="c1", dataset_table_name=None)
    with patch("backend.database.session.SessionLocal", _session_local_yielding(None)):
        result = _check_sqlite_health(conn)

    assert result["success"] is False


def test_unmigrated_connection_with_missing_blob_fails():
    from backend.connectors.factory import _check_sqlite_health

    conn = MagicMock(id="c1", dataset_table_name="orgs/1/db.sqlite")
    with patch("backend.database.session.SessionLocal", _session_local_yielding(None)), \
         patch("backend.services.sqlite_blob_storage.blob_exists", return_value=False):
        result = _check_sqlite_health(conn)

    assert result["success"] is False
