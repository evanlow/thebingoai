"""Smoke tests for widget spec rendering.

Schema JSONs are loaded with errors silently swallowed (widget_specs._warm_cache),
so a syntax error would silently drop a widget type from the agent's spec tool.
These tests guard against that.
"""
import pytest

from backend.agents.dashboard_agent.widget_specs import get_available_types, get_widget_spec

ALL_TYPES = ("kpi", "chart", "table", "pivot_table", "filter", "text")


def test_all_types_available():
    assert set(get_available_types()) == set(ALL_TYPES)


@pytest.mark.parametrize("widget_type", ALL_TYPES)
def test_spec_renders_non_empty(widget_type):
    spec = get_widget_spec(widget_type)
    assert spec and widget_type in spec


def test_chart_spec_includes_new_features():
    spec = get_widget_spec("chart")
    assert "sliceLabel" in spec
    assert "trendline" in spec
    assert "referenceLines" in spec
    assert "cumulative" in spec


def test_kpi_spec_includes_new_features():
    spec = get_widget_spec("kpi")
    assert "compactNumbers" in spec
    assert "comparison" in spec
    assert "progressVisual" in spec


def test_table_spec_includes_new_features():
    spec = get_widget_spec("table")
    assert "displayType" in spec
    assert "comparisonCalc" in spec
    assert "runningCalc" in spec
    assert "showSummaryRow" in spec


def test_pivot_spec_includes_sorting():
    spec = get_widget_spec("pivot_table")
    assert "sortBy" in spec
    assert "sortDir" in spec
