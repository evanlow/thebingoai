"""Pipeline API router (Phase 2)."""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.pipeline import Pipeline, PipelineRun
from backend.utils.cron import compute_next_run, is_valid_timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class PipelineCreate(BaseModel):
    name: str
    source_connection_id: int
    owner_scope_kind: str = "user"
    owner_scope_id: str
    target_table: str
    cron: str | None = None
    timezone: str | None = None
    mode: str = "full"
    incremental_key: str | None = None
    extraction_config: dict[str, Any] = {}


class PipelineOverride(BaseModel):
    """Per-table override of the watermark cursor + ingestion mode.

    Only the fields actually provided are applied — omit one to leave it
    unchanged. Used by the "Pipelines" tab on the connection-detail page to
    correct the auto-detected cursor or flip a table between full / incremental.
    """
    mode: str | None = None              # "full" | "incremental"
    incremental_key: str | None = None   # column name; required when mode=incremental


class WatermarkRedetectResponse(BaseModel):
    """Output of POST /pipelines/{id}/redetect — pipeline-side answers only."""
    pipeline_id: str
    table: str | None
    suggested_incremental_key: str | None
    current_incremental_key: str | None
    current_mode: str


class BackfillRequest(BaseModel):
    """Trigger a one-off "Load history" run with a custom cursor lower bound."""
    backfill_since: str  # ISO datetime string (e.g. "2024-01-01T00:00:00+00:00")


class PipelineResponse(BaseModel):
    id: str
    name: str
    source_connection_id: int
    owner_scope_kind: str
    owner_scope_id: str
    target_table: str
    cron: str | None
    timezone: str
    mode: str
    incremental_key: str | None
    unique_key: list[str] | None
    extraction_config: dict[str, Any]
    pipeline_fingerprint: str
    last_run_at: datetime | None
    last_run_status: str | None
    next_run_at: datetime | None
    enabled: bool
    created_by_user_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PipelineRunResponse(BaseModel):
    id: str
    pipeline_id: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    rows_written: int | None
    bytes_written: int | None
    error_message: str | None
    triggered_by: str
    triggered_by_user_id: str | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_pipeline_for_user(pipeline_id: str, user_id: str, db: Session) -> Pipeline:
    """Fetch a pipeline owned by (or accessible to) the requesting user."""
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    # Ownership check: pipeline belongs to the user directly OR the user created it
    if pipeline.created_by_user_id != user_id and pipeline.owner_scope_id != user_id:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


# ---------------------------------------------------------------------------
# POST /api/pipelines — create
# ---------------------------------------------------------------------------

@router.post("", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    body: PipelineCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new pipeline.

    Validates extraction_config against the connector's model (P2.1),
    deduplicates by fingerprint within the owner scope, and sets next_run_at
    from the cron expression when provided.
    """
    from backend.governance.contract import require as governance_require
    governance_require(
        user=current_user,
        action="create",
        resource={
            "type": "pipeline",
            "owner_scope_kind": body.owner_scope_kind,
            "owner_scope_id": body.owner_scope_id,
        },
    )

    from backend.models.database_connection import DatabaseConnection
    from backend.connectors.factory import get_connector_registration
    from backend.pipelines.runner import compute_pipeline_fingerprint

    # Verify the source connection exists and is accessible to the user
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == body.source_connection_id,
        DatabaseConnection.user_id == current_user.id,
    ).first()
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source connection not found",
        )

    reg = get_connector_registration(connection.db_type)

    # P2.1: validate extraction_config against the connector's model if present
    if reg and reg.extraction_config_model is not None:
        try:
            reg.extraction_config_model(**body.extraction_config)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid extraction_config: {exc}",
            )

    # Compute pipeline fingerprint
    conn_fingerprint = (reg.fingerprint(connection) if (reg and reg.fingerprint) else None) or ""
    fingerprint = compute_pipeline_fingerprint(conn_fingerprint, body.extraction_config)

    # Dedup check: same owner scope + fingerprint → 409
    existing = db.query(Pipeline).filter(
        Pipeline.owner_scope_kind == body.owner_scope_kind,
        Pipeline.owner_scope_id == body.owner_scope_id,
        Pipeline.pipeline_fingerprint == fingerprint,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A pipeline with this configuration already exists: id={existing.id}",
        )

    # Validate timezone
    tz_name = body.timezone or "UTC"
    if tz_name != "UTC" and not is_valid_timezone(tz_name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown IANA timezone: {tz_name}",
        )

    # Compute next_run_at from cron, evaluated in the requested timezone
    next_run_at: datetime | None = None
    if body.cron:
        next_run_at = compute_next_run(body.cron, tz_name)

    pipeline = Pipeline(
        id=str(_uuid.uuid4()),
        name=body.name,
        source_connection_id=body.source_connection_id,
        owner_scope_kind=body.owner_scope_kind,
        owner_scope_id=body.owner_scope_id,
        target_table=body.target_table,
        cron=body.cron,
        timezone=tz_name,
        mode=body.mode,
        incremental_key=body.incremental_key,
        extraction_config=body.extraction_config,
        pipeline_fingerprint=fingerprint,
        next_run_at=next_run_at,
        created_by_user_id=current_user.id,
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)

    from backend.governance.contract import emit_resource_created
    emit_resource_created(
        resource_type="pipeline",
        resource=pipeline,
        creator_user=current_user,
    )

    logger.info(
        "Pipeline %r (id=%s) created by user %s",
        pipeline.name, pipeline.id, current_user.id,
    )
    return pipeline


# ---------------------------------------------------------------------------
# GET /api/pipelines — list
# ---------------------------------------------------------------------------

@router.get("", response_model=list[PipelineResponse])
async def list_pipelines(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List pipelines for the requesting user (created by them or scoped to them)."""
    pipelines = (
        db.query(Pipeline)
        .filter(
            (Pipeline.created_by_user_id == current_user.id)
            | (Pipeline.owner_scope_id == current_user.id)
        )
        .order_by(Pipeline.created_at.desc())
        .all()
    )
    return pipelines


# ---------------------------------------------------------------------------
# GET /api/pipelines/{pipeline_id} — get single
# ---------------------------------------------------------------------------

@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve a single pipeline by ID."""
    return _get_pipeline_for_user(pipeline_id, current_user.id, db)


# ---------------------------------------------------------------------------
# GET /api/pipelines/{pipeline_id}/runs — run history
# ---------------------------------------------------------------------------

@router.get("/{pipeline_id}/runs", response_model=list[PipelineRunResponse])
async def get_pipeline_runs(
    pipeline_id: str,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List recent runs for a pipeline, newest first."""
    _get_pipeline_for_user(pipeline_id, current_user.id, db)

    runs = (
        db.query(PipelineRun)
        .filter(PipelineRun.pipeline_id == pipeline_id)
        .order_by(PipelineRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return runs


# ---------------------------------------------------------------------------
# POST /api/pipelines/{pipeline_id}/run — manual trigger
# ---------------------------------------------------------------------------

@router.post("/{pipeline_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_pipeline_run(
    pipeline_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger a pipeline run. Dispatches via Celery."""
    pipeline = _get_pipeline_for_user(pipeline_id, current_user.id, db)

    from backend.pipelines.tasks import run_pipeline_task

    task = run_pipeline_task.delay(pipeline.id, "manual", current_user.id)
    logger.info(
        "Manual trigger for pipeline %s by user %s → task %s",
        pipeline.id, current_user.id, task.id,
    )
    return {"run_id": task.id, "status": "queued"}


# ---------------------------------------------------------------------------
# DELETE /api/pipelines/{pipeline_id}
# ---------------------------------------------------------------------------

@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline_endpoint(
    pipeline_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a pipeline. Metadata + runs removed; materialized output left in place."""
    _get_pipeline_for_user(pipeline_id, current_user.id, db)
    from backend.services.resource_lifecycle import delete_pipeline
    delete_pipeline(pipeline_id, db)
    db.commit()


# ---------------------------------------------------------------------------
# PATCH /api/pipelines/{pipeline_id}/override — edit cursor + mode
# ---------------------------------------------------------------------------

@router.patch("/{pipeline_id}/override", response_model=PipelineResponse)
async def override_pipeline(
    pipeline_id: str,
    body: PipelineOverride,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Override the auto-detected cursor / mode for one pipeline.

    Updates `mode`, `incremental_key`, and the matching keys in
    `extraction_config` so the next dlt run picks up the new cursor. The dlt
    state is NOT reset here — call `/backfill` if you need to re-pull history
    under the new cursor.
    """
    pipeline = _get_pipeline_for_user(pipeline_id, current_user.id, db)

    new_mode = body.mode if body.mode is not None else pipeline.mode
    if new_mode not in ("full", "incremental"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"mode must be 'full' or 'incremental', got {new_mode!r}",
        )

    new_key = body.incremental_key if body.incremental_key is not None else pipeline.incremental_key
    if new_mode == "incremental" and not new_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="incremental_key is required when mode='incremental'",
        )

    pipeline.mode = new_mode
    pipeline.incremental_key = new_key if new_mode == "incremental" else None

    cfg = dict(pipeline.extraction_config or {})
    if new_mode == "incremental":
        cfg["incremental_key"] = new_key
        # initial_value left as-is; user can call /backfill to override the cursor lower bound
    else:
        cfg.pop("incremental_key", None)
        cfg.pop("initial_value", None)
    pipeline.extraction_config = cfg

    db.commit()
    db.refresh(pipeline)
    logger.info(
        "Pipeline %s override applied by user %s: mode=%s incremental_key=%s",
        pipeline.id, current_user.id, pipeline.mode, pipeline.incremental_key,
    )
    return pipeline


# ---------------------------------------------------------------------------
# POST /api/pipelines/{pipeline_id}/redetect — re-run watermark classifier
# ---------------------------------------------------------------------------

@router.post("/{pipeline_id}/redetect", response_model=WatermarkRedetectResponse)
def redetect_watermark(
    pipeline_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-run the watermark classifier against the live source schema.

    Defined sync (not ``async``) on purpose: ``classify_connection`` runs
    ``asyncio.run()`` internally when the LLM classifier is configured, which
    raises ``RuntimeError`` inside a running event loop. FastAPI executes sync
    endpoints in a threadpool, so ``asyncio.run`` gets a fresh loop. The body
    is fully synchronous (blocking connector + DB calls).

    Returns the *suggested* cursor without auto-applying — the UI surfaces it
    so the user can accept (via `/override`) or ignore. Honors the
    `WATERMARK_CLASSIFIER_*` env knobs (deterministic-only when unset).
    """
    pipeline = _get_pipeline_for_user(pipeline_id, current_user.id, db)
    tables = (pipeline.extraction_config or {}).get("tables") or []
    if len(tables) != 1:
        return WatermarkRedetectResponse(
            pipeline_id=pipeline.id,
            table=None,
            suggested_incremental_key=None,
            current_incremental_key=pipeline.incremental_key,
            current_mode=pipeline.mode,
        )
    table = tables[0]

    from backend.models.database_connection import DatabaseConnection
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == pipeline.source_connection_id,
        DatabaseConnection.user_id == current_user.id,
    ).first()
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source connection not found",
        )

    from backend.connectors.factory import get_connector_for_connection
    from backend.services.watermark_classifier import classify_connection

    suggested: str | None = None
    try:
        connector = get_connector_for_connection(connection)
    except Exception:
        logger.warning("redetect: cannot open connector for pipeline %s", pipeline.id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to the source database",
        )
    try:
        try:
            schema_obj = connector.get_table_schema(table, schema=None)
        except Exception as exc:
            logger.warning(
                "redetect: schema fetch failed for table %s on pipeline %s",
                table, pipeline.id, exc_info=True,
            )
            # Propagate as 503 instead of returning an ambiguous null suggestion —
            # the UI message "Classifier found no usable cursor" would mislead the
            # user when the real failure is a transient DB reachability issue.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Could not read schema for table '{table}': {exc}",
            )
        columns = list(getattr(schema_obj, "columns", []) or [])
        if columns:
            suggested = classify_connection({table: columns}).get(table)
    finally:
        close = getattr(connector, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    return WatermarkRedetectResponse(
        pipeline_id=pipeline.id,
        table=table,
        suggested_incremental_key=suggested,
        current_incremental_key=pipeline.incremental_key,
        current_mode=pipeline.mode,
    )


# ---------------------------------------------------------------------------
# POST /api/pipelines/{pipeline_id}/backfill — "Load history" trigger
# ---------------------------------------------------------------------------

@router.post("/{pipeline_id}/backfill", status_code=status.HTTP_202_ACCEPTED)
async def backfill_pipeline(
    pipeline_id: str,
    body: BackfillRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trigger a one-off historical run with a custom cursor lower bound.

    Off-schedule: does NOT advance `next_run_at`. Uses an ephemeral dlt
    `pipeline_name` so the saved cursor isn't shadowed by prior state; merge
    dedup via `unique_key` handles overlap with the canonical pipeline's
    already-loaded rows. Tables without a `unique_key` will produce duplicates
    (the override UI flags those as a dedup risk).
    """
    pipeline = _get_pipeline_for_user(pipeline_id, current_user.id, db)

    # Validate + normalize `backfill_since` to an aware UTC datetime. A
    # timezone-naive value would reach the dlt incremental cursor in
    # `sql_dlt_source`, where it's compared against an aware UTC `end_value` —
    # mixing aware/naive raises TypeError. Naive input is interpreted as UTC.
    try:
        parsed = datetime.fromisoformat(body.backfill_since)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"backfill_since must be an ISO datetime string, got {body.backfill_since!r}",
        )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    backfill_since = parsed.astimezone(timezone.utc).isoformat()

    if pipeline.mode != "incremental":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Backfill only applies to incremental pipelines — full snapshots reload all rows on every run",
        )

    from backend.pipelines.tasks import run_pipeline_task
    task = run_pipeline_task.delay(
        pipeline.id, "manual", current_user.id, backfill_since,
    )
    logger.info(
        "Backfill triggered for pipeline %s by user %s since=%s → task %s",
        pipeline.id, current_user.id, backfill_since, task.id,
    )
    return {"run_id": task.id, "status": "queued", "backfill_since": backfill_since}
