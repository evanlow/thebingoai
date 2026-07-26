"""The dataset docs table is a UI artifact, not model context.

Its content reaches the agents through the schema block instead (the semantic
layer is overlaid by load_enriched_context), so re-sending the whole markdown
table on every turn would be pure cost.
"""
from types import SimpleNamespace

from backend.agents.orchestrator.graph import _build_messages


def _msg(role: str, content: str, source: str = "chat") -> SimpleNamespace:
    return SimpleNamespace(role=role, content=content, source=source, attachments=None)


_DOCS_TABLE = "| Column | I read this as |"


def test_dataset_docs_message_is_withheld_from_the_model():
    messages = _build_messages(
        "what is total revenue?",
        [
            _msg("user", "here is my file"),
            _msg("assistant", _DOCS_TABLE, source="dataset_docs"),
            _msg("assistant", "ask away"),
        ],
        None,
    )
    contents = [m.content for m in messages]

    assert _DOCS_TABLE not in contents
    # Everything around it survives, in order, plus the current question.
    assert contents == ["here is my file", "ask away", "what is total revenue?"]


def test_ordinary_assistant_messages_still_pass_through():
    messages = _build_messages("next question", [_msg("assistant", "previous answer")], None)
    assert [m.content for m in messages] == ["previous answer", "next question"]
