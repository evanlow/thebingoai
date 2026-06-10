"""Tests for transform_table columnConfig passthrough."""
from backend.connectors.base import QueryResult
from backend.services.widget_transform import transform_table


def _result():
    return QueryResult(
        columns=["region", "revenue"],
        rows=[("EU", 100), ("US", 200)],
        row_count=2,
        execution_time_ms=1.0,
    )


def test_extended_column_fields_pass_through():
    mapping = {
        "type": "table",
        "columnConfig": [
            {"column": "region", "label": "Region", "role": "dimension", "filterable": True},
            {
                "column": "revenue",
                "label": "Revenue",
                "sortable": True,
                "format": "currency",
                "role": "metric",
                "displayType": "bar",
                "showBarValue": True,
                "compactNumbers": True,
                "aggregation": "sum",
                "comparisonCalc": "percentOfTotal",
                "runningCalc": "runningSum",
            },
        ],
    }
    config = transform_table(_result(), mapping)
    region, revenue = config["columns"]
    assert region == {"key": "region", "label": "Region", "role": "dimension", "filterable": True}
    assert revenue["displayType"] == "bar"
    assert revenue["showBarValue"] is True
    assert revenue["compactNumbers"] is True
    assert revenue["aggregation"] == "sum"
    assert revenue["comparisonCalc"] == "percentOfTotal"
    assert revenue["runningCalc"] == "runningSum"
    assert revenue["sortable"] is True
    assert revenue["format"] == "currency"


def test_unknown_keys_not_leaked():
    mapping = {
        "type": "table",
        "columnConfig": [{"column": "region", "label": "Region", "bogusKey": 1}],
    }
    config = transform_table(_result(), mapping)
    assert "bogusKey" not in config["columns"][0]


def test_rows_unaffected():
    mapping = {
        "type": "table",
        "columnConfig": [
            {"column": "region", "label": "Region"},
            {"column": "revenue", "label": "Revenue", "displayType": "heatmap"},
        ],
    }
    config = transform_table(_result(), mapping)
    assert config["rows"] == [
        {"region": "EU", "revenue": 100},
        {"region": "US", "revenue": 200},
    ]
