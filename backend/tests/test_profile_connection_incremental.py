"""profile_connection saves partial context during the loop (every 50 tables),
not only at the end, so a crash mid-run keeps completed tables.

The DB session and all heavy collaborators are patched; no real DB/connector.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.tasks import profiling_tasks
from backend.models.database_connection import ProfilingStatus

_N_TABLES = 120  # > 2 * PARTIAL_SAVE_EVERY (50) → expect 2 partial saves + 1 final


def _schema():
    tables = {f"t{i}": {"columns": [{"name": "c", "type": "integer"}], "row_count": 0}
              for i in range(_N_TABLES)}
    return {"schemas": {"public": {"tables": tables}}, "table_names": list(tables), "relationships": []}


def test_partial_context_saved_during_loop():
    conn = SimpleNamespace(
        id=1, db_type="postgres", profiling_status=ProfilingStatus.PENDING.value,
        profiling_error=None, profiling_started_at=None, profiling_completed_at=None,
        profiling_progress=None, data_context=None,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = conn

    save_spy = MagicMock()

    with patch.object(profiling_tasks, "SessionLocal", return_value=db), \
         patch("backend.connectors.factory.get_connector_registration", return_value=None), \
         patch("backend.connectors.factory.get_connector_for_connection", return_value=MagicMock()), \
         patch("backend.services.schema_discovery.load_schema_file", return_value=_schema()), \
         patch("backend.services.table_profiler.profile_table",
               side_effect=lambda **kw: {"table_name": kw["table_name"],
                                         "columns": {"c": {"type": "numeric", "min": 1}}}), \
         patch("backend.services.connection_context.build_connection_context", return_value={}), \
         patch("backend.services.connection_context.save_connection_context", save_spy):
        profiling_tasks.profile_connection(conn.id)

    # 2 partial saves (at 50, 100) + 1 final save.
    assert save_spy.call_count == 3, save_spy.call_count
    assert conn.profiling_status == ProfilingStatus.READY.value
    assert conn.profiling_progress == f"{_N_TABLES}/{_N_TABLES} tables"


if __name__ == "__main__":
    test_partial_context_saved_during_loop()
    print("ok")
