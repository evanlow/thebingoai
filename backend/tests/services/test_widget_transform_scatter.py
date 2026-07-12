"""Tests for transform_chart scatter/bubble: dimension grouping, bubble size,
series naming, and the 1000-point downsample cap."""
from backend.connectors.base import QueryResult
from backend.services.widget_transform import transform_chart


def _result():
    return QueryResult(
        columns=["price", "score", "room_type", "reviews"],
        rows=[
            (100, 4.5, "Private", 10),
            (200, 3.0, "Entire", 25),
            (150, 5.0, "Private", 5),
        ],
        row_count=3,
        execution_time_ms=1.0,
    )


def test_scatter_plain_xy():
    config = transform_chart(_result(), {
        "type": "chart", "xMetricColumn": "price", "yMetricColumn": "score",
    })
    (ds,) = config["data"]["datasets"]
    assert ds["label"] == "score vs price"
    assert ds["data"] == [
        {"x": 100, "y": 4.5}, {"x": 200, "y": 3.0}, {"x": 150, "y": 5.0},
    ]


def test_scatter_grouped_by_dimension():
    config = transform_chart(_result(), {
        "type": "chart", "xMetricColumn": "price", "yMetricColumn": "score",
        "labelColumn": "room_type",
    })
    datasets = {ds["label"]: ds["data"] for ds in config["data"]["datasets"]}
    assert set(datasets) == {"Private", "Entire"}
    assert datasets["Private"] == [{"x": 100, "y": 4.5}, {"x": 150, "y": 5.0}]
    assert datasets["Entire"] == [{"x": 200, "y": 3.0}]


def test_bubble_chart_type_size_metric():
    config = transform_chart(_result(), {
        "type": "chart", "chartType": "bubble",
        "xMetricColumn": "price", "yMetricColumn": "score",
        "sizeMetricColumn": "reviews",
    })
    (ds,) = config["data"]["datasets"]
    assert ds["label"] == "score vs price"
    assert ds["data"][0] == {"x": 100, "y": 4.5, "r": 10}
    assert ds["data"][1] == {"x": 200, "y": 3.0, "r": 25}


def test_scatter_caps_at_1000_points():
    result = QueryResult(
        columns=["x", "y"],
        rows=[(i, i * 2) for i in range(5000)],
        row_count=5000,
        execution_time_ms=1.0,
    )
    config = transform_chart(result, {
        "type": "chart", "xMetricColumn": "x", "yMetricColumn": "y",
    })
    (ds,) = config["data"]["datasets"]
    assert len(ds["data"]) == 1000
    assert ds["data"][0] == {"x": 0, "y": 0}  # even sampling keeps first point


def test_scatter_y_aggregation_ignores_grouping():
    config = transform_chart(_result(), {
        "type": "chart", "xMetricColumn": "room_type", "yMetricColumn": "price",
        "yAggregation": "avg", "labelColumn": "room_type",
    })
    (ds,) = config["data"]["datasets"]
    assert ds["label"] == "price vs room_type"
    assert ds["data"] == [{"x": "Private", "y": 125.0}, {"x": "Entire", "y": 200.0}]
