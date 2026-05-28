"""Shared dlt-source helper for SQL connectors (postgres, mysql).

Builds a `dlt.sources.sql_database` source from a `DatabaseConnection`.
Per-connector modules expose `dlt_source_for(connection, extraction_config)`
that delegates here with the right SQLAlchemy URL drivername.

Incremental extracts: when `extraction_config.incremental_keys` is set, the
matching table resource gets a `dlt.sources.incremental` cursor applied via
`apply_hints`, so dlt extracts only rows where `cursor_col > last_seen_value`
(persisted in `dlt_pipeline_states`). An optional `backfill_since` floors the
initial cursor value for first-ingest / "Load history" runs.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SqlExtractionConfig(BaseModel):
    """Optional pipeline-level filters for SQL ingestion."""

    tables: Optional[list[str]] = None  # None → all tables in schema
    schema: Optional[str] = None         # None → connector default
    # `target_table` -> cursor column. Populated by `runner.run_pipeline` from
    # `Pipeline.incremental_key` when mode='incremental'. Keyed by target table
    # (the dlt resource name) so a single source can drive multiple tables with
    # distinct cursors.
    incremental_keys: Optional[dict[str, str]] = None
    # Initial cursor value for the first-ingest / manual-backfill run. Applies
    # to every resource with an `incremental_keys` entry. Subsequent cron runs
    # ignore this — dlt's persisted state takes precedence.
    backfill_since: Optional[datetime] = None


def build_sqlalchemy_url(drivername: str, connection) -> str:
    """Compose a SQLAlchemy URL from a `DatabaseConnection` row."""
    from sqlalchemy.engine.url import URL

    return URL.create(
        drivername=drivername,
        username=connection.username,
        password=connection.password,
        host=connection.host,
        port=connection.port,
        database=connection.database,
    ).render_as_string(hide_password=False)


def sql_dlt_source(drivername: str, connection, extraction_config: Optional[dict] = None):
    """Return a dlt source pulling from the given SQL `connection`."""
    import dlt
    from dlt.sources.sql_database import sql_database

    cfg = SqlExtractionConfig(**(extraction_config or {}))
    url = build_sqlalchemy_url(drivername, connection)

    kwargs: dict = {"credentials": url}
    if cfg.schema:
        kwargs["schema"] = cfg.schema
    if cfg.tables:
        kwargs["table_names"] = cfg.tables

    source = sql_database(**kwargs)

    if cfg.incremental_keys:
        # Apply a per-resource incremental cursor. dlt names the resource after
        # the source table name (the dict key matches `Pipeline.target_table`,
        # which `_build_sql_pipeline_templates` derives from the source table —
        # so the keys here should match the dlt resource names emitted by
        # `sql_database`).
        for table, cursor_col in cfg.incremental_keys.items():
            try:
                resource = source.resources.get(table)
                if resource is None:
                    continue
                resource.apply_hints(
                    incremental=dlt.sources.incremental(
                        cursor_col,
                        initial_value=cfg.backfill_since,
                    ),
                )
            except Exception:
                # apply_hints failures shouldn't break the run — dlt will fall
                # back to a full extract for this resource.
                continue

    return source
