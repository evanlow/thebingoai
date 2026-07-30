"""Guards for the agent-profile `tools` refresh (documentation-driven storytelling, no averages).

Prompt edits to `dashboard_prompt_blocks` / `profile_defaults` only reach the inline
path and freshly-seeded profiles. Rows seeded by an earlier revision keep their old
text, so without this migration the dashboard agent never sees the documentation rules
and — worse — the data agent keeps being told to report an average that
`llm_privacy._VALUE_KEYS` now strips, which invites a fabricated number.
"""
import ast
import hashlib
import importlib.util
import pathlib

_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[3]
    / "alembic" / "versions"
    / "d0cst0ry0a1b_refresh_agent_tools_docs_story_no_avg.py"
)


def _literal(name: str):
    tree = ast.parse(_MIGRATION.read_text())
    return next(
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == name for t in n.targets)
    )


def _load_module():
    """Load by file path — alembic/versions is not a package."""
    spec = importlib.util.spec_from_file_location("_mig_d0cst0ry0a1b", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_no_live_defaults_import_at_upgrade():
    """The snapshot must be a literal, or this historical revision's result changes
    every time someone edits a prompt block."""
    src = _MIGRATION.read_text()
    assert "from backend.agents.profile_defaults import DEFAULTS" not in src
    assert "_NEW_TOOLS" in src


def test_snapshot_covers_both_agents():
    """data_agent is still live-equal — nothing has refreshed it since. The
    dashboard_agent text is frozen instead: `w1dgc4p0001` refreshes it again
    downstream, so this revision's job is to write the text that revision knows
    how to recognise, not whatever the prompt blocks say today.

    Exactly one revision per agent may assert live-equality — the newest one.
    Holding it here too is what dragged every later prompt edit back into this
    file and its predecessors."""
    from backend.agents.profile_defaults import DEFAULTS

    new_tools = _literal("_NEW_TOOLS")
    assert set(new_tools) == {"dashboard_agent", "data_agent"}
    assert new_tools["data_agent"] == DEFAULTS["data_agent"]["tools"]
    assert hashlib.sha256(new_tools["dashboard_agent"].encode()).hexdigest() == (
        "f35055b4ee341b28005774adb7eb27d8204fdd6538a55cb51297678d662e815e"
    )


def test_dashboard_snapshot_is_recognised_downstream():
    """A fresh install runs this revision and then `w1dgc4p0001`. If that one
    cannot match what this one wrote, the refresh silently stops here and the
    install ends up on older text than an upgraded one."""
    downstream = (
        _MIGRATION.parent / "w1dgc4p0001_refresh_dashboard_profile_widget_cap.py"
    )
    old_hashes = next(
        ast.literal_eval(n.value)
        for n in ast.parse(downstream.read_text()).body
        if isinstance(n, ast.Assign)
        and any(getattr(t, "id", None) == "_OLD_TOOLS_HASHES" for t in n.targets)
    )
    written = _literal("_NEW_TOOLS")["dashboard_agent"]
    assert hashlib.sha256(written.encode()).hexdigest() in old_hashes


def test_snapshot_carries_the_new_rules():
    new_tools = _literal("_NEW_TOOLS")
    assert "Documented meaning first" in new_tools["dashboard_agent"]
    assert "Findings already established with the user" in new_tools["dashboard_agent"]
    # The whole reason data_agent is in this migration.
    assert "avg $50K" not in new_tools["data_agent"]


def test_old_hashes_include_the_text_the_previous_revision_wrote():
    """d4shpr0f1le1 already refreshed dashboard_agent rows. Installs that ran it hold
    that text, so its digest must be in the match set or they are skipped forever."""
    old = _literal("_OLD_TOOLS_HASHES")
    assert "ef73c9e062fbf0354e301f94d05f96b268c8df82166251d30572db1d4e310809" in old["dashboard_agent"]
    assert "1709ad4eb7732d4e37cb4b406784b370e1542a4907cbb272754b5313ab35b0fc" in old["data_agent"]


def test_matcher_spares_user_edited_text():
    mod = _load_module()
    assert mod._is_old_default("dashboard_agent", "text a user wrote themselves") is False
    assert mod._is_old_default("dashboard_agent", None) is False
    assert mod._is_old_default("dashboard_agent", "") is False


def test_matcher_is_scoped_per_agent_type(monkeypatch):
    """A data_agent digest must not refresh a dashboard_agent row."""
    mod = _load_module()
    text = "SOME OLD TOOLS TEXT"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    monkeypatch.setitem(mod._OLD_TOOLS_HASHES, "data_agent", {digest})
    monkeypatch.setitem(mod._OLD_TOOLS_HASHES, "dashboard_agent", set())

    assert mod._is_old_default("data_agent", text) is True
    assert mod._is_old_default("dashboard_agent", text) is False
