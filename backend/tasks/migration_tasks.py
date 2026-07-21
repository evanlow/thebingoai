"""Celery task for migrating a SQLite connection's blob into the DataPlane as Parquet."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


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
