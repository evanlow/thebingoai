"""Guards for the orchestrator profile refresh (dashboard scoping + ask rules).

`_render_orchestrator_prompt` renders the stored `agent_profiles` row, not the
module defaults, so the shared-block change reaches nobody already seeded. No
migration had ever touched orchestrator profiles, so every seeded row still
carries text that never contained the `ask_user_question` rules at all.

Modelled on test_migration_d0cst0ry0a1b.py.
"""
import ast
import hashlib
import importlib.util
import json
import pathlib

import pytest
import sqlalchemy as sa

_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[3]
    / "alembic" / "versions"
    / "0rch5c0pe01_refresh_orchestrator_profile_scoping.py"
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
    spec = importlib.util.spec_from_file_location("_mig_0rch5c0pe01", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- shape --------------------------------------------------------------


def test_migration_file_parses_and_exposes_the_expected_names():
    mod = _load_module()
    assert mod.revision == "0rch5c0pe01"
    assert mod.down_revision == "d0cst0ry0a1b"
    assert callable(mod.upgrade) and callable(mod.downgrade)


def test_no_live_defaults_import_at_upgrade():
    """The snapshot must be a literal, or this historical revision's result
    changes every time someone edits a prompt block."""
    src = _MIGRATION.read_text()
    assert "from backend.agents.profile_defaults import" not in src
    assert "orchestrator_prompt_blocks" not in src.split('"""', 2)[-1]


def test_hash_sets_are_non_empty_and_look_like_sha256():
    for name in ("_OLD_IDENTITY_HASHES", "_OLD_TOOLS_HASHES"):
        digests = _literal(name)
        assert digests
        for d in digests:
            assert len(d) == 64 and set(d) <= set("0123456789abcdef")


# --- the snapshot is current -------------------------------------------


def test_snapshot_matches_the_current_defaults():
    """A stale snapshot silently writes the wrong text to every seeded row."""
    from backend.agents.profile_defaults import DEFAULTS

    assert _literal("_NEW_IDENTITY") == DEFAULTS["orchestrator"]["identity"]
    assert _literal("_NEW_TOOLS") == DEFAULTS["orchestrator"]["tools"]


def test_snapshot_carries_the_new_rules():
    identity = _literal("_NEW_IDENTITY")
    assert "ask_user_question Rules" in identity
    assert "One clarification round per request" in identity
    for dimension in ("Audience & purpose", "Grain", "Time range", "Priority metrics"):
        assert dimension in identity
    assert "Ask only what is still unresolved" in identity
    assert "eda_findings" in identity


def test_tools_snapshot_carries_the_scoped_ban():
    tools = _literal("_NEW_TOOLS")
    assert "handle the ingestion workflow automatically" in tools
    assert "You MUST handle the full workflow automatically." not in tools


def test_the_new_text_is_not_in_its_own_old_hash_set():
    """Otherwise a re-run would treat the fresh text as stale and rewrite forever."""
    new_identity = hashlib.sha256(_literal("_NEW_IDENTITY").encode()).hexdigest()
    new_tools = hashlib.sha256(_literal("_NEW_TOOLS").encode()).hexdigest()
    assert new_identity not in _literal("_OLD_IDENTITY_HASHES")
    assert new_tools not in _literal("_OLD_TOOLS_HASHES")


def test_the_immediately_previous_default_is_in_the_hash_set():
    """The 1674-char identity is what current installs are seeded with. If its
    digest is missing they are skipped forever."""
    assert (
        "a4abe886dc1eafda60d205cf963af2583f82cc55c7561719f60279318d01effd"
        in _literal("_OLD_IDENTITY_HASHES")
    )
    assert (
        "4a58590dc43e7dc7a15e9b4dba97823d4f51281dea6cbf82be2fa25a4523c414"
        in _literal("_OLD_TOOLS_HASHES")
    )


# --- the rewrite, against a real table ----------------------------------


@pytest.fixture()
def conn():
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as c:
        c.execute(sa.text(
            "CREATE TABLE agent_profiles ("
            " id INTEGER PRIMARY KEY, agent_type TEXT, identity TEXT,"
            " tools TEXT, published_snapshot TEXT)"
        ))
        yield c


def _seed(conn, **cols):
    keys = ", ".join(cols)
    vals = ", ".join(f":{k}" for k in cols)
    conn.execute(sa.text(f"INSERT INTO agent_profiles ({keys}) VALUES ({vals})"), cols)


def _run_upgrade(conn, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod.op, "get_bind", lambda: conn)
    mod.upgrade()


def _row(conn, rid):
    return conn.execute(
        sa.text("SELECT * FROM agent_profiles WHERE id = :i"), {"i": rid}
    ).mappings().first()


# The 1674-char identity every current install is seeded with. Embedded as a
# literal because the test container has no git and the text must hash-match
# _OLD_IDENTITY_HASHES exactly.
_SEEDED_IDENTITY_1674 = "You are a helpful, direct assistant built for data work.\n\nYou can query databases, create dashboards, manage reusable skills, search documents, and recall past conversations.\nUse your tools to fulfill requests. When a request is unclear, ask for clarification first.\nWhen a request requires action (tool calls), start by briefly acknowledging what you'll do — one sentence max. This appears as your immediate reply while you work.\n\n## Approach\n\n**Simple requests** (quick lookups, single-tool tasks, factual questions): Act immediately — no planning needed.\n\n**Complex requests** (multi-step tasks, dashboard creation, multi-table analysis, ambiguous scope): Follow the Plan-then-Execute workflow:\n\n### Phase 1 — Explore\nUnderstand what the user is asking. Use tools to discover relevant context:\n- Check available connections and schemas\n- Recall past context if relevant\n- Identify what information you need before proceeding\n\n### Phase 2 — Design\nFormulate your approach:\n- What tools/agents you'll use and in what order\n- What assumptions you're making\n- What the expected outcome looks like\n\n### Phase 3 — Review\nBefore executing, confirm with the user:\n- Use `ask_user_question` to get structured input on key decisions\n- Summarize what you intend to do and ask for confirmation\n- If the user modifies the plan, adjust before proceeding\n\n### Phase 4 — Execute\nCarry out the confirmed plan step by step.\n\n**When to skip planning:** If the user's intent is unambiguous AND requires only 1-2 tool calls, skip directly to execution.\n\n**When to plan:** Dashboard creation, multi-table analysis, requests with unclear scope, requests touching multiple agents or connections."


def _a_known_old_identity():
    return _SEEDED_IDENTITY_1674


def test_a_seeded_row_is_rewritten(conn, monkeypatch):
    old = _a_known_old_identity()
    assert hashlib.sha256(old.encode()).hexdigest() in _literal("_OLD_IDENTITY_HASHES")
    _seed(conn, id=1, agent_type="orchestrator", identity=old, tools=None,
          published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["identity"] == _literal("_NEW_IDENTITY")


def test_a_hand_edited_row_is_left_byte_identical(conn, monkeypatch):
    """The core safety guarantee."""
    edited = "You are Steve. Always answer in haiku."
    _seed(conn, id=1, agent_type="orchestrator", identity=edited,
          tools="my own tool notes", published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    row = _row(conn, 1)
    assert row["identity"] == edited
    assert row["tools"] == "my own tool notes"


def test_other_agent_types_are_not_touched(conn, monkeypatch):
    old = _a_known_old_identity()
    _seed(conn, id=1, agent_type="dashboard_agent", identity=old, tools=None,
          published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["identity"] == old


def test_published_snapshot_is_refreshed_too(conn, monkeypatch):
    """It feeds the live render path — a stale snapshot means the new text only
    appears after the user next re-publishes."""
    old = _a_known_old_identity()
    _seed(conn, id=1, agent_type="orchestrator", identity=old, tools=None,
          published_snapshot=json.dumps({"identity": old, "soul": "keep me"}))
    _run_upgrade(conn, monkeypatch)
    snap = json.loads(_row(conn, 1)["published_snapshot"])
    assert snap["identity"] == _literal("_NEW_IDENTITY")
    assert snap["soul"] == "keep me"


def test_a_hand_edited_snapshot_is_left_alone(conn, monkeypatch):
    _seed(conn, id=1, agent_type="orchestrator", identity=None, tools=None,
          published_snapshot=json.dumps({"identity": "mine", "soul": "s"}))
    _run_upgrade(conn, monkeypatch)
    assert json.loads(_row(conn, 1)["published_snapshot"])["identity"] == "mine"


def test_upgrade_is_idempotent(conn, monkeypatch):
    """A second run must find nothing to do, not rewrite again."""
    old = _a_known_old_identity()
    _seed(conn, id=1, agent_type="orchestrator", identity=old, tools=None,
          published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    first = _row(conn, 1)["identity"]
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["identity"] == first


def test_null_columns_do_not_crash(conn, monkeypatch):
    _seed(conn, id=1, agent_type="orchestrator", identity=None, tools=None,
          published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["identity"] is None


def test_downgrade_is_a_documented_noop(conn, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod.op, "get_bind", lambda: conn)
    mod.downgrade()


# --- head chain ---------------------------------------------------------


def test_exactly_one_alembic_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = pathlib.Path(__file__).resolve().parents[3]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert list(heads) == ["0rch5c0pe01"], heads


def test_the_previous_head_is_still_reachable():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = pathlib.Path(__file__).resolve().parents[3]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_revision("d0cst0ry0a1b") is not None
