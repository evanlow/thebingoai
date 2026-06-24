"""BaseWidget ABC + shared helpers.

Subclasses in this package inherit `BaseWidget` and use `_pick` to lift flat
params into config / mapping dicts. The agent's lean per-widget params feed
`build()` (in the package's __init__); `build_widgets` hydrates them into
the full widget JSON the rest of the pipeline persists.
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
        # Optional emphasis: agent may set `width` (e.g. 8) on a widget it wants
        # larger. Used only as the packing SEED — normalize_dashboard_layout
        # still enforces sum-to-12 + overlap + per-type min/max. Omitted = type default.
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
