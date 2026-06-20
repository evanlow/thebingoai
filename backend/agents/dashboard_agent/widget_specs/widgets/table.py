"""TableWidget — lean table params -> full widget JSON.

Agent emits: columns* [{column, label, sortable?, format?, ...}], title?,
            connectionId*, sql*, sources?
Hydrates:    config.columns (`key=` from each column entry) + table-level options;
            mapping.columnConfig (full display fields lifted from the same entry)
"""
from .base import BaseWidget, _pick


class TableWidget(BaseWidget):
    type = "table"
    has_data_source = True
    default_position = {"w": 12, "h": 5, "minW": 4, "minH": 3}
    params_doc = (
        "## Table params\n"
        "- `columns`* (array): one entry per SQL output column, written ONCE. Each item:\n"
        "  {column* (SQL name), label* , sortable?, filterable?, format? (number|currency|\n"
        "  percent|date|text), role? (dimension|metric), displayType? (number|bar|heatmap),\n"
        "  showBarValue?, compactNumbers?, aggregation?, comparisonCalc?, runningCalc?}\n"
        "- `title` (string), `pagination` (bool), `rowsPerPage` (number),\n"
        "  `showSummaryRow` (bool), `defaultSortKey` (string), `defaultSortDir` (asc|desc)\n"
        "- `connectionId`* (int), `sql`* (string), `sources` (string[])\n"
    )

    _CONFIG_EXTRA = ("title", "pagination", "rowsPerPage", "showSummaryRow",
                     "defaultSortKey", "defaultSortDir")
    # Display fields live on columnConfig; transform rebuilds config.columns from it.
    _COL_DISPLAY = ("label", "sortable", "filterable", "format", "role", "displayType",
                    "showBarValue", "compactNumbers", "aggregation", "comparisonCalc",
                    "runningCalc")

    def _config(self, params: dict) -> dict:
        cols = params.get("columns") or []
        config_cols = [
            {"key": c["column"], **_pick(c, ("label", "sortable", "filterable", "format"))}
            for c in cols
        ]
        return {"columns": config_cols, **_pick(params, self._CONFIG_EXTRA)}

    def _mapping(self, params: dict) -> dict:
        cols = params.get("columns") or []
        column_config = [
            {"column": c["column"], **_pick(c, self._COL_DISPLAY)} for c in cols
        ]
        return {"type": "table", "columnConfig": column_config}
