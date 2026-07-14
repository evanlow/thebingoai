"""Session-lifecycle guards for the chat/websocket handoff to the orchestrator.

chat.py and websocket.py close the request session *before* the (minutes-long)
orchestrator run so the pooled connection isn't left idle-in-transaction and
reaped by the pooler. Every ORM row loaded beforehand is therefore detached for
the whole run, and the orchestrator still reads from it (graph.py `_build_messages`,
`_build_dynamic_tools`). These tests pin the two properties that make that safe.

The sessions here are built from the *production* DetachedReadSessionLocal kwargs —
the factory those two handlers use — so a revert of `expire_on_commit=False` in
backend/database/session.py fails these tests rather than silently passing on
conftest's own session config.

Prerequisites (the image ships neither):

    docker exec thebingo-backend pip install -r requirements-dev.txt
    docker exec thebingo-postgres psql -U thebingo_user -d thebingo \
        -c "CREATE DATABASE thebingo_test OWNER thebingo_user;"
"""
import asyncio
import uuid

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import sessionmaker

from backend.database.session import DetachedReadSessionLocal
from backend.models.agent_profile import AgentProfile
from backend.models.custom_agent import CustomAgent
from backend.models.organization import Organization
from backend.models.team import Team
from backend.models.team_membership import MemberRole, TeamMembership
from backend.models.user import User
from backend.services.conversation_service import ConversationService
from backend.services.heartbeat_context import build_orchestrator_context


@pytest.fixture
def prod_session(test_engine):
    """A session configured exactly like the chat handlers', bound to the test engine."""
    prod_kwargs = {k: v for k, v in DetachedReadSessionLocal.kw.items() if k != "bind"}
    Session = sessionmaker(bind=test_engine, **prod_kwargs)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def _make_user(db) -> User:
    user = User(id=str(uuid.uuid4()), email=f"sess-{uuid.uuid4()}@example.com", auth_provider="sso")
    db.add(user)
    db.commit()
    return user


def test_history_rows_stay_readable_after_the_session_closes(prod_session):
    """websocket.py ordering: load history -> add_message (COMMIT) -> close -> agent reads rows.

    The commit must not expire the history rows, or the first attribute read inside
    the orchestrator hits a detached+expired instance and raises DetachedInstanceError.
    """
    db = prod_session
    user = _make_user(db)
    conversation = ConversationService.create_conversation(db, user.id, title="t")
    ConversationService.add_message(db, conversation.id, "user", "first question")
    ConversationService.add_message(db, conversation.id, "assistant", "first answer")

    # Order matters: history is loaded *before* the user message is saved.
    history = ConversationService.get_conversation_history(db, conversation.thread_id, user.id)
    assert len(history) == 2
    ConversationService.add_message(db, conversation.id, "user", "second question")  # commits

    db.close()  # what chat.py / websocket.py do before the orchestrator run

    # graph.py `_build_messages` reads exactly these columns off the detached rows.
    assert [(m.role, m.content, m.attachments) for m in history] == [
        ("user", "first question", None),
        ("assistant", "first answer", None),
    ]


def test_add_message_returns_a_usable_pk_without_a_refresh(prod_session):
    """`assistant_msg.id` is read in websocket._persist_and_postprocess.

    Message has only Python-side column defaults, so the flush populates the PK —
    add_message needs no refresh() (which would only re-open a read transaction).
    """
    db = prod_session
    user = _make_user(db)
    conversation = ConversationService.create_conversation(db, user.id, title="t")

    message = ConversationService.add_message(db, conversation.id, "assistant", "answer")

    assert message.id is not None
    assert "id" not in sa_inspect(message).unloaded  # no lazy SELECT needed to read it

    db.close()
    assert message.content == "answer"  # still readable once detached


def test_custom_agents_carry_their_profile_after_the_session_closes(prod_session):
    """graph.py `_build_dynamic_tools` reads the lazy CustomAgent.profile relationship.

    A relationship — unlike a column — is unreadable on a detached row unless it was
    eager-loaded, and expire_on_commit=False does not help. build_orchestrator_context
    must joinedload it.
    """
    db = prod_session
    user = _make_user(db)
    org = Organization(id=str(uuid.uuid4()), name=f"org-{uuid.uuid4()}")
    team = Team(id=str(uuid.uuid4()), org_id=org.id, name=f"team-{uuid.uuid4()}")
    db.add_all([org, team])
    db.add(TeamMembership(id=str(uuid.uuid4()), team_id=team.id, user_id=user.id, role=MemberRole.ADMIN))
    profile = AgentProfile(
        id=str(uuid.uuid4()), user_id=user.id, agent_type="orchestrator",
        identity="I am a test agent", is_active=True,
    )
    db.add(profile)
    db.add(CustomAgent(
        id=str(uuid.uuid4()), user_id=user.id, team_id=team.id, name="a", description="d",
        system_prompt="x", profile_id=profile.id, is_active=True, tool_keys=[], connection_ids=[],
    ))
    db.commit()

    # query="": memory retrieval is gated on a truthy query (heartbeat_context.py),
    # and it would embed via OpenAI + search Qdrant. The custom_agents path is identical.
    ctx = asyncio.run(build_orchestrator_context(
        db=db, user=user, query="", connection_ids=None, thread_id=None,
    ))
    db.close()  # what chat.py / websocket.py do before the orchestrator run

    assert len(ctx.custom_agents) == 1
    agent = ctx.custom_agents[0]
    assert "profile" not in sa_inspect(agent).unloaded  # eager-loaded, so safe while detached
    assert getattr(agent, "profile", None).identity == "I am a test agent"  # graph.py:1008
