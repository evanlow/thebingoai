from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, conlist, field_validator


class Kpi(BaseModel):
    label: str
    value: str  # pre-formatted ("$13,816", "92.4%")
    delta_vs_prev: Optional[str] = None
    delta_direction: Optional[Literal["up", "down", "flat"]] = None


class Section(BaseModel):
    heading: str
    prose: str
    widget_id: Optional[Union[str, int]] = None  # dashboard widget id, e.g. "chart_rolling_30d"

    @field_validator("widget_id", mode="before")
    @classmethod
    def coerce_nullish(cls, v):
        # 0 and "" are treated as "no widget"
        if v == 0 or v == "":
            return None
        return v


class BriefingPayload(BaseModel):
    headline: str = Field(..., min_length=1, max_length=240)
    deck: str = Field(..., min_length=1, max_length=600)
    kpis: List[Kpi] = Field(default_factory=list, max_length=3)
    sections: conlist(Section, min_length=1)  # type: ignore[valid-type]
    key_takeaways: conlist(str, min_length=3, max_length=3)  # type: ignore[valid-type]
    # Concrete next steps derived from the key findings. Optional so briefings
    # generated before this shipped still validate.
    recommended_actions: Optional[conlist(str, min_length=2, max_length=4)] = None  # type: ignore[valid-type]
    # Rendered widget data configs keyed by widget_id, snapshot at generation
    # time so the briefing view renders instantly without re-running each
    # widget's SQL. Injected by emit_briefing, not the LLM. Absent on briefings
    # generated before this shipped → frontend falls back to a live refresh.
    widget_snapshots: Optional[Dict[str, Any]] = None


class BriefingResponse(BaseModel):
    id: int
    user_id: str
    dashboard_id: int
    dashboard_name: Optional[str] = None
    source: str
    status: str
    payload: Optional[BriefingPayload] = None
    error: Optional[str] = None
    date_range_from: Optional[datetime] = None
    date_range_to: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# Keys a public visitor may see on an embedded widget. Everything else —
# notably `dataSource` (SQL + connectionId) and `sources` — is dropped.
_PUBLIC_WIDGET_KEYS = ("id", "widget", "title")


def strip_widget(w: dict) -> dict:
    """Reduce a dashboard widget to the keys safe for anonymous eyes.

    Allowlist, not denylist: a new secret-bearing key added to widgets later
    must not start leaking because nobody remembered to exclude it here.
    """
    return {k: w[k] for k in _PUBLIC_WIDGET_KEYS if k in w}


class PublicBriefingResponse(BaseModel):
    """Anonymous view of a briefing. Deliberately NOT BriefingResponse, which
    carries user_id / dashboard_id / error / source — none of a stranger's
    business. widget_snapshots is required: a briefing lacking it cannot be
    shared (POST /share rejects it), which is what keeps this path SQL-free.
    """

    headline: str
    deck: str
    kpis: List[Kpi] = Field(default_factory=list)
    sections: List[Section]
    key_takeaways: List[str]
    recommended_actions: Optional[List[str]] = None
    widget_snapshots: Dict[str, Any]
    widgets: Dict[str, Any]          # widget_id -> strip_widget(widget)
    dashboard_name: Optional[str] = None
    created_at: datetime
