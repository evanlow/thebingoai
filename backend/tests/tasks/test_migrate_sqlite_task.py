"""migrate_sqlite_connection resolves the plane then delegates to migrate_connection."""
from unittest.mock import MagicMock, patch


def _session_local_yielding(conn):
    """A SessionLocal stand-in whose context manager yields a db whose
    query(...).filter(...).first() returns `conn`."""
    session_local = MagicMock()
    db = session_local.return_value.__enter__.return_value
    db.query.return_value.filter.return_value.first.return_value = conn
    return session_local


def test_migrate_sqlite_connection_delegates_to_migrate_connection():
    from backend.tasks import migration_tasks

    conn = MagicMock(id=42)
    result = MagicMock(status="migrated", new_dataplane_table="listings", rows_migrated=10)

    with patch("backend.database.session.SessionLocal", _session_local_yielding(conn)), \
         patch("backend.models.database_connection.DatabaseConnection", MagicMock()), \
         patch("backend.services.data_plane_service.get_plane_for_connection") as get_plane, \
         patch("backend.migration.substrate.migrate_connection", return_value=result) as migrate:
        migration_tasks.migrate_sqlite_connection(42)

    get_plane.assert_called_once_with(conn)
    migrate.assert_called_once()
    args, kwargs = migrate.call_args
    assert args[0] == 42
    assert "db" in kwargs


def test_migrate_sqlite_connection_missing_connection_is_noop():
    from backend.tasks import migration_tasks

    with patch("backend.database.session.SessionLocal", _session_local_yielding(None)), \
         patch("backend.models.database_connection.DatabaseConnection", MagicMock()), \
         patch("backend.services.data_plane_service.get_plane_for_connection") as get_plane, \
         patch("backend.migration.substrate.migrate_connection") as migrate:
        migration_tasks.migrate_sqlite_connection(999)

    get_plane.assert_not_called()
    migrate.assert_not_called()
