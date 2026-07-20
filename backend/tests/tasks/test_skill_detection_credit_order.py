"""_process_user credit ordering — parse/persist inside the credit context.

The sibling test_skill_detection_parse.py pins _parse_patterns in isolation;
this one pins the credit path hanging off it, which the parse test can't see:

  - unusable LLM output → void() then a clean __exit__ (turn recorded free)
  - usable output       → persist commits BEFORE __exit__, no void (turn billed)
  - persist failure     → __exit__ receives the exception (manager skips billing)
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

import backend.tasks.skill_detection_tasks as sd


class _FakeMgr:
    def __init__(self, order, **kwargs):
        self.order = order
        self.voids = []

    def void(self, reason="unresolved"):
        self.voids.append(reason)
        self.order.append(("void", reason))

    def __enter__(self):
        self.order.append("enter")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.order.append(("exit", exc_type))
        return False


def _db(order, *, commit_fails=False):
    """MagicMock session wired for _process_user's six up-front queries.

    Each db.query() returns a fresh mock, so the distinct chains (.count() vs
    .all(), with and without .join()) can't cross-talk.
    """
    db = MagicMock()

    def query_side_effect(*models):
        q = MagicMock()
        # message_count: query(Message).join(...).filter(...).count() — needs >= 10
        q.join.return_value.filter.return_value.count.return_value = 10
        # pending_count: query(SkillSuggestion).filter(...).count() — needs < 3
        q.filter.return_value.count.return_value = 0
        # rows: query(...).join().filter().order_by().limit().all()
        q.join.return_value.filter.return_value.order_by.return_value \
            .limit.return_value.all.return_value = [("show me revenue", "thread-abc-123")]
        # existing skills / pending names / dismissed suggestions
        q.filter.return_value.all.return_value = []
        return q

    db.query.side_effect = query_side_effect

    def _commit():
        order.append("commit")
        if commit_fails:
            raise RuntimeError("persist failed")

    db.commit.side_effect = _commit
    return db


def _run(order, llm_response, *, commit_fails=False):
    """Drive _process_user with a stubbed LLM reply. Returns (mgr, db)."""
    db = _db(order, commit_fails=commit_fails)
    user = MagicMock(id="u-1")

    provider = MagicMock()

    async def _chat(messages, **kw):
        order.append("llm")
        return llm_response

    provider.chat = _chat

    mgr_box = {}

    def _mk_mgr(**kw):
        mgr_box["mgr"] = _FakeMgr(order, **kw)
        return mgr_box["mgr"]

    import backend.services.token_tracking_service as tts
    import backend.plugins.loader as loader

    with patch.object(sd, "get_provider", return_value=provider), \
         patch.object(loader, "get_loaded_plugins", lambda: {}), \
         patch.object(tts, "CreditContextManager", _mk_mgr), \
         patch.object(sd, "_evaluate_suggestions"), \
         patch.object(sd, "_notify_new_suggestions"):
        sd._process_user(db, user, datetime(2026, 1, 1))

    return mgr_box.get("mgr"), db


_GOOD = '[{"suggested_name": "weekly-report", "confidence": 0.9}]'


def test_usable_output_persists_before_exit_and_is_billed():
    order = []
    mgr, _ = _run(order, _GOOD)
    # The suggestion commit must land inside the context, before the charge.
    assert order == ["enter", "llm", "commit", ("exit", None)]
    assert mgr.voids == []


def test_unparseable_output_voids_the_turn():
    order = []
    mgr, _ = _run(order, "sorry, I cannot help with that")
    assert mgr.voids == ["unparseable skill-pattern response"]
    # Voided, but still a clean exit — the manager skips recording, not crashes.
    assert order == [
        "enter", "llm", ("void", "unparseable skill-pattern response"), ("exit", None),
    ]


def test_non_dict_array_voids_rather_than_crashing():
    # Valid JSON, valid list, unusable content: the elements aren't dicts, so
    # the persist loop's `.get` would AttributeError. Must void instead.
    order = []
    mgr, _ = _run(order, '["summarize", "chart"]')
    assert mgr.voids == ["unparseable skill-pattern response"]
    assert ("exit", None) in order


def test_persist_failure_reaches_exit_unbilled():
    order = []
    mgr, _ = _run(order, _GOOD, commit_fails=True)
    # The exception flows through __exit__ (manager skips billing) and the task
    # swallows it — a bookkeeping task must not crash the worker.
    assert ("exit", RuntimeError) in order
    assert ("exit", None) not in order
    assert mgr.voids == []  # not voided — voiding is for *unusable output*


def test_malformed_confidence_skips_only_that_pattern():
    # One bad entry must not sink the batch: the good suggestion still persists.
    order = []
    mgr, db = _run(
        order,
        '[{"suggested_name": "bad", "confidence": "high"},'
        ' {"suggested_name": "good", "confidence": 0.9}]',
    )
    assert mgr.voids == []
    added = [c.args[0] for c in db.add.call_args_list]
    assert [s.suggested_name for s in added] == ["good"]


@pytest.mark.parametrize("response", ["[]", "```json\n[]\n```"])
def test_empty_pattern_list_is_billed_not_voided(response):
    # "No patterns found" is a real answer the LLM was paid to produce.
    order = []
    mgr, db = _run(order, response)
    assert mgr.voids == []
    assert order == ["enter", "llm", ("exit", None)]
    db.commit.assert_not_called()  # nothing to persist
