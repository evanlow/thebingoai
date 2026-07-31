"""Tests for POST /api/chat/conversations/{thread_id}/dataset-ack.

Files sent with no question are answered in the browser — the processing *was* the
request, so no agent turn runs and the WS path would reject the empty message
anyway. Nothing then wrote to `messages`, so the thread read empty after a reload.
This endpoint records the same two rows a normal turn would.

Self-contained: mounts only the chat_files router on a throwaway FastAPI app with
dependency overrides, so it never touches a real DB / Redis / Celery.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

CONV = SimpleNamespace(id=7, thread_id="thread-1", user_id="u1")

ATTACHMENT = {
    "file_id": "connection:104",
    "name": "HR_dataset.csv",
    "type": "text/csv",
    "size": 0,
    "content_type": "text",
    "storage_key": None,
}


def _client(user=None):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.api.chat_files import router
    from backend.auth.dependencies import get_current_user
    from backend.database.session import get_db

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: (
        user or SimpleNamespace(id="u1", org_id=None, active_role="member")
    )
    return TestClient(app)


def _post(body, *, conversation=CONV, attachments=(ATTACHMENT,), user=None):
    """POST the ack with the conversation lookup and attachment resolution stubbed.

    Returns (response, add_message_mock).
    """
    async def fake_resolve(file_ids, _svc, db=None, user=None):
        return [], list(attachments)

    with patch(
        "backend.services.conversation_service.ConversationService.get_conversation_by_thread",
        return_value=conversation,
    ), patch(
        "backend.services.conversation_service.ConversationService.add_message"
    ) as add_message, patch(
        "backend.api.websocket._resolve_attachments", side_effect=fake_resolve
    ):
        resp = _client(user).post("/api/chat/conversations/thread-1/dataset-ack", json=body)
    return resp, add_message


# --- the happy path ---------------------------------------------------------


def test_persists_both_rows_of_the_turn():
    resp, add_message = _post({"file_ids": ["connection:104"], "content": "I've read it"})

    assert resp.status_code == 201
    roles = [call.args[2] for call in add_message.call_args_list]
    assert roles == ["user", "assistant"]


def test_the_user_row_is_empty_and_carries_the_attachment():
    """It must round-trip as the same shape a normal turn writes, so the dataset
    card renders from history exactly as it did live."""
    _, add_message = _post({"file_ids": ["connection:104"], "content": "I've read it"})

    user_call = add_message.call_args_list[0]
    assert user_call.args[3] == ""                                 # no question was asked
    assert user_call.kwargs["attachments"] == [ATTACHMENT]


def test_the_assistant_row_carries_the_acknowledgement():
    _, add_message = _post({"file_ids": ["connection:104"], "content": "I've read it"})
    assert add_message.call_args_list[1].args[3] == "I've read it"


def test_no_attachments_resolved_writes_null_not_an_empty_list():
    _, add_message = _post(
        {"file_ids": [], "content": "I've read it"}, attachments=(),
    )
    assert add_message.call_args_list[0].kwargs["attachments"] is None


# --- authorization + input ---------------------------------------------------


def test_unknown_or_foreign_thread_is_a_404():
    """get_conversation_by_thread filters on user_id, so someone else's thread is
    indistinguishable from a missing one — and must stay that way."""
    resp, add_message = _post(
        {"file_ids": [], "content": "hi"}, conversation=None,
    )
    assert resp.status_code == 404
    assert add_message.call_count == 0


def test_a_non_connection_file_id_is_rejected():
    """This endpoint writes a turn nothing validated, so it must not double as a way
    to staple arbitrary Redis-backed chat files onto a message."""
    resp, add_message = _post(
        {"file_ids": ["abc-123-uuid"], "content": "hi"},
    )
    assert resp.status_code == 400
    assert add_message.call_count == 0


def test_a_malformed_connection_file_id_is_rejected():
    resp, _ = _post({"file_ids": ["connection:"], "content": "hi"})
    assert resp.status_code == 400

    resp, _ = _post({"file_ids": ["connection:abc"], "content": "hi"})
    assert resp.status_code == 400


def test_an_overlong_acknowledgement_is_rejected():
    resp, add_message = _post({"file_ids": [], "content": "x" * 4001})
    assert resp.status_code == 422
    assert add_message.call_count == 0


def test_a_viewer_cannot_write():
    resp, add_message = _post(
        {"file_ids": [], "content": "hi"},
        user=SimpleNamespace(id="u1", org_id=None, active_role="viewer"),
    )
    assert resp.status_code == 403
    assert add_message.call_count == 0
