"""PivotTableWidget — lean pivot params -> full widget JSON.

Agent emits: rowDimensions*, columnDimensions?, values*, title?,
            connectionId*, sql*, sources?
Hydrates:    config{rowDimensions, columnDimensions, values, ...};
            mapping.columnConfig = auto-union of every column referenced by
            rowDimensions + columnDimensions + values (de-duped, first label wins)
"""
from .base import BaseWidget, _pick


class PivotTableWidget(BaseWidget):
    type = "pivot_table"
    has_data_source = True
    default_position = {"w": 8, "h": 5, "minW": 4, "minH": 3}
    params_doc = (
        "## Pivot table params\n"
        "- `rowDimensions`* (array of {column*, label?}): row breakdown, outer→inner\n"
        "- `columnDimensions` (array of {column*, label?}, max 2): column breakdown\n"
        "- `values`* (array of {column*, label?, aggregation* (sum|average|count|\n"
        "  countDistinct|min|max|median|stdDev|variance), format?}): cell metrics\n"
        "- `expandCollapse`, `defaultExpandLevel`, `showRowTotals`, `showColumnTotals`,\n"
        "  `rowLimit`, `columnLimit`, `sortBy`, `sortDir`\n"
        "- `connectionId`* (int), `sql`* (string), `sources` (string[])\n"
        "mapping.columnConfig is auto-derived from rowDimensions+columnDimensions+values.\n"
    )

    _CONFIG_KEYS = ("title", "rowDimensions", "columnDimensions", "values",
                    "expandCollapse", "defaultExpandLevel", "showRowTotals",
                    "showColumnTotals", "rowLimit", "columnLimit", "sortBy", "sortDir")

    def _config(self, params: dict) -> dict:
        return _pick(params, self._CONFIG_KEYS)

    def _mapping(self, params: dict) -> dict:
        # Union of every column referenced by the three dimension/value lists,
        # de-duplicated by SQL column name (first label wins).
        column_config: list[dict] = []
        seen: set[str] = set()
        for group in ("rowDimensions", "columnDimensions", "values"):
            for item in params.get(group) or []:
                col = item.get("column")
                if not col or col in seen:
                    continue
                seen.add(col)
                column_config.append({"column": col, **_pick(item, ("label",))})
        return {"type": "pivot_table", "columnConfig": column_config}
