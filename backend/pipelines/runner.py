"""Pipeline runner — the core execute-a-Pipeline logic (Phase 2)."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Literal

logger = logging.getLogger(__name__)

PIPELINE_LOCK_TTL = 1800  # 30 minutes

# ponytail: tables per dlt run for schedule (new-model) runs. dlt's sql_database
# holds ~1 source connection PER TABLE in the chunk at once, so peak source-DB
# connections ≈ _CHUNK_SIZE × (concurrent pipeline runs, capped at the celery
# `pipelines` worker --concurrency). Keep small to avoid exhausting the source DB:
# 10 × 10 pipelines = ≤100 conns. Bigger = fewer dlt cycles (faster) but more
# connections + a failed chunk loses more tables.
_CHUNK_SIZE = 10


def compute_pipeline_fingerprint(connection_fingerprint: str | None, extraction_config: dict) -> str:
    """sha256(conn_fingerprint | canonical_json(extraction_config))."""
    canonical = json.dumps(extraction_config, sort_keys=True, separators=(",", ":"))
    raw = f"{connection_fingerprint or ''}|{canonical}"
    return hashlib.sha256(raw.encode()).hexdigest()


def run_pipeline(
    pipeline_id: str,
    triggered_by: Literal["cron", "manual", "api", "bootstrap", "manual-backfill"],
    triggered_by_user_id: str | None = None,
    backfill_since: str | None = None,
    schedule_id: str | None = None,
) -> str:
    """Execute a Pipeline; return the new pipeline_run_id.

    Steps:
    1. Acquire Redis lock keyed pipeline:run:{pipeline_id}. Skip if held.
    2. Insert PipelineRun(status='running').
    3. Enter system_context(reason='pipeline.run', scope=...).
    4. Call connector's dlt_source_for(connection, extraction_config).
    5. Build dlt destination wrapping DataPlane.
    6. dlt.run(source, destination).
    7. Update Pipeline + PipelineRun to terminal status.
    8. Publish lineage:invalidate to Redis pub/sub.
    9. Publish pipeline.run.failed event if failed.
    10. Chain profile_pipeline_output Celery task on success.
    11. Release lock.

    `backfill_since` (ISO datetime string) is the "Load history" entry point:
    overrides `extraction_config["initial_value"]` for this run only, and uses
    an ephemeral dlt `pipeline_name` so the persisted incremental cursor is
    bypassed (fresh state → `initial_value` is honored). The canonical pipeline
    state row is left untouched; merge dedup via `unique_key` handles overlap.
    """
    import uuid
    import redis as syncredis
    from datetime import datetime, timezone

    from backend.config import settings
    from backend.database.session import SessionLocal
    from backend.models.pipeline import Pipeline, PipelineRun
    from backend.models.database_connection import DatabaseConnection
    from backend.connectors.factory import get_connector_registration
    from backend.auth.system_context import system_context
    from backend.data_plane.scope import OwnerScope
    from backend.services.data_plane_service import get_default_plane

    redis_client = syncredis.from_url(settings.redis_url)
    lock_key = f"pipeline:run:{pipeline_id}"
    lock = redis_client.lock(lock_key, timeout=PIPELINE_LOCK_TTL)

    if not lock.acquire(blocking=False):
        logger.info("Pipeline %s already running (Redis lock held), skipping", pipeline_id)
        return ""

    db = SessionLocal()
    run_id = str(uuid.uuid4())
    run = None

    try:
        pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
        if not pipeline:
            logger.warning("run_pipeline: pipeline %s not found", pipeline_id)
            return ""

        connection = db.query(DatabaseConnection).filter(
            DatabaseConnection.id == pipeline.source_connection_id
        ).first()
        if not connection:
            raise RuntimeError(f"Source connection {pipeline.source_connection_id} not found")

        # New-model run: a schedule provides the table subset + per-table specs.
        schedule = None
        if schedule_id:
            from backend.models.pipeline import PipelineSchedule
            schedule = db.query(PipelineSchedule).filter(
                PipelineSchedule.id == schedule_id
            ).first()
            if not schedule:
                logger.warning("run_pipeline: schedule %s not found", schedule_id)
                return ""

        scope = OwnerScope(pipeline.owner_scope_kind, pipeline.owner_scope_id)
        plane = get_default_plane(scope, db)

        # Insert running run record
        started_at = datetime.now(timezone.utc)
        run = PipelineRun(
            id=run_id,
            pipeline_id=pipeline_id,
            schedule_id=schedule_id,
            started_at=started_at,
            status="running",
            triggered_by=triggered_by,
            triggered_by_user_id=triggered_by_user_id,
        )
        db.add(run)
        pipeline.last_run_status = "running"
        db.commit()

        error_message = None
        rows_written = 0
        bytes_written = 0

        try:
            with system_context(reason="pipeline.run", scope=scope):
                # Get connector registration to find dlt_source_for
                reg = get_connector_registration(connection.db_type)
                if reg is None:
                    raise RuntimeError(f"No connector registration for db_type={connection.db_type!r}")

                connector_cls = reg.connector_class

                # Resolve dlt_source_for: prefer the registration field (new shape),
                # fall back to a connector_class attribute (legacy shape) for plugins
                # that haven't been ported to the new template scaffold yet.
                source_fn = reg.dlt_source_for
                if source_fn is None and hasattr(connector_cls, "dlt_source_for"):
                    source_fn = connector_cls.dlt_source_for
                if source_fn is None:
                    raise RuntimeError(
                        f"Connector {connection.db_type!r} does not implement dlt_source_for — "
                        "cannot run as a Pipeline"
                    )

                # pre_run hook (token refresh, auth setup)
                if hasattr(connector_cls, "pre_run"):
                    connector_cls.pre_run(connection)

                # Build dlt source. Inject the per-pipeline incremental cursor
                # column + cutoff window into extraction_config so SQL
                # connectors (postgres / mysql) hand them to dlt's
                # `sources.incremental` for true incremental extracts. Other
                # connectors (CSV, notion, GA4, …) ignore unknown keys.
                #
                # For a backfill ("Load history") run, override `initial_value`
                # so the cursor pulls from `backfill_since` forward instead of
                # the last persisted watermark. A no-op for full-snapshot
                # pipelines.
                # Build extraction_config. New-model (schedule) runs pass
                # per-table specs (own target/mode/cursor/PK); legacy runs pass
                # the pipeline-wide single incremental_key.
                extraction_config = dict(pipeline.extraction_config or {})
                unique_key_by_table: dict[str, tuple] | None = None
                specs: list[dict] = []
                if schedule is not None:
                    specs = [s for s in (schedule.tables or []) if s.get("enabled", True)]
                    extraction_config["cutoff_days"] = settings.incremental_cutoff_days
                    extraction_config.pop("incremental_key", None)
                    unique_key_by_table = {
                        s["target_table"]: tuple(s["unique_key"])
                        for s in specs
                        if s.get("mode") == "incremental" and s.get("unique_key")
                    }
                elif pipeline.mode == "incremental" and pipeline.incremental_key:
                    extraction_config["incremental_key"] = pipeline.incremental_key
                    # T-N cutoff: cap the cursor's exclusive upper bound at
                    # `cutoff_days` whole days before the start of today UTC
                    # (default 1 = T-1). Applied in `sql_dlt_source`.
                    extraction_config["cutoff_days"] = settings.incremental_cutoff_days
                if backfill_since:
                    extraction_config["initial_value"] = backfill_since

                # Build dlt destination wrapping DataPlane. Schedule runs write
                # many target tables (per resource), so pass a per-table dedup
                # map; legacy runs write one table with one unique_key.
                from backend.pipelines.dlt_destination import make_dataplane_destination
                destination, row_counter = make_dataplane_destination(
                    plane, scope, pipeline.target_table or "",
                    unique_key=tuple(pipeline.unique_key) if pipeline.unique_key else None,
                    unique_key_by_table=unique_key_by_table,
                )

                # Run dlt. Use an ephemeral `pipeline_name` for backfills so
                # the saved watermark cursor doesn't shadow our `initial_value`
                # override (dlt only respects `initial_value` when no prior
                # state exists for that pipeline_name).
                import dlt as _dlt
                dlt_pipeline_name = (
                    f"bingo_{pipeline_id[:8]}_bf_{int(started_at.timestamp())}"
                    if backfill_since
                    else f"bingo_{pipeline_id[:8]}"
                )
                dlt_pipeline = _dlt.pipeline(
                    pipeline_name=dlt_pipeline_name,
                    destination=destination,
                )
                # write_disposition + primary_key:
                #   full        → replace (snapshot)
                #   incremental → merge on `unique_key` when present (dedup),
                #                 else append (no PK to dedup on — UI surfaces
                #                 this table as a dedup risk).
                # `incremental_key` is the cursor (watermark) column, applied
                # in `sql_dlt_source`; it is NOT a merge primary key.
                # Bytes: dlt LoadPackage job.file_size sums to the actual
                # bytes written to the plane (Parquet on GCS / local fs).
                def _bytes(load_info) -> int:
                    n = 0
                    for load_pkg in (load_info.load_packages or []):
                        for job in (load_pkg.jobs.get("completed_jobs") or []):
                            n += getattr(job, "file_size", 0) or 0
                    return n

                if schedule is not None:
                    # Run tables in chunks of _CHUNK_SIZE — one dlt run per chunk
                    # (each chunk = a single normalize/load cycle over its tables),
                    # in schedule.tables order. Per-resource hints (table_name,
                    # write_disposition, primary_key, incremental) are applied in
                    # sql_dlt_source; resources within a chunk extract sequentially,
                    # so concurrent source connections stay bounded by the celery
                    # pipeline-worker cap. Best-effort: a failing chunk is logged and
                    # skipped so later chunks still ingest; errors mark the run failed.
                    table_errors: list[str] = []
                    for i in range(0, len(specs), _CHUNK_SIZE):
                        chunk = specs[i:i + _CHUNK_SIZE]
                        ec = dict(extraction_config)
                        ec["table_specs"] = chunk
                        try:
                            bytes_written += _bytes(dlt_pipeline.run(source_fn(connection, ec)))
                        except Exception as exc:
                            targets = ", ".join(s.get("target_table") for s in chunk)
                            table_errors.append(f"[{targets}]: {exc}")
                            logger.exception(
                                "Pipeline %s schedule %s: chunk %d-%d failed",
                                pipeline_id, schedule.id, i, i + len(chunk),
                            )
                    if table_errors:
                        error_message = "; ".join(table_errors)[:2000]
                else:
                    if pipeline.mode == "full":
                        write_disposition = "replace"
                    elif pipeline.unique_key:
                        write_disposition = "merge"
                    else:
                        write_disposition = "append"
                    bytes_written += _bytes(dlt_pipeline.run(
                        source_fn(connection, extraction_config),
                        table_name=pipeline.target_table,
                        write_disposition=write_disposition,
                        primary_key=tuple(pipeline.unique_key) if pipeline.unique_key else None,
                    ))

                # Rows: closure counter from the custom destination is the
                # only accurate source -- dlt LoadPackage exposes file_size
                # (bytes), not row counts.
                rows_written = row_counter["rows"]

                # Persist dlt incremental state. Isolate this in its own
                # try/except + rollback so a serialization gap (e.g. an
                # unexpected non-JSON type in dlt's state dict) cannot strand
                # the session and prevent the terminal run-status commit below.
                # Backfill runs are ephemeral and intentionally do NOT
                # overwrite the canonical pipeline's saved cursor — otherwise
                # the next scheduled run would skip forward to the backfill's
                # watermark and miss recent rows.
                if not backfill_since:
                    from backend.pipelines.dlt_state import set_state as _set_state
                    raw_state = dlt_pipeline.state or {}
                    try:
                        _set_state(
                            pipeline_id,
                            raw_state,
                            db,
                            owner_scope_kind=pipeline.owner_scope_kind,
                            owner_scope_id=pipeline.owner_scope_id,
                        )
                    except Exception:
                        logger.exception(
                            "Pipeline %s run %s: failed to persist dlt state; continuing with run-status update",
                            pipeline_id, run_id,
                        )
                        db.rollback()

        except Exception as exc:
            error_message = str(exc)[:2000]
            logger.exception("Pipeline %s run %s failed", pipeline_id, run_id)

        # Update terminal status
        finished_at = datetime.now(timezone.utc)
        status = "failed" if error_message else "success"

        run.status = status
        run.finished_at = finished_at
        run.error_message = error_message
        run.rows_written = rows_written or None
        run.bytes_written = bytes_written or None

        pipeline.last_run_status = status
        pipeline.last_run_at = finished_at

        # Flip the bootstrap-flag latch on first successful ingest. Phase 2
        # widget / chat plane-redirect paths read this to decide whether to
        # allow a live source-DB fallback ("not-ready policy" — one live query
        # per missing partition until the first ingest lands, then plane-only).
        # Gate on rows_written > 0: a zero-row "success" never calls
        # write_parquet → no BQ external table → latching would permanently
        # 503 the widget read (plane_table_missing).
        if (
            status == "success"
            and not pipeline.first_ingest_done
            and (rows_written or 0) > 0
        ):
            pipeline.first_ingest_done = True

        # Advance next_run_at for cron pipelines. Skip for backfill runs —
        # they're off-schedule "Load history" actions and must not push out
        # the next scheduled run.
        if pipeline.cron and not backfill_since:
            from croniter import croniter
            pipeline.next_run_at = croniter(pipeline.cron, finished_at).get_next(datetime)

        db.commit()

        # Publish lineage:invalidate
        try:
            redis_client.publish("lineage:invalidate", json.dumps({
                "pipeline_id": pipeline_id,
                "scope_kind": pipeline.owner_scope_kind,
                "scope_id": pipeline.owner_scope_id,
            }))
        except Exception:
            logger.warning("Failed to publish lineage:invalidate for pipeline %s", pipeline_id)

        # Publish pipeline.run.failed notification event
        if status == "failed":
            try:
                from backend.notifications import publish
                publish({
                    "event_type": "pipeline.run.failed",
                    "scope": {"kind": pipeline.owner_scope_kind, "id": pipeline.owner_scope_id},
                    "resource_type": "pipeline",
                    "resource_id": pipeline_id,
                    "name": pipeline.name,
                    "run_id": run_id,
                    "error_message": error_message,
                })
            except Exception:
                logger.warning("Failed to publish pipeline.run.failed for pipeline %s", pipeline_id)

        # Chain profiling + warm dashboards on success.
        if status == "success":
            from backend.services.dashboard_cache import enqueue_dashboard_warm_for_table
            if schedule is not None:
                # New model: one run wrote many target tables — warm each.
                # (Schema-drift profiling per target is a P1 follow-up; the
                # legacy single-target diff path below doesn't apply here.)
                for s in (schedule.tables or []):
                    tgt = s.get("target_table")
                    if tgt:
                        try:
                            enqueue_dashboard_warm_for_table(scope, tgt)
                        except Exception:
                            logger.warning("warm enqueue failed for %s", tgt)
            else:
                try:
                    from backend.tasks.profiling_tasks import profile_pipeline_output
                    profile_pipeline_output.delay(pipeline_id, run_id)
                except Exception:
                    logger.warning("Failed to chain profile_pipeline_output for pipeline %s", pipeline_id)
                enqueue_dashboard_warm_for_table(scope, pipeline.target_table)

        return run_id

    except Exception as exc:
        logger.exception("run_pipeline outer error for pipeline %s", pipeline_id)
        if run is not None:
            try:
                run.status = "failed"
                run.error_message = str(exc)[:2000]
                run.finished_at = datetime.now(timezone.utc)
                db.commit()
            except Exception:
                db.rollback()
        return run_id or ""

    finally:
        db.close()
        try:
            lock.release()
        except Exception:
            pass
        try:
            redis_client.close()
        except Exception:
            pass
