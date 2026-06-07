"""Unit tests for lineage `_attach_errors` — per-node error attribution.

Regression guard for the fix that made dbt error attribution per-model instead
of broadcasting one run's error to every failed transform node. Each failed
transform node must receive the error_message from the newest run in which
*that* model failed (matched by name via the run's models_run JSONB), with a
run-level fallback for models the run errored out before enumerating.

Only the dbt-model path is exercised here: the pipeline path builds a SQL window
function (func.row_number().over(...)) that requires a real database, which the
lightweight stub harness in conftest.py deliberately avoids. Passing no failed
*pipeline* nodes keeps that branch dormant.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock


class _FakeQuery:
    def __init__(self, rows):
        self._rows = list(rows)
    def filter(self, *_a, **_kw): return self
    def order_by(self, *_a, **_kw): return self
    def all(self): return list(self._rows)


def _make_db(dbt_runs):
    from backend.models.transforms import DbtRun
    db = MagicMock()
    def query(model, *rest):
        return _FakeQuery(dbt_runs if model is DbtRun else ())
    db.query.side_effect = query
    return db


def _dbt_run(*, models_run, error_message, started_at):
    from backend.models.transforms import DbtRun
    r = DbtRun()
    r.owner_scope_kind = "user"
    r.owner_scope_id = "u1"
    r.status = "failed"
    r.error_message = error_message
    r.started_at = started_at
    r.models_run = models_run
    return r


def _node(*, node_id, name, model_id, status):
    from backend.lineage import service
    return service.Node(
        id=node_id, kind="transform", name=name,
        meta={"model_id": model_id, "last_run_status": status},
    )


def test_attach_errors_is_per_model_not_broadcast():
    """Two failed models in different runs each get their own run's error."""
    from backend.data_plane.scope import OwnerScope
    from backend.lineage import service

    nodes = {
        "table:orders_summary": _node(node_id="table:orders_summary",
                                      name="orders_summary", model_id="m1", status="failed"),
        "table:customers": _node(node_id="table:customers",
                                 name="customers", model_id="m2", status="failed"),
        "table:revenue": _node(node_id="table:revenue",
                               name="revenue", model_id="m3", status="success"),
    }
    runs = [
        # newest: orders_summary failed here, customers succeeded
        _dbt_run(
            models_run=[{"name": "orders_summary", "status": "failed"},
                        {"name": "customers", "status": "success"}],
            error_message="orders boom",
            started_at=datetime(2026, 6, 6, 12, 0),
        ),
        # older: customers failed here
        _dbt_run(
            models_run=[{"name": "customers", "status": "failed"}],
            error_message="customers boom",
            started_at=datetime(2026, 6, 5, 12, 0),
        ),
    ]

    service._attach_errors(nodes, _make_db(runs), OwnerScope("user", "u1"))

    assert nodes["table:orders_summary"].meta["error_message"] == "orders boom"
    assert nodes["table:customers"].meta["error_message"] == "customers boom"
    # The successful node is never queried/attributed.
    assert "error_message" not in nodes["table:revenue"].meta


def test_attach_errors_falls_back_to_run_error_when_model_not_enumerated():
    """A failed model absent from models_run (run errored early) gets the
    newest run's run-level error_message as a fallback."""
    from backend.data_plane.scope import OwnerScope
    from backend.lineage import service

    nodes = {
        "table:orders_summary": _node(node_id="table:orders_summary",
                                      name="orders_summary", model_id="m1", status="failed"),
    }
    runs = [
        _dbt_run(models_run=[], error_message="dbt crashed before run",
                 started_at=datetime(2026, 6, 6, 12, 0)),
    ]

    service._attach_errors(nodes, _make_db(runs), OwnerScope("user", "u1"))

    assert nodes["table:orders_summary"].meta["error_message"] == "dbt crashed before run"


def test_attach_errors_noop_when_no_failed_nodes():
    """No failed nodes → nothing queried, no error_message added."""
    from backend.data_plane.scope import OwnerScope
    from backend.lineage import service

    nodes = {
        "table:revenue": _node(node_id="table:revenue",
                               name="revenue", model_id="m3", status="success"),
    }
    service._attach_errors(nodes, _make_db([]), OwnerScope("user", "u1"))
    assert "error_message" not in nodes["table:revenue"].meta
