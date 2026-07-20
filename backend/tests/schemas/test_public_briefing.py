from backend.schemas.briefing import strip_widget


def test_strip_widget_drops_datasource_and_sources():
    w = {
        "id": "chart_1",
        "title": "Revenue",
        "widget": {"config": {"type": "line"}},
        "dataSource": {"sql": "SELECT secret FROM revenue", "connectionId": "conn-abc"},
        "sources": [{"table": "revenue"}],
    }
    out = strip_widget(w)
    assert out == {"id": "chart_1", "title": "Revenue", "widget": {"config": {"type": "line"}}}


def test_strip_widget_is_an_allowlist_not_a_denylist():
    # A newly-added secret-bearing key must NOT survive by default.
    w = {"id": "c1", "widget": {}, "someFutureSecret": "leak-me"}
    assert "someFutureSecret" not in strip_widget(w)


def test_strip_widget_tolerates_missing_keys():
    assert strip_widget({"id": "c1"}) == {"id": "c1"}
