"""Account-deletion teardown.

Triggered by `DELETE /auth/account` after SSO has renamed + deactivated the
account. We mirror the rename locally and DISABLE (do not delete) the resources
that keep consuming credits on a schedule — live database connections, pipelines,
dbt transforms, heartbeat jobs, autonomous agents, dashboard refresh schedules —
by flipping each one's existing on/off flag. Every scheduler filters on that flag,
so flipping it off stops the run while preserving the row.

KEPT untouched: conversations, generated briefs, dashboard configs, BigQuery/GCS
data, file-based connections, the credit ledger. The user row itself is NOT
deleted — it is renamed (tombstoned) and flagged `is_active=False`. Keeping the
row means the `cascade="all, delete-orphan"` relationships on `User` never fire,
so the KEEP set survives automatically. Freeing the original email (via the
rename) lets it register again later as a fresh account.
"""
import logging

logger = logging.getLogger(__name__)

# db_type values that are file-based / managed — KEPT (untouched) on deletion.
# Everything else (postgres, mysql, bigquery_ga4, ...) is a live external DB
# connection holding credentials and feeding pipelines, and is disabled.
FILE_BASED_DB_TYPES = {"dataset", "sqlite", "data_plane"}


def tombstone_account(db, user, new_email: str) -> None:
    """Rename + deactivate `user` and disable its credit-consuming resources.

    Disables (does not delete) every scheduled/credit-consuming resource by
    flipping its flag. Runs synchronously; commits on success. Call inside
    run_in_threadpool from an async endpoint.
    """
    from backend.models.database_connection import DatabaseConnection
    from backend.models.heartbeat_job import HeartbeatJob
    from backend.models.custom_agent import CustomAgent
    from backend.models.dashboard import Dashboard
    from backend.models.pipeline import Pipeline
    from backend.models.transforms import DbtModel

    if not new_email:
        raise ValueError("tombstone_account: new_email must be a non-empty masked email")

    user_id = user.id

    # 1. Mirror SSO's email mask and flag the row inactive. Keep the row so the
    #    KEEP set (conversations, briefs, dashboards, file connections) survives.
    user.email = new_email
    user.is_active = False

    # 2. Disable live DB connections (KEEP file-based ones). Rows + encrypted
    #    creds stay at rest but are never used while inactive; connection
    #    listings/usage filter is_active.
    conn_disabled = (
        db.query(DatabaseConnection)
        .filter(
            DatabaseConnection.user_id == user_id,
            DatabaseConnection.db_type.notin_(FILE_BASED_DB_TYPES),
        )
        .update({DatabaseConnection.is_active: False}, synchronize_session=False)
    )

    # 3. Disable pipelines (cron sync jobs). dispatch_pipelines filters enabled.
    pipelines_disabled = (
        db.query(Pipeline)
        .filter(Pipeline.created_by_user_id == user_id)
        .update(
            {Pipeline.enabled: False, Pipeline.next_run_at: None},
            synchronize_session=False,
        )
    )

    # 4. Disable dbt transforms (cron transform jobs). dispatch_dbt_runs filters enabled.
    transforms_disabled = (
        db.query(DbtModel)
        .filter(DbtModel.created_by_user_id == user_id)
        .update(
            {DbtModel.enabled: False, DbtModel.next_run_at: None},
            synchronize_session=False,
        )
    )

    # 5. Disable heartbeat jobs (scheduled orchestrator runs). dispatcher filters is_active.
    #    Generated briefs are unaffected (we keep the jobs, just stop them).
    hb_disabled = (
        db.query(HeartbeatJob)
        .filter(HeartbeatJob.user_id == user_id)
        .update(
            {HeartbeatJob.is_active: False, HeartbeatJob.next_run_at: None},
            synchronize_session=False,
        )
    )

    # 6. Disable autonomous agents (scheduled mesh agents). agent dispatch filters is_active.
    #    Non-autonomous agents are static config — left enabled.
    agents_disabled = (
        db.query(CustomAgent)
        .filter(
            CustomAgent.user_id == user_id,
            CustomAgent.is_autonomous.is_(True),
        )
        .update({CustomAgent.is_active: False}, synchronize_session=False)
    )

    # 7. Stop dashboard refresh schedules but KEEP the dashboards + cron config.
    dash_disabled = (
        db.query(Dashboard)
        .filter(
            Dashboard.user_id == user_id,
            Dashboard.schedule_active.is_(True),
        )
        .update(
            {Dashboard.schedule_active: False, Dashboard.next_run_at: None},
            synchronize_session=False,
        )
    )

    db.commit()
    logger.info(
        "tombstone_account: user %s tombstoned as %s — disabled %d conn, %d pipeline, "
        "%d transform, %d heartbeat, %d agent, %d dashboard schedule",
        user_id, new_email, conn_disabled, pipelines_disabled, transforms_disabled,
        hb_disabled, agents_disabled, dash_disabled,
    )
