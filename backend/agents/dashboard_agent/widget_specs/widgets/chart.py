"""ChartWidget — lean chart params -> full widget JSON.

Agent emits: chartType*, title?, labelColumn?, datasetColumns*, options?,
            connectionId*, sql*, sources?
Hydrates:    config{type:chartType, title, options, animation};
            mapping{type:"chart", labelColumn, datasetColumns, chartType, ...}
"""
from .base import BaseWidget, _pick


class ChartWidget(BaseWidget):
    type = "chart"
    has_data_source = True
    default_position = {"w": 6, "h": 5, "minW": 3, "minH": 3}
    params_doc = (
        "## Chart params\n"
        "- `chartType`* (bar|line|pie|doughnut|area|scatter|bubble|funnel|timeline)\n"
        "- `title` (string), `description` (string)\n"
        "- `options` (object): stacked, indexAxis, xAxisMode, showValues, showLegend,\n"
        "  legendPosition, showGrid, sortBy, sortDirection, referenceLines, referenceBands, sliceLabel, ...\n"
        "  funnel: `funnelShape` (smoothed|stepped), `funnelLabelMode` (number|percentage|numberPercentage),\n"
        "  `funnelPercentType` (max|previous), `funnelColorMode` (single|byValue)\n"
        "  timeline: `timelineGroupByRowLabel`, `timelineColorBy` (row|bar), `timelineAltRows`\n"
        "- `animation` (object)\n"
        "- `labelColumn` (string): x-axis / slice names (all types except pure scatter); for funnel = stage names; for timeline = the row/lane label\n"
        "- `datasetColumns` (array of {column, label, aggregation?, seriesType?, yAxisID?, ...}); funnel = one entry = stage value\n"
        "- `dateGranularity` (string): bucket a timestamp labelColumn (year|quarter|month|week|day|hour|hour_of_day|day_of_week|month_of_year)\n"
        "- `breakdownColumn` (string): split the first metric into one series per distinct value\n"
        "- scatter: `xMetricColumn`, `yMetricColumn`, `xAggregation`, `yAggregation`; optional `labelColumn` groups/colors points per value\n"
        "- bubble: same as scatter plus **required** `sizeMetricColumn` — point size scales with that metric\n"
        "- timeline: `startColumn`* (date), `endColumn`* (date), `barLabelColumn` (optional per-bar label), `tooltipColumn` (optional)\n"
        "- `connectionId`* (int), `sql`* (string), `sources` (string[])\n"
    )

    _CONFIG_KEYS = ("title", "description", "options", "animation")
    _MAPPING_KEYS = ("labelColumn", "datasetColumns", "dateGranularity",
                     "breakdownColumn", "xMetricColumn",
                     "yMetricColumn", "xAggregation", "yAggregation", "sizeMetricColumn",
                     "startColumn", "endColumn", "barLabelColumn", "tooltipColumn")

    def _config(self, params: dict) -> dict:
        return {"type": params.get("chartType"), **_pick(params, self._CONFIG_KEYS)}

    def _mapping(self, params: dict) -> dict:
        # chartType is required by transform_widget_data (scatter {x,y} depends on it).
        return {
            "type": "chart",
            "chartType": params.get("chartType"),
            **_pick(params, self._MAPPING_KEYS),
        }
