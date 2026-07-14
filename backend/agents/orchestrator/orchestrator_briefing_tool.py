"""emit_briefing — terminal orchestrator tool that persists a structured briefing."""

import logging
from typing import Callable
from langchain_core.tools import tool
from pydantic import ValidationError

from backend.agents.context import AgentContext
from backend.schemas.briefing import BriefingPayload

logger = logging.getLogger(__name__)


def _post_chat_message(db_session, *, user_id: str, briefing_id: int, headline: str) -> None:
    """Insert an assistant message into the user's permanent Bingo AI conversation."""
    from backend.models.message import Message
    from backend.services.conversation_service import ConversationService

    conv = ConversationService.get_or_create_permanent_conversation(db_session, user_id)

    msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=headline,
        source="heartbeat",
        briefing_id=briefing_id,
    )
    db_session.add(msg)


def _emit_ws(user_id: str, briefing_id: int) -> None:
    """Push briefing.ready event to the user via WebSocket (sync, Celery-safe)."""
    from backend.services.ws_connection_manager import ConnectionManager
    ConnectionManager.publish_to_user_sync(user_id, {
        "type": "briefing.ready",
        "briefing_id": briefing_id,
    })


def build_briefing_tools(
    context: AgentContext,
    db_session_factory: Callable,
    briefing_id: int,
) -> list:
    """Factory: returns [emit_briefing] bound to a specific briefing row."""

    @tool
    async def emit_briefing(payload: dict) -> str:
        """
        Deliver the final structured briefing for the current dashboard analysis.
        Call this exactly ONCE at the end of your analysis with the complete briefing payload.

        Args:
            payload: A BriefingPayload dict with keys:
                headline (str): one-line headline, ≤240 chars.
                deck (str): 1–2 sentence summary, ≤600 chars.
                kpis (list[Kpi]): 0–3 KPI tiles. Each: {label, value, delta_vs_prev?, delta_direction?}.
                sections (list[Section]): ≥1 numbered sections. Each: {heading, prose, widget_id?}.
                key_takeaways (list[str]): exactly 3 bullets.
                recommended_actions (list[str]): 2–4 concrete next steps derived from the key findings.
        """
        try:
            validated = BriefingPayload.model_validate(payload)
        except ValidationError as e:
            logger.warning("emit_briefing validation failed for briefing %s: %s", briefing_id, e)
            return f"invalid briefing payload: {e.errors()[:3]}"

        db = db_session_factory()
        try:
            from backend.models.briefing import Briefing
            briefing = db.query(Briefing).filter(Briefing.id == briefing_id).first()
            if not briefing:
                return f"briefing {briefing_id} not found"
            if briefing.user_id != context.user_id:
                return "briefing user mismatch"

            payload_dump = validated.model_dump()
            # Snapshot each referenced widget's rendered data now so the briefing
            # view renders instantly instead of re-running every widget's SQL.
            try:
                from backend.models.dashboard import Dashboard
                from backend.models.user import User
                from backend.api.widget_data import render_widget_snapshots
                from backend.services.briefing_runner import non_filter_widgets
                dashboard = db.query(Dashboard).filter(Dashboard.id == briefing.dashboard_id).first()
                user = db.query(User).filter(User.id == context.user_id).first()

                # The prompt catalog omits filter widgets, but analyze_dashboard still
                # shows them, so drop any section that references one rather than
                # rendering a dashboard control as if it were data.
                if dashboard:
                    referenceable = {
                        w.get("id") for w in non_filter_widgets(dashboard.widgets or [])
                    }
                    for section in payload_dump["sections"]:
                        if section.get("widget_id") and section["widget_id"] not in referenceable:
                            logger.info(
                                "Briefing %s: dropping non-referenceable widget_id %r",
                                briefing_id, section["widget_id"],
                            )
                            section["widget_id"] = None

                widget_ids = [
                    s["widget_id"] for s in payload_dump["sections"] if s.get("widget_id")
                ]
                if dashboard and user and widget_ids:
                    payload_dump["widget_snapshots"] = await render_widget_snapshots(
                        dashboard, widget_ids, user, db,
                    )
            except Exception as e:
                logger.warning("Briefing %s snapshot step failed (non-fatal): %s", briefing_id, e)

            briefing.payload = payload_dump
            briefing.status = "ready"
            briefing.error = None

            _post_chat_message(db, user_id=context.user_id, briefing_id=briefing_id, headline=validated.headline)
            db.commit()

            _emit_ws(context.user_id, briefing_id)
            return f"briefing {briefing_id} ready"
        except Exception as e:
            db.rollback()
            logger.exception("emit_briefing persistence failed: %s", e)
            return f"persistence error: {e}"
        finally:
            db.close()

    return [emit_briefing]
