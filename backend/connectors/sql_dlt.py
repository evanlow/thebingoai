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


class TableSpec(BaseModel):
    """Per-table ingest config for the new-model (one-pipeline-per-connection)
    path. Each table carries its own target name, mode, cursor and dedup key."""

    source_table: str
    target_table: str
    mode: str = "full"                    # full | incremental
    incremental_key: Optional[str] = None
    unique_key: Optional[list[str]] = None


class SqlExtractionConfig(BaseModel):
    """Optional pipeline-level filters for SQL ingestion."""

    tables: Optional[list[str]] = None   # None → all tables in schema
    schema: Optional[str] = None          # None → connector default
    # New-model per-table specs. When set, takes precedence over `tables` +
    # the single `incremental_key` below: each table gets its own cursor,
    # target table name, write disposition and primary key.
    table_specs: Optional[list[TableSpec]] = None
    # dlt incremental cursor configuration. When `incremental_key` is set, the
    # resource for the matching table(s) gets `apply_hints(incremental=...)` so
    # dlt tracks a watermark and only pulls newer rows on subsequent runs.
    incremental_key: Optional[str] = None
    initial_value: Optional[str] = None   # ISO datetime/date string (first-run lower bound)
    # Exclusive upper-bound cutoff, in whole days back from the start of today
    # UTC. 1 = T-1 (exclude same-day partials), 2 = T-2, 0 = include today.
    cutoff_days: int = 1


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


def _incremental_window(cutoff_days: int, initial_value: Optional[str]):
    """Return (initial, end_value) datetimes for an incremental cursor.

    `end_value` is an EXCLUSIVE upper bound capped at the start of today UTC
    shifted back `cutoff_days - 1` whole days (default 1 → T-1), so same-day
    partials are never pulled. dlt requires an `initial_value` whenever
    `end_value` is set, so a safely-early sentinel is used when none is given.
    """
    from datetime import datetime, timedelta, timezone

    end_value = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    ) - timedelta(days=max(0, cutoff_days) - 1)
    unbounded_lower_sentinel = datetime(1900, 1, 1, tzinfo=timezone.utc)

    initial = unbounded_lower_sentinel
    if initial_value:
        try:
            initial = datetime.fromisoformat(initial_value)
            if initial.tzinfo is None:
                initial = initial.replace(tzinfo=timezone.utc)
        except ValueError:
            initial = unbounded_lower_sentinel
    return initial, end_value


def sql_dlt_source(drivername: str, connection, extraction_config: Optional[dict] = None):
    """Return a dlt source pulling from the given SQL `connection`.

    Two shapes:
      - New model: `table_specs` — each table gets its own target name, write
        disposition, primary key and (when incremental) T-1 cursor.
      - Legacy: `tables` + a single `incremental_key` applied to all of them.
    """
    from dlt.sources.sql_database import sql_database

    cfg = SqlExtractionConfig(**(extraction_config or {}))
    url = build_sqlalchemy_url(drivername, connection)

    # ---- New model: per-table specs ----
    if cfg.table_specs:
        import dlt

        source_tables = [s.source_table for s in cfg.table_specs]
        kwargs: dict = {"credentials": url, "table_names": source_tables}
        if cfg.schema:
            kwargs["schema"] = cfg.schema
        src = sql_database(**kwargs)

        initial, end_value = _incremental_window(cfg.cutoff_days, cfg.initial_value)

        for spec in cfg.table_specs:
            resource = src.resources.get(spec.source_table)
            if resource is None:
                continue
            hints: dict = {"table_name": spec.target_table}
            if spec.mode == "incremental" and spec.incremental_key:
                hints["incremental"] = dlt.sources.incremental(
                    spec.incremental_key, initial_value=initial, end_value=end_value,
                )
                if spec.unique_key:
                    hints["write_disposition"] = "merge"
                    hints["primary_key"] = tuple(spec.unique_key)
                else:
                    hints["write_disposition"] = "append"
            else:
                hints["write_disposition"] = "replace"
            resource.apply_hints(**hints)
        return src

    # ---- Legacy: shared incremental_key across `tables` ----
    kwargs = {"credentials": url}
    if cfg.schema:
        kwargs["schema"] = cfg.schema
    if cfg.tables:
        kwargs["table_names"] = cfg.tables

    src = sql_database(**kwargs)

    if cfg.incremental_key and cfg.tables:
        import dlt

        initial, end_value = _incremental_window(cfg.cutoff_days, cfg.initial_value)
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
