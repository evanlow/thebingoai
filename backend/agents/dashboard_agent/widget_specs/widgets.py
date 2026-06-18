"""Base-widget hydration.

The dashboard agent emits a *lean* param object per widget (semantic content
only — no position, no envelopes, no duplicated mapping columns). `build_widgets`
expands those into the full widget JSON the rest of the pipeline persists:

    {id, position, widget:{type, config}, dataSource?:{connectionId, sql, mapping}}

`mapping` is derived from the same params (the keys `transform_widget_data`
reads), so the agent never writes config columns and mapping columns twice.
Position is seeded from per-type defaults and reflowed by
`normalize_dashboard_layout` afterwards — the agent does not emit coordinates.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


def _pick(params: dict, keys: tuple[str, ...]) -> dict:
    """Copy the keys that are present (and not None) from params."""
    return {k: params[k] for k in keys if params.get(k) is not None}


class BaseWidget(ABC):
    type: str
    params_doc: str = ""            # lean field list, rendered into the widget spec
    has_data_source: bool = True
    default_position: dict = {"w": 6, "h": 4}

    def build(self, params: dict, widget_id: str) -> dict:
        """Lean params -> full widget JSON."""
        wh = dict(self.default_position)
        # Optional emphasis: agent may set `width` on a widget it wants larger.
        # Used only as the packing SEED — normalize_dashboard_layout still
        # enforces sum-to-12 + overlap + per-type min/max. Omitted = type default.
        if isinstance(params.get("width"), int):
            wh["w"] = params["width"]

        out: dict = {
            "id": widget_id,
            # Seed a complete default position so the verifiers pass;
            # normalize_dashboard_layout reflows x/y/h and packs w afterwards.
            "position": {"x": 0, "y": 0, **wh},
            "widget": {"type": self.type, "config": self._config(params)},
        }
        if params.get("sources") is not None:
            out["sources"] = params["sources"]
        if self.has_data_source:
            out["dataSource"] = {
                "connectionId": params.get("connectionId"),
                "sql": params.get("sql"),
                "mapping": self._mapping(params),
            }
        return out

    @abstractmethod
    def _config(self, params: dict) -> dict:
        ...

    def _mapping(self, params: dict) -> dict:
        raise NotImplementedError(f"{self.type} widget has no dataSource mapping")


class KpiWidget(BaseWidget):
    type = "kpi"
    has_data_source = True
    default_position = {"w": 3, "h": 2, "minW": 2, "minH": 2}
    params_doc = (
        "## KPI params\n"
        "- `label`* (string): card label (NOT 'title')\n"
        "- `valueColumn`* (string): SQL column holding the value\n"
        "- `aggregation` (sum|avg|count|countDistinct|min|max|first|last): default 'first'\n"
        "- `prefix`/`suffix` (string), `compactNumbers`/`roundValue` (bool), `decimalPlaces` (number)\n"
        "- `comparison` (object), `progressVisual` (bar|circle|none)\n"
        "- trend: `autoTrend` (bool), `periodLabel`, `trendDateColumn`, `trendValueColumn`,\n"
        "  `sparklineXColumn`, `sparklineYColumn`, `sparklineSortColumn`, `sparklineSortDirection`\n"
        "- `connectionId`* (int), `sql`* (string), `sources` (string[])\n"
    )

    _CONFIG_KEYS = ("label", "prefix", "suffix", "roundValue", "decimalPlaces",
                    "compactNumbers", "comparison", "progressVisual")
    _MAPPING_KEYS = ("valueColumn", "aggregation", "autoTrend", "periodLabel",
                     "trendDateColumn", "trendValueColumn", "sparklineXColumn",
                     "sparklineYColumn", "sparklineSortColumn", "sparklineSortDirection")

    def _config(self, params: dict) -> dict:
        return _pick(params, self._CONFIG_KEYS)

    def _mapping(self, params: dict) -> dict:
        return {"type": "kpi", **_pick(params, self._MAPPING_KEYS)}


class ChartWidget(BaseWidget):
    type = "chart"
    has_data_source = True
    default_position = {"w": 6, "h": 5, "minW": 3, "minH": 3}
    params_doc = (
        "## Chart params\n"
        "- `chartType`* (bar|line|pie|doughnut|area|scatter)\n"
        "- `title` (string), `description` (string)\n"
        "- `options` (object): stacked, indexAxis, xAxisMode, showValues, showLegend,\n"
        "  legendPosition, showGrid, sortBy, sortDirection, referenceLines, sliceLabel, ...\n"
        "- `animation` (object)\n"
        "- `labelColumn` (string): x-axis / slice names (all types except pure scatter)\n"
        "- `datasetColumns` (array of {column, label, aggregation?, seriesType?, yAxisID?, ...})\n"
        "- scatter: `xMetricColumn`, `yMetricColumn`, `xAggregation`, `yAggregation`\n"
        "- `connectionId`* (int), `sql`* (string), `sources` (string[])\n"
    )

    _CONFIG_KEYS = ("title", "description", "options", "animation")
    _MAPPING_KEYS = ("labelColumn", "datasetColumns", "xMetricColumn",
                     "yMetricColumn", "xAggregation", "yAggregation")

    def _config(self, params: dict) -> dict:
        return {"type": params.get("chartType"), **_pick(params, self._CONFIG_KEYS)}

    def _mapping(self, params: dict) -> dict:
        # chartType is required by transform_widget_data (scatter {x,y} depends on it).
        return {
            "type": "chart",
            "chartType": params.get("chartType"),
            **_pick(params, self._MAPPING_KEYS),
        }


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


class TextWidget(BaseWidget):
    type = "text"
    has_data_source = False
    default_position = {"w": 12, "h": 1, "minW": 2, "minH": 1}
    params_doc = (
        "## Text params\n"
        "- `content`* (string): markdown; use ## for section headers\n"
        "- `alignment` (left|center|right)\n"
    )

    def _config(self, params: dict) -> dict:
        return _pick(params, ("content", "alignment"))


WIDGET_REGISTRY: dict[str, BaseWidget] = {
    w.type: w for w in (
        KpiWidget(), ChartWidget(), TableWidget(),
        PivotTableWidget(), FilterWidget(), TextWidget(),
    )
}


def build_widgets(lean: list) -> list:
    """Expand lean per-widget params into full widget JSON.

    Already-full widgets (carrying a "widget" envelope) and unknown types pass
    through untouched so existing-dashboard context and the verifier still work.
    """
    if not isinstance(lean, list):
        return lean
    out: list = []
    for i, lw in enumerate(lean):
        if not isinstance(lw, dict) or "widget" in lw:
            out.append(lw)
            continue
        builder = WIDGET_REGISTRY.get(lw.get("type"))
        if builder is None:
            out.append(lw)
            continue
        widget_id = lw.get("id") or f"{lw['type']}_{i}"
        out.append(builder.build(lw, widget_id))
    return out
