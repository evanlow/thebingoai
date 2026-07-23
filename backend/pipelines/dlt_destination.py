"""Custom dlt destination that routes Parquet output through the Bingo DataPlane.

Usage inside Pipeline.run():
    dest = make_dataplane_destination(plane, scope, table)
    pipeline = dlt.pipeline(pipeline_name=..., destination=dest)
    pipeline.run(source, table_name=table, write_disposition=...)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.data_plane.scope import OwnerScope

logger = logging.getLogger(__name__)


def make_dataplane_destination(
    plane,
    scope: "OwnerScope",
    table: str,
    *,
    unique_key: tuple[str, ...] | None = None,
    unique_key_by_table: dict[str, tuple[str, ...] | None] | None = None,
):
    """Return (destination, row_counter) for a dlt run.

    dlt custom destinations receive (items, table) calls.  We accumulate items
    into a PyArrow table and flush to the DataPlane on each batch.

    `unique_key` (when set) is forwarded to `plane.write_parquet` so the plane
    can register a bronze external table + silver dedup view per pipeline.

    `row_counter` is a mutable dict (`{"rows": int}`) that the destination
    increments per batch -- the caller reads it after `dlt_pipeline.run`
    finishes to record an accurate row count on the PipelineRun. dlt's
    LoadPackage stats expose only `file_size` (bytes), not row counts, so
    a closure-tracked counter is the simplest correct source.
    """
    try:
        import dlt
        import pyarrow as pa

        row_counter: dict[str, int] = {"rows": 0}

        @dlt.destination(name="dataplane", batch_size=5000)
        def _dataplane_dest(items: list[dict], table: dlt.TTableSchema) -> None:
            if not items:
                return
            table_name_from_dlt = table["name"]
            # Forward dlt's write_disposition so the plane can pick snapshot
            # vs append semantics. runner.py maps pipeline.mode='full' →
            # 'replace' and 'incremental' → 'merge'; treat anything other
            # than 'replace' as append (delta union).
            write_disposition = table.get("write_disposition", "replace")
            mode = "overwrite" if write_disposition == "replace" else "append"
            # Per-table dedup key (new model) keyed by the dlt/target table name;
            # fall back to the single closure key (legacy one-table pipelines).
            tbl_unique_key = unique_key
            if unique_key_by_table is not None:
                tbl_unique_key = unique_key_by_table.get(table_name_from_dlt, None)
            arrow_tbl = pa.Table.from_pylist(items)
            # `from_pylist` infers the column set from whichever keys this batch
            # happens to carry, so batches of one load can write Parquet files
            # with different schemas under a single external table. It also
            # makes the plane's column sanitization batch-dependent: the
            # collision suffix it appends is computed over the columns of the
            # table it is handed. Pad every batch out to the table's declared
            # columns so the whole load presents one column set.
            for col in table.get("columns") or {}:
                if col not in arrow_tbl.column_names:
                    arrow_tbl = arrow_tbl.append_column(
                        col, pa.nulls(arrow_tbl.num_rows),
                    )
            plane.write_parquet(
                scope, table_name_from_dlt, arrow_tbl,
                mode=mode, unique_key=tbl_unique_key,
            )
            row_counter["rows"] += len(items)
            logger.debug(
                "dlt_destination: wrote %d rows to DataPlane table %s (mode=%s, unique_key=%s)",
                len(items), table_name_from_dlt, mode, unique_key,
            )

        return _dataplane_dest, row_counter

    except ImportError:
        raise ImportError(
            "dlt is required for Pipeline runs. "
            "Install it with: pip install 'dlt[parquet]>=0.4'"
        )
