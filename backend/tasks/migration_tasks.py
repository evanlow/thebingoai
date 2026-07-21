"""Celery task for migrating a SQLite connection's blob into the DataPlane as Parquet."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def enqueue_profile_then_migrate(connection_id: int) -> None:
    """Kick profiling, then migrate the SQLite blob → Parquet after profiling
    *terminates* (success or final failure). Wired as both the success ``link``
    and the failure ``link_error`` so a failed profiling run still migrates;
    exactly one fires (retries don't trigger link_error). Immutable ``.si``
    ignores profiling's return/error args, so migration receives just the id."""
    from backend.tasks.profiling_tasks import profile_connection
    migrate_sig = migrate_sqlite_connection.si(connection_id)
    prof_sig = profile_connection.s(connection_id)
    prof_sig.link(migrate_sig)
    prof_sig.link_error(migrate_sig)
    prof_sig.delay()


def _refresh_schema_from_plane(db, connection) -> None:
    """Re-discover the schema now that the DataPlane, not the blob, is the source.

    The plane may rename columns on write (BigQuery rejects e.g. `Order Total`),
    so the schema cached at upload time can name columns the migrated table no
    longer has — every query generated from it would then fail. Post-migration
    `get_connector_for_connection` routes to `DataPlaneConnector`, so
    re-discovery reads the real column names.

    Non-fatal: the blob is already deleted, so a failure here must not retry the
    migration. `profile_connection` rediscovers the schema on its next run.
    """
    from backend.tasks.profiling_tasks import _discover_and_save_schema
    try:
        _discover_and_save_schema(db, connection)
    except Exception as exc:
        logger.warning(
            "migrate_sqlite_connection: post-migration schema refresh failed for %s: %s",
            connection.id, exc, exc_info=True,
        )


@shared_task(name="migrate_sqlite_connection", bind=True, max_retries=2)
def migrate_sqlite_connection(self, connection_id: int):
    from backend.database.session import SessionLocal
    from backend.migration.substrate import migrate_connection_with_plane
    from backend.models.database_connection import DatabaseConnection

    try:
        with SessionLocal() as db:
            # ponytail: connection re-queried inside migrate_connection; the extra
            # PK lookup here (needed to resolve the plane) is cheap on a one-shot
            # upload.
            connection = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == connection_id
            ).first()
            if connection is None:
                logger.warning("migrate_sqlite_connection: connection %s not found", connection_id)
                return
            result = migrate_connection_with_plane(connection, db=db)
            if result.status == "migrated":
                _refresh_schema_from_plane(db, connection)
    except Exception as exc:  # provisioning race, storage blip, etc.
        logger.error(
            "migrate_sqlite_connection: connection=%s raised; retrying: %s", connection_id, exc,
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

    logger.info(
        "migrate_sqlite_connection: connection=%s status=%s table=%s rows=%s",
        connection_id, result.status, result.new_dataplane_table, result.rows_migrated,
    )
    if result.status == "failed":
        logger.error("SQLite migration failed for %s: %s", connection_id, result.error_message)
        raise self.retry(
            exc=RuntimeError(result.error_message or "migration failed"),
            countdown=60 * (2 ** self.request.retries),
        )
