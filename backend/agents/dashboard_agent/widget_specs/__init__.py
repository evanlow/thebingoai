"""Widget spec registry and renderer.

Combines each widget's lean param documentation (from the BaseWidget subclasses
in widgets.py) with hand-written guidance to produce the spec the dashboard
agent reads before designing. The agent emits lean params; the backend hydrates
them into full widget JSON (see widgets.build_widgets).
"""

from typing import Optional

from backend.agents.dashboard_agent.widget_specs.widgets import WIDGET_REGISTRY

# Cache rendered specs at module load time
_spec_cache: dict[str, str] = {}


def _build_spec(widget_type: str) -> str:
    """Combine a widget's lean param doc with its hand-written guidance."""
    from backend.agents.dashboard_agent.widget_specs.guidance import GUIDANCE

    params_doc = WIDGET_REGISTRY[widget_type].params_doc
    guidance = GUIDANCE.get(widget_type, "")
    return f"{params_doc}\n{guidance}"


def _warm_cache() -> None:
    """Pre-render all widget specs into the cache."""
    for wt in WIDGET_REGISTRY:
        try:
            _spec_cache[wt] = _build_spec(wt)
        except Exception:
            pass  # Logged at call time if needed


def get_widget_spec(widget_type: str) -> Optional[str]:
    """
    Get the complete rendered specification for a widget type.

    Returns the lean param doc + hand-written guidance, or None if the widget
    type is unknown.
    """
    if not _spec_cache:
        _warm_cache()

    return _spec_cache.get(widget_type)


def get_available_types() -> list[str]:
    """Return the list of supported widget types."""
    return list(WIDGET_REGISTRY)
