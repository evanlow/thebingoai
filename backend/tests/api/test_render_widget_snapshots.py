import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from backend.api.widget_data import render_widget_snapshots


def _dashboard():
    return SimpleNamespace(
        id=1,
        widgets=[
            {"id": "w_ok", "dataSource": {"connectionId": 5, "sql": "select 1", "mapping": {"x": ["a"]}},
             "widget": {"config": {"type": "bar"}}},
            {"id": "w_nodata", "widget": {"config": {"type": "kpi"}}},  # no dataSource → skip
        ],
    )


def test_snapshots_only_referenced_renderable_widgets():
    async def fake_refresh(request, current_user, db):
        return SimpleNamespace(config={"served": request.widget_id})

    with patch("backend.api.widget_data.refresh_widget", side_effect=fake_refresh):
        out = asyncio.run(render_widget_snapshots(
            _dashboard(), ["w_ok", "w_nodata", "w_missing", None], user=object(), db=object(),
        ))

    # Only the widget with a complete dataSource is snapshot; others skipped.
    assert out == {"w_ok": {"served": "w_ok"}}


def test_failing_widget_is_skipped_not_fatal():
    async def boom(request, current_user, db):
        raise RuntimeError("query blew up")

    with patch("backend.api.widget_data.refresh_widget", side_effect=boom):
        out = asyncio.run(render_widget_snapshots(
            _dashboard(), ["w_ok"], user=object(), db=object(),
        ))

    assert out == {}
