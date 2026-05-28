"""Shared dlt-source helper for SQL connectors (postgres, mysql).

Builds a `dlt.sources.sql_database` source from a `DatabaseConnection`.
Per-connector modules expose `dlt_source_for(connection, extraction_config)`
that delegates here with the right SQLAlchemy URL drivername.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SqlExtractionConfig(BaseModel):
    """Optional pipeline-level filters for SQL ingestion."""

    tables: Optional[list[str]] = None  # None → all tables in schema
    schema: Optional[str] = None         # None → connector default
    # T-1 snapshot: when set, each run reads only rows with
    # `snapshot_date_column` < (today_utc - (snapshot_lag_days - 1)d), i.e. data
    # up to end of T-1. None → no date filter (plain full read).
    snapshot_date_column: Optional[str] = None
    snapshot_lag_days: int = 1


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
    from dlt.sources.sql_database import sql_database

    cfg = SqlExtractionConfig(**(extraction_config or {}))
    url = build_sqlalchemy_url(drivername, connection)

    kwargs: dict = {"credentials": url}
    if cfg.schema:
        kwargs["schema"] = cfg.schema
    if cfg.tables:
        kwargs["table_names"] = cfg.tables
    if cfg.snapshot_date_column:
        from datetime import datetime, timedelta, timezone

        col = cfg.snapshot_date_column
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=cfg.snapshot_lag_days - 1)

        def _t1_filter(query, table):
            # Cap the read at end of T-1 on the snapshot date column. Skip
            # silently if the column isn't present on the reflected table.
            cols = table.columns
            if col in cols.keys():
                return query.where(cols[col] < cutoff)
            return query

        kwargs["query_adapter_callback"] = _t1_filter

    return sql_database(**kwargs)
