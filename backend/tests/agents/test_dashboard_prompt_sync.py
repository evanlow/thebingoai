"""Guard against drift between the inline dashboard prompt and the
DB-seeded AgentProfile defaults — both must compose from
backend.agents.dashboard_prompt_blocks."""

from backend.agents.dashboard_prompt_blocks import (
    DASHBOARD_CHART_GUIDE,
    DASHBOARD_CROSS_CONNECTION,
    DASHBOARD_EDA_FRAMEWORK,
    DASHBOARD_FAILURE_RECOVERY,
    DASHBOARD_IDENTITY,
    DASHBOARD_MESH_WORKFLOW,
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

    def test_cross_connection_rules_present(self):
        # The mesh prompt must keep the shared-data-plane join rules, or the
        # no-profile mesh path regresses to "cross-connection joins unsupported".
        assert DASHBOARD_CROSS_CONNECTION in DASHBOARD_AGENT_MESH_PROMPT

    def test_uses_mesh_workflow_not_inline(self):
        # Mesh binds neither list_tables nor get_table_schema — the peer-agent
        # workflow (sessions_send) replaces the inline direct-call workflow.
        assert DASHBOARD_MESH_WORKFLOW in DASHBOARD_AGENT_MESH_PROMPT
        assert DASHBOARD_WORKFLOW not in DASHBOARD_AGENT_MESH_PROMPT
        assert "sessions_send" in DASHBOARD_AGENT_MESH_PROMPT


class TestEdaFrameworkHonesty:
    def test_no_forbidden_profiling_claim(self):
        # The old wording forbade the profiling query it depended on.
        assert "do not run extra profiling queries" not in DASHBOARD_WORKFLOW
        assert "profiled statistics already in the context" not in DASHBOARD_WORKFLOW

    def test_profiling_step_restored(self):
        assert "profile_table" in DASHBOARD_WORKFLOW

    def test_privacy_withholding_acknowledged(self):
        # EDA framework must not assume raw endpoints/values are always present.
        assert "withheld" in DASHBOARD_EDA_FRAMEWORK


class TestLeanConnectionId:
    """Runtime-injected connection blocks must use the lean top-level
    connectionId, not the legacy nested dataSource.connectionId envelope."""

    def _conns(self):
        class _Conn:
            def __init__(self, id, name, db_type, database):
                self.id, self.name, self.db_type, self.database = id, name, db_type, database
        return [_Conn(1, "Sales DB", "postgres", "sales")]

    def test_fallback_prompt_uses_top_level_connection_id(self, monkeypatch):
        # Avoid DB / connection-context IO — only assert the static wording.
        import backend.agents.dashboard_agent.prompts as prompts
        monkeypatch.setattr(prompts, "build_dashboard_runtime_suffix", lambda **kw: "")
        prompt = prompts.build_dashboard_agent_prompt(
            available_connections=[1],
            connection_metadata=self._conns(),
        )
        assert "dataSource.connectionId" not in prompt
        assert "top-level connectionId" in prompt

    def test_profile_render_uses_top_level_connection_id(self):
        from backend.agents.profile_renderer import ProfileRenderer, RuntimeContext
        from backend.models.agent_profile import AgentProfile

        profile = AgentProfile(
            agent_type="dashboard_agent",
            identity=DASHBOARD_IDENTITY,
            is_active=True,
            version=1,
        )
        rendered = ProfileRenderer.render(
            profile,
            RuntimeContext(available_connections=[1], connection_metadata=self._conns()),
        )
        assert "dataSource.connectionId" not in rendered
        assert "top-level connectionId" in rendered


class TestMeshProfileParity:
    """A profile-backed dashboard agent in mesh mode must not instruct the
    unbound inline tools (list_tables/get_table_schema/profile_table)."""

    def test_seeded_tools_swap_to_mesh_workflow(self):
        tools = DEFAULTS["dashboard_agent"]["tools"]
        assert DASHBOARD_WORKFLOW in tools
        swapped = tools.replace(DASHBOARD_WORKFLOW, DASHBOARD_MESH_WORKFLOW)
        assert "sessions_send" in swapped
        assert DASHBOARD_WORKFLOW not in swapped
        # The inline direct-call phase-1 step is gone.
        assert "1. Call `list_tables(connection_id)`" not in swapped

    def test_resolve_applies_mesh_swap(self, monkeypatch):
        import backend.agents.dashboard_agent.graph as graph

        seeded = "PROLOGUE\n\n" + DASHBOARD_WORKFLOW + "\n\nEPILOGUE"
        monkeypatch.setattr(graph, "resolve_agent_prompt", lambda **kw: seeded)
        monkeypatch.setattr(graph, "_get_org_for_user", lambda uid: None)

        class _Ctx:
            user_id = "u"
            available_connections = [1]
            connection_metadata = []

        out = graph._resolve_dashboard_agent_prompt(
            _Ctx(), db_session_factory=None, mesh_enabled=True
        )
        assert "sessions_send" in out
        assert DASHBOARD_WORKFLOW not in out

    def test_resolve_inline_keeps_direct_workflow(self, monkeypatch):
        import backend.agents.dashboard_agent.graph as graph

        seeded = "PROLOGUE\n\n" + DASHBOARD_WORKFLOW + "\n\nEPILOGUE"
        monkeypatch.setattr(graph, "resolve_agent_prompt", lambda **kw: seeded)
        monkeypatch.setattr(graph, "_get_org_for_user", lambda uid: None)
        monkeypatch.setattr(graph.settings, "agent_mesh_enabled", False, raising=False)

        class _Ctx:
            user_id = "u"
            available_connections = [1]
            connection_metadata = []

        out = graph._resolve_dashboard_agent_prompt(_Ctx(), db_session_factory=None)
        assert DASHBOARD_WORKFLOW in out
        assert "sessions_send" not in out


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


class TestDocumentationDrivesTheStory:
    """The documented meaning replaces averages as the design signal.

    `avg` no longer reaches the agent (llm_privacy._VALUE_KEYS), so the framework has
    to name descriptions and business definitions as the inputs that pick the
    aggregation, the questions and the section titles. Both prompt paths compose from
    these blocks (asserted above), so guarding the block guards both.
    """

    def test_framework_no_longer_lists_averages_as_something_you_have(self):
        assert "and numeric **averages**" not in DASHBOARD_EDA_FRAMEWORK

    def test_framework_forbids_inventing_a_withheld_stat(self):
        assert "never invent one" in DASHBOARD_EDA_FRAMEWORK

    def test_descriptions_decide_unit_and_aggregation(self):
        assert "Read the column's description first" in DASHBOARD_EDA_FRAMEWORK
        assert "Never infer this from a statistic." in DASHBOARD_EDA_FRAMEWORK

    def test_documented_columns_are_where_the_questions_come_from(self):
        assert "Documented meaning first" in DASHBOARD_EDA_FRAMEWORK

    def test_established_findings_become_the_question_skeleton(self):
        assert "Findings already established with the user" in DASHBOARD_EDA_FRAMEWORK

    def test_section_titles_use_the_documentation_vocabulary(self):
        assert "Draw the wording from the documentation" in DASHBOARD_EDA_FRAMEWORK
