"""Guard against drift between the inline dashboard prompt and the
DB-seeded AgentProfile defaults — both must compose from
backend.agents.dashboard_prompt_blocks."""

from backend.agents.dashboard_prompt_blocks import (
    DASHBOARD_CHART_GUIDE,
    DASHBOARD_CROSS_CONNECTION,
    DASHBOARD_EDA_FRAMEWORK,
    DASHBOARD_FAILURE_RECOVERY,
    DASHBOARD_IDENTITY,
    DASHBOARD_SOUL,
    DASHBOARD_SQL_CHECKLIST,
    DASHBOARD_STORYBOARD,
    DASHBOARD_UPDATE_RULES,
    DASHBOARD_WIDGET_CONTRACT,
    DASHBOARD_WORKFLOW,
)
from backend.agents.dashboard_agent.prompts import (
    DASHBOARD_AGENT_MESH_PROMPT,
    DASHBOARD_AGENT_SYSTEM_PROMPT,
)
from backend.agents.profile_defaults import DEFAULTS

_STALE_MARKERS = [
    # Old widget-type list without section/pivot_table.
    "Available types: kpi, chart, table, filter, text",
    # Old full-envelope contract (superseded by lean widgets).
    "Every widget MUST have: `id`, `position`",
    # Old hardcoded layout coordinates.
    "y=2:",
    "(y=4 to y=14)",
    "Section 2 — Filters (y=2)",
]


class TestInlinePrompt:
    def test_composed_from_blocks(self):
        for block in (
            DASHBOARD_IDENTITY,
            DASHBOARD_WORKFLOW,
            DASHBOARD_EDA_FRAMEWORK,
            DASHBOARD_STORYBOARD,
            DASHBOARD_CHART_GUIDE,
            DASHBOARD_WIDGET_CONTRACT,
            DASHBOARD_CROSS_CONNECTION,
            DASHBOARD_FAILURE_RECOVERY,
            DASHBOARD_SQL_CHECKLIST,
            DASHBOARD_UPDATE_RULES,
        ):
            assert block in DASHBOARD_AGENT_SYSTEM_PROMPT

    def test_no_stale_markers(self):
        for marker in _STALE_MARKERS:
            assert marker not in DASHBOARD_AGENT_SYSTEM_PROMPT

    def test_min_four_sections_rule_present(self):
        assert "MINIMUM 4 sections" in DASHBOARD_AGENT_SYSTEM_PROMPT

    def test_section_widget_is_the_header(self):
        assert "NEVER use a text widget as a header" in DASHBOARD_AGENT_SYSTEM_PROMPT


class TestMeshPrompt:
    def test_design_principles_exactly_once(self):
        # Regression: the old mesh prompt split on a removed marker and
        # duplicated the design principles.
        assert DASHBOARD_AGENT_MESH_PROMPT.count("## Dashboard Design Principles") == 1

    def test_composed_from_blocks(self):
        assert DASHBOARD_STORYBOARD in DASHBOARD_AGENT_MESH_PROMPT
        assert DASHBOARD_SQL_CHECKLIST in DASHBOARD_AGENT_MESH_PROMPT


class TestProfileDefaults:
    def test_sections_composed_from_blocks(self):
        d = DEFAULTS["dashboard_agent"]
        assert d["identity"] == DASHBOARD_IDENTITY
        assert d["soul"] == DASHBOARD_SOUL
        for block in (
            DASHBOARD_WORKFLOW,
            DASHBOARD_EDA_FRAMEWORK,
            DASHBOARD_STORYBOARD,
            DASHBOARD_CHART_GUIDE,
            DASHBOARD_WIDGET_CONTRACT,
            DASHBOARD_CROSS_CONNECTION,
        ):
            assert block in d["tools"]
        for block in (
            DASHBOARD_FAILURE_RECOVERY,
            DASHBOARD_SQL_CHECKLIST,
            DASHBOARD_UPDATE_RULES,
        ):
            assert block in d["guardrails"]

    def test_no_stale_markers(self):
        d = DEFAULTS["dashboard_agent"]
        combined = "\n".join(v for v in d.values() if v)
        for marker in _STALE_MARKERS:
            assert marker not in combined
