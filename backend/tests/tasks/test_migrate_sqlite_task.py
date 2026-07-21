"""migrate_sqlite_connection loads the connection then delegates to the shared
migrate_connection_with_plane helper, and retries on a failed result."""
from unittest.mock import MagicMock, patch


def _session_local_yielding(conn):
    """A SessionLocal stand-in whose context manager yields a db whose
    query(...).filter(...).first() returns `conn`."""
    session_local = MagicMock()
    db = session_local.return_value.__enter__.return_value
    db.query.return_value.filter.return_value.first.return_value = conn
    return session_local


def test_migrate_sqlite_connection_delegates_to_helper():
    from backend.tasks import migration_tasks

    conn = MagicMock(id=42)
    result = MagicMock(status="migrated", new_dataplane_table="listings", rows_migrated=10)

    with patch("backend.database.session.SessionLocal", _session_local_yielding(conn)), \
         patch("backend.models.database_connection.DatabaseConnection", MagicMock()), \
         patch("backend.migration.substrate.migrate_connection_with_plane", return_value=result) as migrate:
        migration_tasks.migrate_sqlite_connection(42)

    migrate.assert_called_once()
    args, kwargs = migrate.call_args
    assert args[0] is conn
    assert "db" in kwargs


def test_migrate_sqlite_connection_missing_connection_is_noop():
    from backend.tasks import migration_tasks

    with patch("backend.database.session.SessionLocal", _session_local_yielding(None)), \
         patch("backend.models.database_connection.DatabaseConnection", MagicMock()), \
         patch("backend.migration.substrate.migrate_connection_with_plane") as migrate:
        migration_tasks.migrate_sqlite_connection(999)

    migrate.assert_not_called()


def test_migrate_sqlite_connection_failed_status_retries():
    from backend.tasks import migration_tasks

    conn = MagicMock(id=7)
    result = MagicMock(
        status="failed", new_dataplane_table=None, rows_migrated=0, error_message="boom",
    )

    class _Retry(Exception):
        pass

    with patch("backend.database.session.SessionLocal", _session_local_yielding(conn)), \
         patch("backend.models.database_connection.DatabaseConnection", MagicMock()), \
         patch("backend.migration.substrate.migrate_connection_with_plane", return_value=result), \
         patch.object(migration_tasks.migrate_sqlite_connection, "retry", side_effect=_Retry) as retry:
        try:
            migration_tasks.migrate_sqlite_connection(7)
            assert False, "expected a failed result to trigger self.retry"
        except _Retry:
            pass

    retry.assert_called_once()
