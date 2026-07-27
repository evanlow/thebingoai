"""The created dashboard's own figures must reach the orchestrator.

The dashboard sub-agent never sees a number — widget SQL runs after it emits its
widgets — so before this the orchestrator could only report "created 13 widgets".
`_summarize_widgets` reads the already-executed widgets, and it is shared with
`analyze_dashboard` precisely because that function already draws the right line:
aggregates the user is looking at, never raw cell values.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.agents.orchestrator.orchestrator_dashboard_tools import (
    _attach_widget_summary,
    _summarize_widgets,
)

_KPI = {
    "id": "w1",
    "widget": {"type": "kpi", "config": {
        "label": "Total Employees", "value": 14999, "suffix": "", "trend": 4.2,
    }},
}
_CHART = {
    "id": "w2",
    "widget": {"type": "chart", "config": {
        "type": "line", "title": "Attrition by Month",
        "data": {
            "labels": ["Jan", "Feb", "Mar"],
            "datasets": [{"label": "Leavers", "data": [100, 150, 200]}],
        },
    }},
}
_TABLE = {
    "id": "w3",
    "widget": {"type": "table", "config": {
        "title": "Leavers by Role",
        "columns": ["role", "leavers"],
        "rows": [["Alice Tan", 3], ["Bob Lim", 5]],
    }},
}


def test_kpi_value_is_reported():
    [entry] = _summarize_widgets([_KPI])
    assert entry["type"] == "kpi"
    assert entry["label"] == "Total Employees"
    assert entry["value"] == 14999
    assert entry["trend"] == 4.2


def test_chart_series_is_reduced_to_aggregates():
    [entry] = _summarize_widgets([_CHART])
    [stats] = entry["dataset_stats"]
    assert stats["min"] == 100
    assert stats["max"] == 200
    assert stats["avg"] == 150.0
    assert stats["total"] == 450
    assert stats["trend"] == "increasing"
    assert stats["change_pct"] == 100.0


def test_no_raw_cell_value_survives_the_summary():
    """The privacy line: an aggregate of a rendered series is fair game, the cells
    behind it are not. Table rows and chart axis labels must not appear anywhere in
    the payload — only their counts."""
    payload = json.dumps(_summarize_widgets([_KPI, _CHART, _TABLE]))

    assert "Alice Tan" not in payload   # table row content
    assert "Bob Lim" not in payload
    assert "Jan" not in payload         # chart axis label
    assert "Feb" not in payload


def test_table_contributes_counts_only():
    [entry] = _summarize_widgets([_TABLE])
    assert entry["row_count"] == 2
    assert entry["column_count"] == 2
    assert "rows" not in entry


def test_chart_reports_label_count_not_labels():
    [entry] = _summarize_widgets([_CHART])
    assert entry["label_count"] == 3
    assert "labels" not in entry


def test_unexecuted_widgets_summarize_to_nothing_useful():
    """Guards the ordering contract: called before `_execute_widget_sql`, every
    entry comes back empty — which is why `_attach_widget_summary` reads the
    persisted row rather than the agent's emitted widgets."""
    lean = {"id": "w9", "widget": {"type": "kpi", "config": {"label": "Revenue"}}}
    [entry] = _summarize_widgets([lean])
    assert entry["value"] is None


# --- _attach_widget_summary --------------------------------------------------

class _FakeSession:
    """query(...).filter(...).scalar() returns the persisted widgets."""

    def __init__(self, widgets, raise_on_query=False):
        self._widgets = widgets
        self._raise = raise_on_query
        self.closed = False

    def query(self, *a, **k):
        if self._raise:
            raise RuntimeError("connection reset")
        return self

    def filter(self, *a, **k):
        return self

    def scalar(self):
        return self._widgets

    def close(self):
        self.closed = True


def _attach(result, widgets, raise_on_query=False):
    session = _FakeSession(widgets, raise_on_query)
    _attach_widget_summary(
        result, SimpleNamespace(user_id="u1"), lambda: session,
    )
    return session


def test_summary_and_narration_instruction_are_attached():
    result = {"success": True, "dashboard_id": 42, "message": "Dashboard 'HR' created with 3 widget(s)."}
    _attach(result, [_KPI, _CHART, _TABLE])

    assert len(result["widget_summary"]) == 3
    assert "widget_summary" in result["message"]
    assert "Dashboard 'HR' created" in result["message"]  # original message kept


def test_failed_creation_is_left_alone():
    result = {"success": False, "message": "Validation failed"}
    session = _attach(result, [_KPI])
    assert "widget_summary" not in result
    assert result["message"] == "Validation failed"
    assert session.closed is False  # never opened a session


def test_missing_dashboard_id_is_left_alone():
    result = {"success": True, "dashboard_id": None, "message": "ok"}
    _attach(result, [_KPI])
    assert "widget_summary" not in result


def test_a_db_failure_never_breaks_a_created_dashboard():
    """Narrating is a bonus. A read failure must not turn a successful creation into
    an error the user sees."""
    result = {"success": True, "dashboard_id": 42, "message": "created"}
    session = _attach(result, [_KPI], raise_on_query=True)

    assert "widget_summary" not in result
    assert result["message"] == "created"
    assert session.closed is True  # session still released


def test_analyze_dashboard_uses_the_same_summarizer():
    """The extraction must not have forked the two paths — the whole point of
    sharing is that analyze_dashboard's privacy line applies to creation too."""
    from backend.agents.orchestrator import orchestrator_dashboard_tools as odt
    import inspect

    src = inspect.getsource(odt._do_analyze_dashboard)
    assert "_summarize_widgets(widgets)" in src
