"""Widget hydration: lean per-widget params -> full widget JSON.

Each widget type lives in its own file (see base.py for the ABC and the
subclass files for the lean param contract). This package's `__init__`
imports the six classes, builds `WIDGET_REGISTRY`, defines `build_widgets()`,
and re-exports the public surface so existing imports of
`backend.agents.dashboard_agent.widget_specs.widgets` keep working.

Adding a new widget:
  1. create widgets/<new_type>.py (subclass BaseWidget; set type, params_doc,
     _config, _mapping, default_position)
  2. add the import + register it in WIDGET_REGISTRY below
  3. (optional) add widget_specs/guidance/<new_type>.py for rich guidance
"""
from .base import BaseWidget, _pick
from .chart import ChartWidget
from .filter import FilterWidget
from .kpi import KpiWidget
from .pivot_table import PivotTableWidget
from .section import SectionWidget
from .table import TableWidget
from .text import TextWidget

WIDGET_REGISTRY: dict[str, BaseWidget] = {
    w.type: w for w in (
        KpiWidget(), ChartWidget(), TableWidget(),
        PivotTableWidget(), FilterWidget(), TextWidget(), SectionWidget(),
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


__all__ = [
    "BaseWidget",
    "KpiWidget", "ChartWidget", "TableWidget", "PivotTableWidget",
    "FilterWidget", "TextWidget", "SectionWidget",
    "WIDGET_REGISTRY", "build_widgets",
    "_pick",
]
