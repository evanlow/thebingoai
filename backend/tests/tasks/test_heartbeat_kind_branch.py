from unittest.mock import patch, MagicMock
from datetime import datetime
from backend.tasks.heartbeat_tasks import dispatch_heartbeat_jobs, execute_heartbeat_briefing


def _job_query_db(job, recent):
    """MagicMock db: query(HeartbeatJob)->job, query(Briefing) recent-check->recent."""
    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        if model.__name__ == "HeartbeatJob":
            q.filter.return_value.first.return_value = job
        else:  # Briefing idempotency lookup
            q.filter.return_value.first.return_value = recent
        return q

    db.query.side_effect = query_side_effect
    return db


def test_execute_heartbeat_briefing_creates_row_and_dispatches():
    job = MagicMock(id="job-1", user_id="u1", prompt="analyze dashboard 42 weekly")
    db = _job_query_db(job, recent=None)
    db.refresh.side_effect = lambda obj: setattr(obj, "id", 99)

    with patch("backend.tasks.heartbeat_tasks.SessionLocal", return_value=db), \
         patch("backend.tasks.briefing_tasks.generate_briefing.delay") as gen_delay:
        execute_heartbeat_briefing("job-1")

    added = db.add.call_args[0][0]
    assert added.source == "scheduled"
    assert added.dashboard_id == 42
    assert added.heartbeat_job_id == "job-1"
    assert added.status == "generating"
    gen_delay.assert_called_once_with(99)


def test_execute_heartbeat_briefing_skips_when_recent_exists():
    job = MagicMock(id="job-1", user_id="u1", prompt="analyze dashboard 42 weekly")
    db = _job_query_db(job, recent=MagicMock(id=7))

    with patch("backend.tasks.heartbeat_tasks.SessionLocal", return_value=db), \
         patch("backend.tasks.briefing_tasks.generate_briefing.delay") as gen_delay:
        execute_heartbeat_briefing("job-1")

    db.add.assert_not_called()
    gen_delay.assert_not_called()


def test_execute_heartbeat_briefing_no_dashboard_id_in_prompt():
    job = MagicMock(id="job-1", user_id="u1", prompt="just summarize things")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = job

    with patch("backend.tasks.heartbeat_tasks.SessionLocal", return_value=db), \
         patch("backend.tasks.briefing_tasks.generate_briefing.delay") as gen_delay:
        execute_heartbeat_briefing("job-1")

    db.add.assert_not_called()
    gen_delay.assert_not_called()


def test_briefing_kind_dispatches_briefing_task():
    job = MagicMock(
        id="job-1", user_id="u1", agent_type=None, kind="briefing",
        cron_expression="0 9 * * MON", is_active=True, next_run_at=datetime(2026, 5, 5),
        prompt="analyze dashboard 42 ...",
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [job]

    with patch("backend.tasks.heartbeat_tasks.SessionLocal", return_value=db), \
         patch("backend.tasks.heartbeat_tasks.execute_heartbeat_briefing.delay") as brief_delay, \
         patch("backend.tasks.heartbeat_tasks.execute_heartbeat_job.delay") as orch_delay:
        dispatch_heartbeat_jobs()

    brief_delay.assert_called_once_with("job-1")
    orch_delay.assert_not_called()
