"""FilterWidget — filter bar (no dataSource).

Agent emits: controls* [{type, label, key, column*, optionsSource?, dateRangeSource?, ...}]
Hydrates:    config.controls (passed through).
"""
from .base import BaseWidget


class FilterWidget(BaseWidget):
    type = "filter"
    has_data_source = False
    default_position = {"w": 12, "h": 2, "minW": 4, "minH": 2}
    params_doc = (
        "## Filter params (NO connectionId/sql/mapping at widget level)\n"
        "- `controls`* (array): each {type* (dropdown|date_range|search), label*, key*,\n"
        "  column* (real DB column), dimension?, multiple?, options?, optionsSource?\n"
        "  {connectionId, sql} (dropdown), dateRangeSource? {connectionId, sql},\n"
        "  dateRangeDefault? (full|7d|30d|90d|ytd)}\n"
    )

    def _config(self, params: dict) -> dict:
        return {"controls": params.get("controls") or []}
