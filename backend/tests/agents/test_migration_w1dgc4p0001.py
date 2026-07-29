"""Guards for the dashboard_agent widget-cap `tools` refresh.

The prompt said "max 17" while `dashboard_widget_verifier.MAX_TOTAL_WIDGETS` rejected
anything over 15 — a compliant agent still got bounced, twice, for ~119s of a 200s
build. Fixing the source constant only reaches the inline path and freshly-seeded
profiles; rows an earlier revision seeded keep the old text forever without this
migration.
"""
import ast
import hashlib
import importlib.util
import pathlib

_VERSIONS = pathlib.Path(__file__).resolve().parents[3] / "alembic" / "versions"
_MIGRATION = _VERSIONS / "w1dgc4p0001_refresh_dashboard_profile_widget_cap.py"
_PREVIOUS = _VERSIONS / "d0cst0ry0a1b_refresh_agent_tools_docs_story_no_avg.py"


def _literal(name: str, path=None):
    tree = ast.parse((path or _MIGRATION).read_text())
    return next(
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == name for t in n.targets)
    )


def _load_module():
    """Load by file path — alembic/versions is not a package."""
    spec = importlib.util.spec_from_file_location("_mig_w1dgc4p0001", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_chains_onto_the_current_head():
    mod = _load_module()
    assert mod.revision == "w1dgc4p0001"
    assert mod.down_revision == "0rch5c0pe01"


def test_no_live_defaults_import_at_upgrade():
    """The snapshot must be a literal, or this revision's result changes every time
    someone edits a prompt block."""
    src = _MIGRATION.read_text()
    assert "from backend.agents.profile_defaults import DEFAULTS" not in src
    assert "_NEW_TOOLS" in src


def test_snapshot_matches_current_defaults():
    from backend.agents.profile_defaults import DEFAULTS

    assert _literal("_NEW_TOOLS") == DEFAULTS["dashboard_agent"]["tools"]


def test_snapshot_carries_the_enforced_cap():
    from backend.agents.orchestrator.dashboard_widget_verifier import MAX_TOTAL_WIDGETS

    new_tools = _literal("_NEW_TOOLS")
    assert f"{MAX_TOTAL_WIDGETS} widgets is a HARD cap" in new_tools
    assert "max 17" not in new_tools


def test_old_hashes_include_the_text_the_previous_revision_wrote():
    """Installs sitting at d0cst0ry0a1b hold the text it wrote. If its digest is not
    in the match set they are skipped forever and never see the new cap."""
    # Every digest the previous revision matched on, plus the digest of the text
    # it actually wrote (which is what those installs are holding right now).
    inherited = _literal("_OLD_TOOLS_HASHES", _PREVIOUS)["dashboard_agent"]
    assert inherited <= _literal("_OLD_TOOLS_HASHES")
    assert len(_literal("_OLD_TOOLS_HASHES")) == len(inherited) + 1

    # …and the current default must NOT be treated as old, or every fresh install
    # rewrites a row with the text it already has.
    mod = _load_module()
    assert mod._is_old_default(_literal("_NEW_TOOLS")) is False


def test_matcher_spares_user_edited_text():
    mod = _load_module()
    assert mod._is_old_default("text a user wrote themselves") is False
    assert mod._is_old_default(None) is False
    assert mod._is_old_default("") is False


def test_matcher_keys_on_the_digest_set(monkeypatch):
    mod = _load_module()
    text = "SOME OLD TOOLS TEXT"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    monkeypatch.setattr(mod, "_OLD_TOOLS_HASHES", {digest})
    assert mod._is_old_default(text) is True
    assert mod._is_old_default("something else") is False
