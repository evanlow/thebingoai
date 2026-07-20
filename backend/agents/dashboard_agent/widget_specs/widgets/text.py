"""TextWidget — section header / markdown text (no dataSource).

Agent emits: content* (markdown), alignment?
Hydrates:    config{content, alignment, isSection, sectionColor?}
"""
from .base import BaseWidget, _pick


class TextWidget(BaseWidget):
    type = "text"
    has_data_source = False
    default_position = {"w": 12, "h": 1, "minW": 2, "minH": 1}
    params_doc = (
        "## Text params\n"
        "- `content`* (string): markdown prose; NOT for section headers — use a `section` widget\n"
        "- `alignment` (left|center|right)\n"
    )

    def _config(self, params: dict) -> dict:
        config = _pick(params, ("content", "alignment", "isSection", "sectionColor"))
        if "isSection" not in config:
            # Storyboard headers are markdown headings — flag them explicitly so
            # the frontend groups the section without relying on its heuristic.
            config["isSection"] = str(config.get("content", "")).lstrip().startswith("#")
        return config
