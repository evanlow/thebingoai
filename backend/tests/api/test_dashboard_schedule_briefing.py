def test_analysis_schedule_creates_briefing_kind_job(authenticated_client, db_session, sample_dashboard):
    from backend.models.heartbeat_job import HeartbeatJob

    resp = authenticated_client.post(
        f"/api/dashboards/{sample_dashboard.id}/analysis-schedule",
        json={"schedule_type": "preset", "schedule_value": "daily"},
    )
    assert resp.status_code == 201

    job = db_session.query(HeartbeatJob).filter(HeartbeatJob.id == resp.json()["job_id"]).first()
    assert job.kind == "briefing"


def test_analysis_schedule_accepts_cron_value(authenticated_client, db_session, sample_dashboard):
    """Monthly briefing has no preset — the button sends a raw cron expression."""
    from backend.models.heartbeat_job import HeartbeatJob

    resp = authenticated_client.post(
        f"/api/dashboards/{sample_dashboard.id}/analysis-schedule",
        json={"schedule_type": "cron", "schedule_value": "0 9 1 * *"},
    )
    assert resp.status_code == 201

    job = db_session.query(HeartbeatJob).filter(HeartbeatJob.id == resp.json()["job_id"]).first()
    assert job.cron_expression == "0 9 1 * *"


def test_analysis_schedule_delete_removes_job(authenticated_client, db_session, sample_dashboard):
    """Turn off → DELETE removes the recurring briefing job."""
    from backend.models.heartbeat_job import HeartbeatJob

    created = authenticated_client.post(
        f"/api/dashboards/{sample_dashboard.id}/analysis-schedule",
        json={"schedule_type": "preset", "schedule_value": "weekly"},
    )
    job_id = created.json()["job_id"]

    resp = authenticated_client.delete(f"/api/dashboards/{sample_dashboard.id}/analysis-schedule")
    assert resp.status_code == 204
    assert db_session.query(HeartbeatJob).filter(HeartbeatJob.id == job_id).first() is None
