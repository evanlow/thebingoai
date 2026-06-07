"""Real-DB coverage for the pipeline branch of lineage `_attach_errors`.

The dbt-model path of `_attach_errors` ranks runs in Python and is covered by the
stub-harness tests in tests/lineage/test_attach_errors.py. The *pipeline* path
ranks runs in SQL — `func.row_number().over(partition_by=pipeline_id,
order_by=started_at.desc())`, filtered to status='failed' AND error_message IS
NOT NULL — which the stub harness deliberately cannot exercise. These tests run
the real window function against Postgres so the newest-failed-run-per-pipeline
selection and its filters are actually verified.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from backend.models.database_connection import DatabaseConnection, DatabaseType
from backend.models.pipeline import Pipeline, PipelineRun
from backend.security.encryption import encrypt_password


def _connection(db_session, user_id):
    conn = DatabaseConnection(
        user_id=user_id,
        name=f"conn-{uuid.uuid4()}",
        db_type=DatabaseType.POSTGRES,
        host="localhost",
        port=5432,
        database="testdb",
        username="testuser",
        _encrypted_password=encrypt_password("testpass"),
    )
    db_session.add(conn)
    db_session.commit()
    db_session.refresh(conn)
    return conn


def _pipeline(db_session, *, user_id, connection_id, owner_id, name="orders"):
    p = Pipeline(
        id=str(uuid.uuid4()),
        owner_scope_kind="user",
        owner_scope_id=owner_id,
        source_connection_id=connection_id,
        target_table=name,
        name=name,
        pipeline_fingerprint=str(uuid.uuid4()),
        created_by_user_id=user_id,
    )
    db_session.add(p)
    db_session.commit()
    return p


def _run(db_session, *, pipeline_id, started_at, status, error_message):
    r = PipelineRun(
        id=str(uuid.uuid4()),
        pipeline_id=pipeline_id,
        started_at=started_at,
        status=status,
        error_message=error_message,
        triggered_by="manual",
    )
    db_session.add(r)
    db_session.commit()
    return r


def _node(pipeline_id, *, name="orders", status="failed"):
    from backend.lineage import service
    return service.Node(
        id=f"pipeline:{pipeline_id}",
        kind="pipeline",
        name=name,
        meta={"pipeline_id": pipeline_id, "last_run_status": status},
    )


def test_pipeline_error_attaches_newest_failed_run(db_session, sample_user):
    """Among several runs, the node gets the *newest* failed run's error."""
    from backend.data_plane.scope import OwnerScope
    from backend.lineage import service

    conn = _connection(db_session, sample_user.id)
    p = _pipeline(db_session, user_id=sample_user.id,
                  connection_id=conn.id, owner_id=sample_user.id)
    _run(db_session, pipeline_id=p.id,
         started_at=datetime(2026, 6, 5, 12, 0), status="failed", error_message="old err")
    _run(db_session, pipeline_id=p.id,
         started_at=datetime(2026, 6, 6, 12, 0), status="failed", error_message="new err")
    _run(db_session, pipeline_id=p.id,
         started_at=datetime(2026, 6, 6, 13, 0), status="running", error_message=None)

    nodes = {f"pipeline:{p.id}": _node(p.id)}
    service._attach_errors(nodes, db_session, OwnerScope("user", sample_user.id))

    assert nodes[f"pipeline:{p.id}"].meta["error_message"] == "new err"


def test_pipeline_skips_non_failed_and_null_error_runs(db_session, sample_user):
    """A newer success run does not mask an older failed run's message —
    the SQL filters to status='failed' AND error_message IS NOT NULL."""
    from backend.data_plane.scope import OwnerScope
    from backend.lineage import service

    conn = _connection(db_session, sample_user.id)
    p = _pipeline(db_session, user_id=sample_user.id,
                  connection_id=conn.id, owner_id=sample_user.id)
    _run(db_session, pipeline_id=p.id,
         started_at=datetime(2026, 6, 5, 12, 0), status="failed", error_message="boom")
    # Newer, but excluded by the status / null-error filters.
    _run(db_session, pipeline_id=p.id,
         started_at=datetime(2026, 6, 6, 12, 0), status="success", error_message=None)
    _run(db_session, pipeline_id=p.id,
         started_at=datetime(2026, 6, 7, 12, 0), status="failed", error_message=None)

    nodes = {f"pipeline:{p.id}": _node(p.id)}
    service._attach_errors(nodes, db_session, OwnerScope("user", sample_user.id))

    assert nodes[f"pipeline:{p.id}"].meta["error_message"] == "boom"


def test_pipeline_errors_are_partitioned_per_pipeline(db_session, sample_user):
    """Two pipelines each receive their own newest failed run's error."""
    from backend.data_plane.scope import OwnerScope
    from backend.lineage import service

    conn = _connection(db_session, sample_user.id)
    p1 = _pipeline(db_session, user_id=sample_user.id,
                   connection_id=conn.id, owner_id=sample_user.id, name="orders")
    p2 = _pipeline(db_session, user_id=sample_user.id,
                   connection_id=conn.id, owner_id=sample_user.id, name="customers")
    _run(db_session, pipeline_id=p1.id,
         started_at=datetime(2026, 6, 6, 12, 0), status="failed", error_message="orders boom")
    _run(db_session, pipeline_id=p2.id,
         started_at=datetime(2026, 6, 6, 12, 0), status="failed", error_message="customers boom")

    nodes = {
        f"pipeline:{p1.id}": _node(p1.id, name="orders"),
        f"pipeline:{p2.id}": _node(p2.id, name="customers"),
    }
    service._attach_errors(nodes, db_session, OwnerScope("user", sample_user.id))

    assert nodes[f"pipeline:{p1.id}"].meta["error_message"] == "orders boom"
    assert nodes[f"pipeline:{p2.id}"].meta["error_message"] == "customers boom"


def test_pipeline_no_qualifying_run_leaves_node_unattributed(db_session, sample_user):
    """A failed node whose pipeline has no failed-with-message run gets nothing."""
    from backend.data_plane.scope import OwnerScope
    from backend.lineage import service

    conn = _connection(db_session, sample_user.id)
    p = _pipeline(db_session, user_id=sample_user.id,
                  connection_id=conn.id, owner_id=sample_user.id)
    _run(db_session, pipeline_id=p.id,
         started_at=datetime(2026, 6, 6, 12, 0), status="running", error_message=None)
    _run(db_session, pipeline_id=p.id,
         started_at=datetime(2026, 6, 6, 13, 0), status="success", error_message=None)

    nodes = {f"pipeline:{p.id}": _node(p.id)}
    service._attach_errors(nodes, db_session, OwnerScope("user", sample_user.id))

    assert "error_message" not in nodes[f"pipeline:{p.id}"].meta


def test_pipeline_success_node_is_never_attributed(db_session, sample_user):
    """A node whose last_run_status != 'failed' is excluded from the query set,
    even if the pipeline has a failed run with a message."""
    from backend.data_plane.scope import OwnerScope
    from backend.lineage import service

    conn = _connection(db_session, sample_user.id)
    p = _pipeline(db_session, user_id=sample_user.id,
                  connection_id=conn.id, owner_id=sample_user.id)
    _run(db_session, pipeline_id=p.id,
         started_at=datetime(2026, 6, 6, 12, 0), status="failed", error_message="boom")

    nodes = {f"pipeline:{p.id}": _node(p.id, status="success")}
    service._attach_errors(nodes, db_session, OwnerScope("user", sample_user.id))

    assert "error_message" not in nodes[f"pipeline:{p.id}"].meta
