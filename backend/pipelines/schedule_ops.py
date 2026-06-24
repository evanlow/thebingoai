"""Shared update logic for new-model `PipelineSchedule` rows.

Used by both the user API (`/api/pipelines/{id}/schedules/{sid}`) and the admin
plugin route so the validation + table-spec rebuild live in one place.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.models.pipeline import Pipeline, PipelineSchedule
from backend.utils.cron import compute_next_run, is_valid_timezone

# Sentinel: distinguishes "field omitted" from "field explicitly set to null".
_UNSET: Any = object()


def update_schedule(
    pipeline: Pipeline,
    schedule: PipelineSchedule,
    db: Session,
    *,
    cron: Any = _UNSET,
    timezone: Any = _UNSET,
    enabled: Any = _UNSET,
    tables: Any = _UNSET,
) -> PipelineSchedule:
    """Apply a partial update to `schedule`. Caller commits.

    Raises ValueError on an invalid timezone or cron expression (endpoints map
    these to 422).
    """
    if timezone is not _UNSET and timezone:
        if not is_valid_timezone(timezone):
            raise ValueError(f"Unknown IANA timezone: {timezone}")
        schedule.timezone = timezone

    if cron is not _UNSET:
        schedule.cron = cron or None

    if enabled is not _UNSET:
        schedule.enabled = bool(enabled)

    if tables is not _UNSET and tables is not None:
        schedule.tables = _rebuild_specs(pipeline, list(tables), db)

    # Recompute next_run_at: only when the schedule is live and has a cron.
    tz = schedule.timezone or "UTC"
    if schedule.enabled and schedule.cron:
        try:
            schedule.next_run_at = compute_next_run(schedule.cron, tz)
        except Exception as exc:  # invalid cron expression
            raise ValueError(f"Invalid cron expression: {schedule.cron!r} ({exc})")
    else:
        schedule.next_run_at = None

    return schedule


def _rebuild_specs(pipeline: Pipeline, selected: list[str], db: Session) -> list[dict]:
    """Re-derive `tables` specs for the selected source tables via the materializer."""
    from backend.models.database_connection import DatabaseConnection
    from backend.connectors.factory import get_connector_registration
    from backend.services.template_materializer import build_specs_for_tables

    conn = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == pipeline.source_connection_id
    ).first()
    if conn is None:
        raise ValueError("Source connection not found for schedule")
    reg = get_connector_registration(conn.db_type)
    if reg is None:
        raise ValueError(f"No connector registration for db_type={conn.db_type!r}")
    return build_specs_for_tables(conn, reg, db, selected)
