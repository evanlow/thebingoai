"""Celery task for migrating a SQLite connection's blob into the DataPlane as Parquet."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="migrate_sqlite_connection", bind=True, max_retries=2)
def migrate_sqlite_connection(self, connection_id: int):
    from backend.database.session import SessionLocal
    from backend.migration.substrate import migrate_connection
    from backend.services.data_plane_service import get_plane_for_connection
    from backend.models.database_connection import DatabaseConnection

    with SessionLocal() as db:
        connection = db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id
        ).first()
        if connection is None:
            logger.warning("migrate_sqlite_connection: connection %s not found", connection_id)
            return
        # Resolve the plane first (triggers provision-on-miss under lockdown),
        # mirroring seed.py before it calls migrate_connection.
        get_plane_for_connection(connection)
        result = migrate_connection(connection_id, db=db)

    logger.info(
        "migrate_sqlite_connection: connection=%s status=%s table=%s rows=%s",
        connection_id, result.status, result.new_dataplane_table, result.rows_migrated,
    )
    if result.status == "failed":
        logger.error("SQLite migration failed for %s: %s", connection_id, result.error_message)
