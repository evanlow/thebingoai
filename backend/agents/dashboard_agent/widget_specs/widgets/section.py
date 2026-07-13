"""SectionWidget — section header bar that groups the widgets below it.

Agent emits: title* (plain text), sectionColor?
Hydrates:    config{title, sectionColor?}
"""
from .base import BaseWidget, _pick

_SECTION_COLORS = {"default", "violet", "blue", "green", "amber", "rose"}


class SectionWidget(BaseWidget):
    type = "section"
    has_data_source = False
    default_position = {"w": 12, "h": 1, "minW": 2, "minH": 1}
    params_doc = (
        "## Section params\n"
        "- `title`* (string): plain-text section name (no markdown)\n"
        "- `sectionColor` (default|violet|blue|green|amber|rose)\n"
    )

    def _config(self, params: dict) -> dict:
        config = _pick(params, ("title", "sectionColor"))
        # Config values feed frontend style bindings — clamp to known tokens.
        if config.get("sectionColor") not in _SECTION_COLORS:
            config.pop("sectionColor", None)
        return config
