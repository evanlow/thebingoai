"""execute_heartbeat_job credit ordering — persist BEFORE charge.

The run row must be committed inside the credit context so a persist failure
raises out of the block and the turn is never billed (same order as the
websocket chat path). Pins:

  - success: enter → orchestrate → persist-commit → exit(None)
  - persist failure: exit receives the exception (manager skips billing)
"""
from unittest.mock import MagicMock, patch

from backend.tasks.heartbeat_tasks import execute_heartbeat_job


class _FakeMgr:
    def __init__(self, order, **kwargs):
        self.order = order

    def __enter__(self):
        self.order.append("enter")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.order.append(("exit", exc_type))
        return False


def _db(order, job, user, commit_fail_on=None):
    """MagicMock db whose commit() appends to the shared order log; the
    commit_fail_on-th commit raises (1-based)."""
    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        first = job if model.__name__ == "HeartbeatJob" else user
        q.filter.return_value.first.return_value = first
        return q

    db.query.side_effect = query_side_effect

    commits = {"n": 0}

    def _commit():
        commits["n"] += 1
        order.append("commit")
        if commit_fail_on is not None and commits["n"] == commit_fail_on:
            raise RuntimeError("persist failed")

    db.commit.side_effect = _commit
    return db


def _run(order, *, commit_fail_on=None):
    job = MagicMock(id="job-1", user_id="u1", prompt="summarize")
    user = MagicMock(id="u1")
    db = _db(order, job, user, commit_fail_on=commit_fail_on)

    async def _orchestrate(job, user):
        order.append("orchestrate")
        return "answer"

    import backend.services.token_tracking_service as tts
    import backend.plugins.loader as loader

    with patch("backend.tasks.heartbeat_tasks.SessionLocal", return_value=db), \
         patch("backend.tasks.heartbeat_tasks._run_orchestrator_for_job", _orchestrate), \
         patch("backend.tasks.heartbeat_tasks._deliver_heartbeat_result"), \
         patch.object(loader, "get_loaded_plugins", lambda: {}), \
         patch.object(tts, "CreditContextManager", lambda **kw: _FakeMgr(order, **kw)):
        execute_heartbeat_job("job-1")


def test_success_persists_before_charge():
    order = []
    _run(order)
    # commit #1 = run-row insert (before the credit block), commit #2 = the
    # completed-run persist — it must land BEFORE the manager exits (charges).
    assert order == ["commit", "enter", "orchestrate", "commit", ("exit", None)]


def test_persist_failure_reaches_exit_unbilled():
    order = []
    # Second commit = the completed-run persist; make it blow up.
    _run(order, commit_fail_on=2)
    # The exception flows through __exit__ (manager skips billing), then
    # record_run_failure swallows it — the task itself must not raise.
    assert ("exit", RuntimeError) in order
    assert ("exit", None) not in order
