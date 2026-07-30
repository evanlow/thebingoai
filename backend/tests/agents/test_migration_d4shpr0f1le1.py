"""Determinism + matcher guards for the dashboard_agent default-refresh migration.

The migration must replay to a fixed result regardless of later edits to
`backend.agents.profile_defaults`, so it embeds a frozen `_NEW_DEFAULTS`
snapshot instead of importing the live DEFAULTS at upgrade time.
"""
import ast
import hashlib
import importlib.util
import pathlib

_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[3]
    / "alembic" / "versions"
    / "d4shpr0f1le1_refresh_dashboard_agent_profile_defaults.py"
)


def _load_source() -> str:
    return _MIGRATION.read_text()


def _load_module():
    """Load the migration by file path — alembic/versions is not a package."""
    spec = importlib.util.spec_from_file_location("_mig_d4shpr0f1le1", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_no_live_defaults_import_at_upgrade():
    """upgrade() must not import DEFAULTS from the app — that would make the
    historical migration's result mutable."""
    src = _load_source()
    assert "from backend.agents.profile_defaults import DEFAULTS" not in src
    assert "_NEW_DEFAULTS" in src


def test_frozen_snapshot_has_all_sections():
    """The frozen snapshot must carry the four refreshed sections as literals."""
    tree = ast.parse(_load_source())
    new_defaults = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", None) == "_NEW_DEFAULTS" for t in node.targets
        ):
            new_defaults = ast.literal_eval(node.value)
    assert new_defaults is not None
    assert set(new_defaults) == {"identity", "soul", "tools", "guardrails"}
    assert all(isinstance(v, str) and v for v in new_defaults.values())


def test_frozen_snapshot_stays_frozen():
    """This revision has shipped. Its snapshot must keep writing the text it
    wrote then, or a fresh install and an upgraded one diverge.

    There used to be a test here asserting the snapshot equals the live
    composed DEFAULTS. That is the invariant of the *newest* refresh
    migration, not a historical one — holding it here forced every later
    prompt edit back into this file, which is exactly what a frozen snapshot
    exists to prevent. `test_migration_d0cst0ry0a1b` owns it now, and pins
    the digest below as the text it must recognise and replace."""
    tree = ast.parse(_load_source())
    new_defaults = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", None) == "_NEW_DEFAULTS" for t in node.targets)
    )
    digest = hashlib.sha256(new_defaults["tools"].encode()).hexdigest()
    assert digest == (
        "ef73c9e062fbf0354e301f94d05f96b268c8df82166251d30572db1d4e310809"
    )


def test_matcher_replaces_old_default_and_spares_edits():
    """_is_old_default hashes stored text against historical digests: an old
    default matches (→ refreshed), user-edited text does not (→ untouched)."""
    mod = _load_module()
    # Take one known historical soul digest and confirm the matcher keys on it.
    known = next(iter(mod._OLD_DEFAULT_HASHES["soul"]))
    # A string hashing to a stored digest can't be reconstructed, so verify the
    # matcher's contract directly: membership in the digest set drives the call.
    assert mod._is_old_default("soul", "not a historical default") is False
    assert known in mod._OLD_DEFAULT_HASHES["soul"]
    # And a freshly-seeded historical value (empty/None) is never a match.
    assert mod._is_old_default("soul", None) is False
    assert mod._is_old_default("soul", "") is False


def test_matcher_true_on_synthetic_hash(monkeypatch):
    """Feed a text whose digest we inject into the historical set → matches."""
    mod = _load_module()
    text = "SOME OLD DEFAULT TOOLS TEXT"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    monkeypatch.setitem(mod._OLD_DEFAULT_HASHES, "tools", {digest})
    assert mod._is_old_default("tools", text) is True
    assert mod._is_old_default("tools", "different text") is False
