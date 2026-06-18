"""Tests for lean-param -> full widget JSON hydration (widget_specs/widgets.py).

Covers each BaseWidget subclass's build()/config/mapping, the BaseWidget
envelope, the _pick helper, build_widgets, and an end-to-end regression
(build -> verify -> layout) that guards the agent-omits-position contract.
"""

from backend.agents.dashboard_agent.widget_specs.widgets import (
    _pick,
    build_widgets,
    WIDGET_REGISTRY,
    BaseWidget,
    KpiWidget,
    ChartWidget,
    TableWidget,
    PivotTableWidget,
    FilterWidget,
    TextWidget,
)


# --------------------------------------------------------------------------- #
# _pick helper
# --------------------------------------------------------------------------- #

def test_pick_drops_absent_and_none():
    params = {"a": 1, "b": None, "c": "x"}
    assert _pick(params, ("a", "b", "c", "d")) == {"a": 1, "c": "x"}


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

def test_registry_keys_match_types():
    assert set(WIDGET_REGISTRY) == {"kpi", "chart", "table", "pivot_table", "filter", "text"}
    for wtype, builder in WIDGET_REGISTRY.items():
        assert builder.type == wtype
        assert isinstance(builder, BaseWidget)
        assert builder.params_doc  # spec source must be non-empty


# --------------------------------------------------------------------------- #
# KpiWidget
# --------------------------------------------------------------------------- #

def test_kpi_minimal_build():
    w = KpiWidget().build(
        {"label": "Rev", "valueColumn": "revenue", "connectionId": 1, "sql": "SELECT 1 AS revenue"},
        "kpi_1",
    )
    assert w["id"] == "kpi_1"
    assert w["widget"] == {"type": "kpi", "config": {"label": "Rev"}}
    assert w["dataSource"]["mapping"] == {"type": "kpi", "valueColumn": "revenue"}
    assert set(w["position"]) >= {"x", "y", "w", "h"}
    assert "sources" not in w  # omitted when absent


def test_kpi_full_config_and_trend_mapping():
    w = KpiWidget().build(
        {
            "label": "Rev", "prefix": "$", "suffix": "K",
            "compactNumbers": True, "roundValue": True, "decimalPlaces": 1,
            "comparison": {"type": "value", "targetValue": 100},
            "progressVisual": "bar",
            "valueColumn": "revenue", "aggregation": "sum",
            "autoTrend": True, "periodLabel": "vs last month",
            "trendDateColumn": "d", "trendValueColumn": "tv",
            "sparklineXColumn": "sx", "sparklineYColumn": "sy",
            "sparklineSortColumn": "ss", "sparklineSortDirection": "asc",
            "connectionId": 1, "sql": "SELECT 1",
        },
        "kpi_2",
    )
    cfg = w["widget"]["config"]
    assert cfg == {
        "label": "Rev", "prefix": "$", "suffix": "K", "compactNumbers": True,
        "roundValue": True, "decimalPlaces": 1,
        "comparison": {"type": "value", "targetValue": 100}, "progressVisual": "bar",
    }
    m = w["dataSource"]["mapping"]
    assert m == {
        "type": "kpi", "valueColumn": "revenue", "aggregation": "sum",
        "autoTrend": True, "periodLabel": "vs last month",
        "trendDateColumn": "d", "trendValueColumn": "tv",
        "sparklineXColumn": "sx", "sparklineYColumn": "sy",
        "sparklineSortColumn": "ss", "sparklineSortDirection": "asc",
    }


# --------------------------------------------------------------------------- #
# ChartWidget
# --------------------------------------------------------------------------- #

def test_chart_config_type_options_animation():
    w = ChartWidget().build(
        {
            "chartType": "bar", "title": "T", "description": "D",
            "options": {"stacked": "standard", "showLegend": True},
            "animation": {"entrance": "fadeIn"},
            "labelColumn": "region",
            "datasetColumns": [{"column": "revenue", "label": "Revenue"}],
            "connectionId": 1, "sql": "SELECT region, revenue FROM t",
        },
        "chart_1",
    )
    assert w["widget"]["config"] == {
        "type": "bar", "title": "T", "description": "D",
        "options": {"stacked": "standard", "showLegend": True},
        "animation": {"entrance": "fadeIn"},
    }
    m = w["dataSource"]["mapping"]
    assert m == {
        "type": "chart", "chartType": "bar",
        "labelColumn": "region",
        "datasetColumns": [{"column": "revenue", "label": "Revenue"}],
    }


def test_chart_scatter_metric_columns_and_charttype():
    w = ChartWidget().build(
        {
            "chartType": "scatter",
            "xMetricColumn": "ts", "yMetricColumn": "bpm",
            "xAggregation": "avg", "yAggregation": "avg",
            "connectionId": 1, "sql": "SELECT ts, bpm FROM m",
        },
        "chart_s",
    )
    assert w["widget"]["config"]["type"] == "scatter"
    m = w["dataSource"]["mapping"]
    assert m["chartType"] == "scatter"  # scatter {x,y} depends on it
    assert m["xMetricColumn"] == "ts" and m["yMetricColumn"] == "bpm"
    assert m["xAggregation"] == "avg" and m["yAggregation"] == "avg"
    assert "labelColumn" not in m


# --------------------------------------------------------------------------- #
# TableWidget
# --------------------------------------------------------------------------- #

def test_table_columns_once_feed_config_and_mapping():
    w = TableWidget().build(
        {
            "title": "Top", "pagination": True, "rowsPerPage": 25,
            "showSummaryRow": True, "defaultSortKey": "price", "defaultSortDir": "desc",
            "columns": [
                {"column": "address", "label": "Address"},
                {"column": "price", "label": "Price", "sortable": True, "filterable": True,
                 "format": "currency", "role": "metric", "displayType": "bar",
                 "showBarValue": True, "compactNumbers": True, "aggregation": "sum",
                 "comparisonCalc": "percentOfTotal", "runningCalc": "runningSum"},
            ],
            "connectionId": 1, "sql": "SELECT address, price FROM listings",
        },
        "table_1",
    )
    cfg = w["widget"]["config"]
    # config.columns uses `key`, only the display-light fields
    assert cfg["columns"] == [
        {"key": "address", "label": "Address"},
        {"key": "price", "label": "Price", "sortable": True, "filterable": True, "format": "currency"},
    ]
    assert cfg["title"] == "Top" and cfg["pagination"] is True and cfg["rowsPerPage"] == 25
    assert cfg["showSummaryRow"] is True and cfg["defaultSortKey"] == "price" and cfg["defaultSortDir"] == "desc"
    # mapping.columnConfig uses `column` + ALL extended display fields
    cc = w["dataSource"]["mapping"]["columnConfig"]
    assert cc[0] == {"column": "address", "label": "Address"}
    assert cc[1] == {
        "column": "price", "label": "Price", "sortable": True, "filterable": True,
        "format": "currency", "role": "metric", "displayType": "bar",
        "showBarValue": True, "compactNumbers": True, "aggregation": "sum",
        "comparisonCalc": "percentOfTotal", "runningCalc": "runningSum",
    }


# --------------------------------------------------------------------------- #
# PivotTableWidget
# --------------------------------------------------------------------------- #

def test_pivot_config_and_deduped_columnconfig():
    w = PivotTableWidget().build(
        {
            "title": "P",
            "rowDimensions": [{"column": "region", "label": "Region"}],
            "columnDimensions": [{"column": "quarter"}],
            "values": [
                {"column": "revenue", "label": "Revenue", "aggregation": "sum"},
                {"column": "region", "label": "dup"},  # duplicate column
            ],
            "expandCollapse": True, "defaultExpandLevel": 1,
            "showRowTotals": False, "showColumnTotals": True,
            "rowLimit": 50, "columnLimit": 10, "sortBy": "revenue", "sortDir": "desc",
            "connectionId": 1, "sql": "SELECT region, quarter, revenue FROM s",
        },
        "pivot_1",
    )
    cfg = w["widget"]["config"]
    assert cfg["values"][0]["aggregation"] == "sum"  # aggregation kept in config
    assert cfg["expandCollapse"] is True and cfg["sortDir"] == "desc"
    cc = w["dataSource"]["mapping"]["columnConfig"]
    assert [c["column"] for c in cc] == ["region", "quarter", "revenue"]  # union, first-wins
    # columnConfig carries only column + label (no aggregation)
    assert all(set(c) <= {"column", "label"} for c in cc)
    assert w["dataSource"]["mapping"]["type"] == "pivot_table"


# --------------------------------------------------------------------------- #
# Filter / Text (no dataSource)
# --------------------------------------------------------------------------- #

def test_filter_no_datasource_multiple_controls():
    w = FilterWidget().build(
        {"controls": [
            {"type": "dropdown", "label": "Region", "key": "r", "column": "region"},
            {"type": "date_range", "label": "Date", "key": "d", "column": "order_date",
             "dateRangeDefault": "full"},
        ]},
        "filter_1",
    )
    assert "dataSource" not in w
    assert len(w["widget"]["config"]["controls"]) == 2
    assert w["widget"]["config"]["controls"][1]["dateRangeDefault"] == "full"


def test_text_alignment_optional():
    full = TextWidget().build({"content": "## Detail", "alignment": "center"}, "t_1")
    bare = TextWidget().build({"content": "## Detail"}, "t_2")
    assert "dataSource" not in full
    assert full["widget"]["config"] == {"content": "## Detail", "alignment": "center"}
    assert bare["widget"]["config"] == {"content": "## Detail"}


# --------------------------------------------------------------------------- #
# BaseWidget envelope
# --------------------------------------------------------------------------- #

def test_sources_included_when_present():
    w = KpiWidget().build(
        {"label": "X", "valueColumn": "v", "connectionId": 1, "sql": "SELECT 1", "sources": ["orders"]},
        "k",
    )
    assert w["sources"] == ["orders"]


def test_width_hint_seeds_position_w():
    w = ChartWidget().build(
        {"chartType": "line", "labelColumn": "d", "datasetColumns": [],
         "connectionId": 1, "sql": "SELECT 1", "width": 8},
        "chart_w",
    )
    assert w["position"]["w"] == 8


def test_default_position_per_type():
    assert KpiWidget().build({"label": "x", "valueColumn": "v", "connectionId": 1, "sql": "s"}, "i")["position"]["w"] == 3
    assert TableWidget().build({"columns": [], "connectionId": 1, "sql": "s"}, "i")["position"]["w"] == 12
    assert FilterWidget().build({"controls": []}, "i")["position"]["h"] == 2


# --------------------------------------------------------------------------- #
# build_widgets
# --------------------------------------------------------------------------- #

def test_build_widgets_id_autogen_and_passthrough():
    full_widget = {"id": "keep", "position": {"x": 0, "y": 0, "w": 6, "h": 5},
                   "widget": {"type": "chart", "config": {"type": "bar"}}}
    out = build_widgets([
        {"type": "text", "content": "## A"},   # hydrated, auto id text_0
        full_widget,                            # passthrough (has "widget")
        {"type": "bogus", "foo": 1},            # passthrough (unknown type)
        "not-a-dict",                           # passthrough (non-dict)
    ])
    assert out[0]["id"] == "text_0" and out[0]["widget"]["type"] == "text"
    assert out[1] is full_widget
    assert out[2] == {"type": "bogus", "foo": 1}
    assert out[3] == "not-a-dict"


def test_build_widgets_preserves_explicit_id():
    out = build_widgets([{"type": "kpi", "id": "my_kpi", "label": "X",
                          "valueColumn": "v", "connectionId": 1, "sql": "SELECT 1 AS v"}])
    assert out[0]["id"] == "my_kpi"


def test_build_widgets_non_list_and_empty():
    assert build_widgets("nope") == "nope"
    assert build_widgets([]) == []


# --------------------------------------------------------------------------- #
# Integration: build -> verify -> layout (agent omits position)
# --------------------------------------------------------------------------- #

def test_lean_dashboard_verifies_and_lays_out():
    from backend.agents.dashboard_tools import _verify_widgets
    from backend.agents.dashboard_layout import normalize_dashboard_layout

    lean = [{"type": "filter", "controls": [{"type": "dropdown", "label": "R", "key": "r", "column": "r"}]}]
    for i in range(4):
        lean.append({"type": "kpi", "label": f"M{i}", "valueColumn": "v", "connectionId": 1, "sql": "SELECT 1 AS v"})
    lean += [
        {"type": "chart", "chartType": "bar", "labelColumn": "r",
         "datasetColumns": [{"column": "v", "label": "V"}], "connectionId": 1, "sql": "SELECT r,v FROM t"},
        {"type": "chart", "chartType": "line", "labelColumn": "d",
         "datasetColumns": [{"column": "v", "label": "V"}], "connectionId": 1, "sql": "SELECT d,v FROM t"},
        {"type": "text", "content": "## Detail"},
        {"type": "table", "columns": [{"column": "a", "label": "A"}], "connectionId": 1, "sql": "SELECT a FROM t"},
    ]
    full = build_widgets(lean)

    # Hydrated widgets pass the pre-persistence gate (build() seeds full shape).
    assert _verify_widgets(full, None) == []

    # Layout reflows from emission order alone — no agent-supplied position.
    normalize_dashboard_layout(full)
    rows: dict[int, list] = {}
    for w in full:
        rows.setdefault(w["position"]["y"], []).append((w["widget"]["type"], w["position"]["w"]))
    ys = sorted(rows)
    assert rows[ys[0]] == [("filter", 12)]
    assert rows[ys[1]] == [("kpi", 3), ("kpi", 3), ("kpi", 3), ("kpi", 3)]
    assert sorted(t for t, _ in rows[ys[2]]) == ["chart", "chart"]
    assert all(w == 6 for _, w in rows[ys[2]])
    assert ("text", 12) in rows[ys[3]]
    assert ("table", 12) in rows[ys[4]]
