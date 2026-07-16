"""Seed the shared Airbnb sample connection.

One canonical Parquet copy owned by a fixed system "Samples" org, surfaced
read-only to every user. Replaces the old per-user SQLite seeding — see
`ensure_shared_sample`. Per-user seeding (`seed_sample_connections`) is now a
no-op kept only so its signup-time caller stays untouched.
"""

import logging
import os
from datetime import datetime

from sqlalchemy import and_
from sqlalchemy.orm import Session

from backend.models.database_connection import DatabaseConnection

logger = logging.getLogger(__name__)

SAMPLE_DB_PATH = "/app/data/sample/airbnb_listings.sqlite"
SAMPLE_SOURCE_MARKER = "__bingo_sample__airbnb_listings"
SAMPLE_CONNECTION_NAME = "Airbnb Listings (Sample)"

# Fixed system scope for the ONE shared sample. Its default DataPlane resolves
# to a Bingo-managed shared bucket (provisioned on first plane resolution under
# lockdown; LocalFilesystemDataPlane in dev). The connection + Parquet are
# created once by `ensure_shared_sample`, then made visible to all users.
SAMPLES_ORG_ID = "00000000-0000-0000-0000-0000000005a3"
SAMPLES_USER_ID = "00000000-0000-0000-0000-0000000005a4"  # sentinel owner (User.user_id NOT NULL)
SAMPLES_USER_EMAIL = "bingo-samples-system@internal.bingo"


def shared_sample_clause():
    """SQLAlchemy predicate matching the shared-sample connection(s).

    OR this into any connection-visibility query so the single shared sample is
    listed/loadable for every user regardless of org. Read authorization is
    handled separately by the governance allowance for SAMPLES_ORG_ID.
    """
    return and_(
        DatabaseConnection.owner_scope_kind == "org",
        DatabaseConnection.owner_scope_id == SAMPLES_ORG_ID,
    )


def is_shared_sample(connection) -> bool:
    """True when *connection* is the shared, read-only sample."""
    return (
        getattr(connection, "owner_scope_kind", None) == "org"
        and getattr(connection, "owner_scope_id", None) == SAMPLES_ORG_ID
    )


def seed_sample_connections(user_id: str, db: Session) -> None:
    """Deprecated no-op. The shared sample (`ensure_shared_sample`) replaces the
    old per-user SQLite copy; new users need nothing seeded per-signup."""
    return


def ensure_shared_sample(db: Session) -> None:
    """Idempotently provision the ONE shared Airbnb sample: system org + sentinel
    user + a `sqlite` connection owned by SAMPLES_ORG_ID, migrated once to
    Parquet on the shared plane via the migration substrate. Post-migration all
    reads reroute to the DataPlane (`SqliteFileConnector.from_connection`).

    Best-effort: called at app startup; a failure here must not block boot.
    """
    if not os.path.isfile(SAMPLE_DB_PATH):
        return

    from backend.models.organization import Organization
    from backend.models.user import User
    from backend.services.data_plane_service import get_plane_for_connection

    # 1. System "Samples" org (required so provision-on-miss can load it).
    if db.get(Organization, SAMPLES_ORG_ID) is None:
        db.add(Organization(id=SAMPLES_ORG_ID, name="Bingo Samples"))
        db.commit()

    # 2. Sentinel owner user (DatabaseConnection.user_id is NOT NULL).
    if db.get(User, SAMPLES_USER_ID) is None:
        db.add(User(
            id=SAMPLES_USER_ID,
            email=SAMPLES_USER_EMAIL,
            auth_provider="system",
            org_id=SAMPLES_ORG_ID,
        ))
        db.commit()

    # 3. Drop the v1 dataset-type shared connection if present (replaced by the
    #    sqlite-type one below; its csv_<id> parquet is left orphaned, harmless).
    legacy = db.query(DatabaseConnection).filter(
        shared_sample_clause(),
        DatabaseConnection.db_type == "dataset",
    ).first()
    if legacy is not None:
        db.delete(legacy)
        db.commit()
        logger.info("Removed v1 dataset-type shared sample (connection id=%s)", legacy.id)

    # 4. The single shared connection (idempotent by marker + sentinel scope).
    connection = db.query(DatabaseConnection).filter(
        shared_sample_clause(),
        DatabaseConnection.source_filename == SAMPLE_SOURCE_MARKER,
    ).first()
    if connection is None:
        connection = DatabaseConnection(
            user_id=SAMPLES_USER_ID,
            org_id=SAMPLES_ORG_ID,
            owner_scope_kind="org",
            owner_scope_id=SAMPLES_ORG_ID,
            name=SAMPLE_CONNECTION_NAME,
            db_type="sqlite",
            host="internal",
            port=0,
            database="sqlite",
            username="sqlite",
            source_filename=SAMPLE_SOURCE_MARKER,
            dataset_table_name=SAMPLE_DB_PATH,
        )
        connection.password = "sqlite"
        connection.ssl_ca_cert = None
        db.add(connection)
        db.commit()
        db.refresh(connection)

    # 5. Publish schema JSON from the bundled file (agents/UI need columns).
    if not connection.schema_json_path:
        from backend.api.sqlite_upload import _discover_sqlite_schema
        from backend.services.schema_discovery import (
            generate_schema_json, save_schema_file, schema_key_for,
        )
        schema_data = _discover_sqlite_schema(SAMPLE_DB_PATH)
        schema_json = generate_schema_json(
            connection_id=connection.id,
            connection_name=connection.name,
            db_type="sqlite",
            schema_data=schema_data,
        )
        connection.schema_json_path = save_schema_file(schema_key_for(connection), schema_json)
        connection.schema_generated_at = datetime.utcnow()
        connection.table_count = len(schema_data["table_names"])
        db.commit()

    # 6. Resolve the shared plane first (triggers provision-on-miss under
    #    lockdown) so the migrator finds a plane to write to.
    get_plane_for_connection(connection)

    # 7. Migrate sqlite → Parquet once. Idempotent: journal status='migrated'
    #    returns "skipped"; a failed journal resets to pending on the next run.
    from backend.migration.substrate import migrate_connection
    result = migrate_connection(connection.id, db=db)
    if result.status == "failed":
        logger.warning("Shared sample migration failed: %s", result.error_message)
        return

    logger.info(
        "Shared sample ready: connection id=%s status=%s table=%s rows=%s",
        connection.id, result.status, result.new_dataplane_table, result.rows_migrated,
    )
