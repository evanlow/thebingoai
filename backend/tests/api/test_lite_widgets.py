"""Unit tests for the widget-config stripping used by GET /dashboards."""
from backend.api.dashboards import _lite_widgets, _skeleton_widgets


def test_strips_heavy_config_keys_keeps_structure():
    widgets = [
        {
            "id": "w-1",
            "position": {"x": 0, "y": 0, "w": 6, "h": 5},
            "widget": {
                "type": "chart",
                "config": {
                    "type": "bar",              # chart type — list UI needs this
                    "title": "Sales",
                    "rows": [[1, 2], [3, 4]],   # heavy — stripped
                    "columns": [{"key": "a"}],  # heavy — stripped
                    "data": {"labels": ["x"], "datasets": [{"data": [1]}]},  # heavy
                },
            },
        }
    ]
    out = _lite_widgets(widgets)
    cfg = out[0]["widget"]["config"]
    assert cfg == {"type": "bar", "title": "Sales"}
    # Structure the list view reads is preserved.
    assert out[0]["position"] == {"x": 0, "y": 0, "w": 6, "h": 5}
    assert out[0]["widget"]["type"] == "chart"
    # Original is not mutated.
    assert "rows" in widgets[0]["widget"]["config"]


def test_passes_through_non_dict_and_missing_config():
    widgets = ["legacy-string", {"id": "w-2", "widget": {"type": "text"}}, {"no_widget": True}]
    out = _lite_widgets(widgets)
    assert out == widgets


def test_handles_empty_and_none():
    assert _lite_widgets([]) == []
    assert _lite_widgets(None) == []


def test_skeleton_strips_values_keeps_columns_when_widget_has_datasource():
    widgets = [
        {
            "id": "w-1",
            "position": {"x": 0, "y": 0, "w": 12, "h": 5},
            "dataSource": {"connectionId": 1, "sql": "select 1"},  # will be refreshed
            "widget": {
                "type": "table",
                "config": {
                    "title": "Sales",
                    "columns": [{"key": "a"}, {"key": "b"}],  # KEPT — tables need it to render
                    "rows": [[1, 2], [3, 4]],                 # stripped (heavy value array)
                    "data": {"datasets": [{"data": [1]}]},    # stripped (heavy value array)
                },
            },
        }
    ]
    out = _skeleton_widgets(widgets)
    cfg = out[0]["widget"]["config"]
    assert cfg == {"title": "Sales", "columns": [{"key": "a"}, {"key": "b"}]}
    assert "rows" not in cfg and "data" not in cfg
    # Original not mutated.
    assert "rows" in widgets[0]["widget"]["config"]


def test_skeleton_keeps_static_widget_without_datasource():
    # No dataSource → nothing will refill it, so baked data must be preserved.
    widgets = [
        {
            "id": "w-2",
            "position": {"x": 0, "y": 0, "w": 6, "h": 4},
            "widget": {"type": "table", "config": {"rows": [[1]], "columns": [{"key": "a"}]}},
        }
    ]
    out = _skeleton_widgets(widgets)
    assert out[0]["widget"]["config"] == {"rows": [[1]], "columns": [{"key": "a"}]}


def test_skeleton_empty_and_none():
    assert _skeleton_widgets([]) == []
    assert _skeleton_widgets(None) == []
