"""Shared dlt-source helper for SQL connectors (postgres, mysql).

Builds a `dlt.sources.sql_database` source from a `DatabaseConnection`.
Per-connector modules expose `dlt_source_for(connection, extraction_config)`
that delegates here with the right SQLAlchemy URL drivername.

When `incremental_key` is set in the extraction config, the source advances a
dlt watermark cursor on that column. The first run uses `initial_value` as the
lower bound; subsequent runs persist + advance the cursor through dlt state,
so each run only reads rows newer than the last seen watermark.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SqlExtractionConfig(BaseModel):
    """Optional pipeline-level filters for SQL ingestion."""

    tables: Optional[list[str]] = None   # None → all tables in schema
    schema: Optional[str] = None          # None → connector default
    # dlt incremental cursor configuration. When `incremental_key` is set, the
    # resource for the matching table(s) gets `apply_hints(incremental=...)` so
    # dlt tracks a watermark and only pulls newer rows on subsequent runs.
    incremental_key: Optional[str] = None
    initial_value: Optional[str] = None   # ISO datetime/date string (first-run lower bound)


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
    """Return a dlt source pulling from the given SQL `connection`.

    Applies a dlt incremental cursor on `incremental_key` (with optional
    `initial_value` first-run lower bound) when configured; otherwise returns
    a plain full-table source.
    """
    from dlt.sources.sql_database import sql_database

    cfg = SqlExtractionConfig(**(extraction_config or {}))
    url = build_sqlalchemy_url(drivername, connection)

    kwargs: dict = {"credentials": url}
    if cfg.schema:
        kwargs["schema"] = cfg.schema
    if cfg.tables:
        kwargs["table_names"] = cfg.tables

    src = sql_database(**kwargs)

    if cfg.incremental_key and cfg.tables:
        import dlt
        from datetime import datetime, timezone

        # `end_value` is an EXCLUSIVE upper bound (`cursor < end_value`). Cap
        # at the start of today UTC so same-day rows are never pulled while
        # an incremental cursor is configured.
        #   - First run with `initial_value`: pulls `[initial_value, end_value)`.
        #   - First run without `initial_value`: pulls `[epoch, end_value)` →
        #     all history up to and including T-1.
        #   - Subsequent runs: dlt advances the watermark; pulls
        #     `(last_max, end_value)` → newly visible rows from prior days only.
        # dlt requires `initial_value` to be set whenever `end_value` is set,
        # so when callers didn't supply one we default to an "unbounded lower"
        # sentinel that's safely before any real source data.
        end_value = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        unbounded_lower_sentinel = datetime(1900, 1, 1, tzinfo=timezone.utc)

        initial: datetime
        if cfg.initial_value:
            try:
                initial = datetime.fromisoformat(cfg.initial_value)
            except ValueError:
                initial = unbounded_lower_sentinel
        else:
            initial = unbounded_lower_sentinel

        for table_name in cfg.tables:
            resource = src.resources.get(table_name)
            if resource is None:
                continue
            resource.apply_hints(
                incremental=dlt.sources.incremental(
                    cfg.incremental_key,
                    initial_value=initial,
                    end_value=end_value,
                )
            )

    return src
