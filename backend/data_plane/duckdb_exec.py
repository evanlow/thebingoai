"""Shared DuckDB execution helper for DataPlane readers.

Both `LocalFilesystemDataPlane` (dev) and the GCS-httpfs reader (prod, Phase 2)
register views then run already-DuckDB SQL through this one path, so param
binding and the row-cap/truncation parity stay identical across planes.
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

from backend.connectors.base import QueryResult

logger = logging.getLogger(__name__)

# DuckDB named placeholder `$name` (name starts with a letter/underscore — `$1`
# numbered-positional placeholders are deliberately excluded).
_NAMED_PARAM_RE = re.compile(r"\$[A-Za-z_]\w*")


def apply_memory_guardrails(conn) -> None:
    """Cap per-connection memory and enable disk spill.

    DuckDB's default memory_limit is ~80% of system RAM *per connection*;
    serving opens one connection per request, so concurrent reads can OOM the
    container. Large aggregations spill to `duckdb_temp_directory` instead of
    failing. Applied at every `duckdb.connect()` site; failures are logged and
    ignored so a bad setting never breaks serving.
    """
    from backend.config import settings

    try:
        os.makedirs(settings.duckdb_temp_directory, exist_ok=True)
        conn.execute(f"SET memory_limit='{settings.duckdb_memory_limit}'")
        conn.execute(f"SET temp_directory='{settings.duckdb_temp_directory}'")
    except Exception:
        logger.warning("Failed to apply DuckDB memory guardrails", exc_info=True)


def build_scope_view_sql(
    table: str,
    source_glob: str,
    unique_key: tuple[str, ...] | None = None,
) -> str:
    """`CREATE OR REPLACE VIEW` DDL exposing a table's Parquet under its bare name.

    Shared by every DuckDB-backed reader (`LocalFilesystemDataPlane` dev,
    `GCSDuckDBReader` prod) so the view definition lives in one place.

    Without *unique_key* the view is a raw union over all `dt=` partitions (the
    historical behavior). With *unique_key* it dedups to the latest `dt=`
    snapshot per key — the DuckDB analog of `BigQueryGCSPlane`'s silver view
    (`ROW_NUMBER() OVER (PARTITION BY <key> ORDER BY dt DESC) = 1`).
    """
    safe = table.replace("-", "_")
    read = f"read_parquet('{source_glob}', hive_partitioning=true)"
    if not unique_key:
        return f"CREATE OR REPLACE VIEW {safe} AS SELECT * FROM {read}"
    keys = ", ".join(f'"{k}"' for k in unique_key)
    return (
        f"CREATE OR REPLACE VIEW {safe} AS "
        f"SELECT * EXCLUDE (dt, _rn) FROM ("
        f"SELECT *, ROW_NUMBER() OVER (PARTITION BY {keys} ORDER BY dt DESC) AS _rn "
        f"FROM {read}) WHERE _rn = 1"
    )


def run_duckdb_query(conn, sql: str, params: dict[str, Any] | None = None) -> QueryResult:
    """Execute *sql* on *conn*, binding *params* and capping rows.

    - Named `$name` placeholders (inject_filters duckdb dialect) bind from the
      dict by name; legacy positional `?` / `$1` bind values in order.
    - Caps at `settings.max_query_rows` (fetch one extra to flag truncation),
      matching the source-DB connectors (`base.py`).
    """
    from backend.config import settings

    start = time.time()
    if params:
        if _NAMED_PARAM_RE.search(sql):
            rel = conn.execute(sql, params)
        else:
            rel = conn.execute(sql, list(params.values()))
    else:
        rel = conn.execute(sql)

    columns = [desc[0] for desc in rel.description]
    max_rows = settings.max_query_rows
    rows = rel.fetchmany(max_rows + 1)
    truncated = len(rows) > max_rows
    if truncated:
        rows = rows[:max_rows]

    return QueryResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        execution_time_ms=(time.time() - start) * 1000,
        truncated=truncated,
    )
