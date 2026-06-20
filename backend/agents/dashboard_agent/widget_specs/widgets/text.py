"""TextWidget — section header / markdown text (no dataSource).

Agent emits: content* (markdown), alignment?
Hydrates:    config{content, alignment}
"""
from .base import BaseWidget, _pick


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
