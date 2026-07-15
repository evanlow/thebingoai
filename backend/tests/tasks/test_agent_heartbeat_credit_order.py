"""execute_agent_heartbeat_job credit ordering — persist BEFORE charge.

The agent-routed twin of test_heartbeat_credit_order.py. Same contract, its own
code path (_run_agent_for_job via AgentRuntime instead of the orchestrator), so
the sibling file's coverage says nothing about this one. Pins:

  - success: enter → agent-run → persist-commit → exit(None) → deliver
  - persist failure: exit receives the exception (manager skips billing)
  - billing failure: must NOT undo an already-committed COMPLETED run
"""
from unittest.mock import MagicMock, patch

from backend.models.heartbeat_job_run import HeartbeatRunStatus
from backend.tasks.heartbeat_tasks import execute_agent_heartbeat_job


class _FakeMgr:
    def __init__(self, order, exit_raises=None, **kwargs):
        self.order = order
        self._exit_raises = exit_raises

    def __enter__(self):
        self.order.append("enter")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.order.append(("exit", exc_type))
        if self._exit_raises is not None and exc_type is None:
            raise self._exit_raises
        return False


def _db(order, job, user, run_box, commit_fail_on=None):
    """MagicMock db whose commit() appends to the shared order log; the
    commit_fail_on-th commit raises (1-based)."""
    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        first = job if model.__name__ == "HeartbeatJob" else user
        q.filter.return_value.first.return_value = first
        return q

    db.query.side_effect = query_side_effect
    db.add.side_effect = lambda obj: run_box.setdefault("run", obj)

    commits = {"n": 0}

    def _commit():
        commits["n"] += 1
        order.append("commit")
        if commit_fail_on is not None and commits["n"] == commit_fail_on:
            raise RuntimeError("persist failed")

    db.commit.side_effect = _commit
    return db


def _run(order, *, commit_fail_on=None, exit_raises=None, deliver_raises=None):
    job = MagicMock(id="job-1", user_id="u1", prompt="summarize", agent_type="data")
    user = MagicMock(id="u1")
    run_box = {}
    db = _db(order, job, user, run_box, commit_fail_on=commit_fail_on)

    async def _agent(job, user):
        order.append("agent-run")
        return "answer"

    import backend.services.token_tracking_service as tts
    import backend.plugins.loader as loader

    with patch("backend.tasks.heartbeat_tasks.SessionLocal", return_value=db), \
         patch("backend.tasks.heartbeat_tasks._run_agent_for_job", _agent), \
         patch("backend.tasks.heartbeat_tasks._deliver_heartbeat_result") as deliver, \
         patch.object(loader, "get_loaded_plugins", lambda: {}), \
         patch.object(tts, "CreditContextManager",
                      lambda **kw: _FakeMgr(order, exit_raises=exit_raises, **kw)):
        if deliver_raises is not None:
            deliver.side_effect = lambda *a, **k: (_ for _ in ()).throw(deliver_raises)
        else:
            deliver.side_effect = lambda *a, **k: order.append("deliver")
        execute_agent_heartbeat_job("job-1")

    return run_box.get("run"), deliver


def test_delivery_failure_leaves_the_turn_unbilled():
    # The permanent-conversation message is the only copy the user ever sees, so
    # a failed insert must reach __exit__ with the exception. Charging here would
    # bill for an answer that never arrived — the run row is internal.
    order = []
    run, _ = _run(order, deliver_raises=RuntimeError("permanent conv insert failed"))
    assert ("exit", RuntimeError) in order
    assert ("exit", None) not in order
    assert run.status == HeartbeatRunStatus.FAILED.value


def test_success_persists_and_delivers_before_charge():
    order = []
    run, deliver = _run(order)
    # commit #1 = run-row insert (before the credit block), commit #2 = the
    # completed-run persist. Both it and the delivery must land BEFORE the
    # manager exits (charges) — the user has the answer before they pay for it.
    assert order == ["commit", "enter", "agent-run", "commit", "deliver", ("exit", None)]
    assert run.status == HeartbeatRunStatus.COMPLETED.value
    assert run.response == "answer"
    deliver.assert_called_once()


def test_persist_failure_reaches_exit_unbilled():
    order = []
    run, deliver = _run(order, commit_fail_on=2)
    # The exception flows through __exit__ (manager skips billing), then
    # record_run_failure swallows it — the task itself must not raise.
    assert ("exit", RuntimeError) in order
    assert ("exit", None) not in order
    deliver.assert_not_called()  # nothing to deliver — the run wasn't saved


def test_billing_failure_does_not_fail_a_completed_run():
    # The whole reason _record_safe swallows: a bookkeeping error must not
    # escape into record_run_failure and flip an already-committed COMPLETED run
    # to FAILED. The real community manager swallows internally; a manager that
    # leaks one would corrupt the run, so pin the blast radius here.
    order = []
    run, deliver = _run(order, exit_raises=RuntimeError("credit_usage insert failed"))
    # __exit__ saw a clean turn — the answer was persisted AND delivered — and
    # only then blew up on the charge.
    assert ("exit", None) in order
    deliver.assert_called_once()
    # record_run_failure caught it and marked the run FAILED even though the user
    # already has the answer — the corruption _record_safe prevents by never
    # raising. Contrast with the next test, which uses the real manager.
    assert run.status == HeartbeatRunStatus.FAILED.value


def test_community_manager_billing_error_leaves_run_completed():
    # The counterpart to the test above, with the REAL community manager (no
    # _FakeMgr): force its _record() INSERT to fail and show _record_safe
    # swallows it, so the COMPLETED run and its delivery survive intact.
    order = []
    job = MagicMock(id="job-1", user_id="u1", prompt="summarize", agent_type="data")
    user = MagicMock(id="u1")
    run_box = {}
    db = _db(order, job, user, run_box)
    db.execute.side_effect = RuntimeError('relation "credit_usage" does not exist')

    async def _agent(job, user):
        return "answer"

    import backend.plugins.loader as loader

    with patch("backend.tasks.heartbeat_tasks.SessionLocal", return_value=db), \
         patch("backend.tasks.heartbeat_tasks._run_agent_for_job", _agent), \
         patch("backend.tasks.heartbeat_tasks._deliver_heartbeat_result") as deliver, \
         patch.object(loader, "get_loaded_plugins", lambda: {}):
        execute_agent_heartbeat_job("job-1")

    run = run_box["run"]
    assert run.status == HeartbeatRunStatus.COMPLETED.value
    deliver.assert_called_once()
    db.rollback.assert_called_once()  # the failed INSERT was rolled back
