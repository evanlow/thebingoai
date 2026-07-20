"""Shared agent-prompt resolver.

`_resolve_data_agent_prompt` and `_resolve_dashboard_agent_prompt` both did:
  1. Try to load the user's active AgentProfile for `agent_type`.
  2. If found, build a RuntimeContext and call ProfileRenderer.render.
  3. Otherwise fall back to the agent-specific prompt builder.

Centralizes that flow so each call site only supplies the agent-specific bits.
"""
from typing import Any, Callable, Dict, Optional

from backend.agents.context import AgentContext
from backend.agents.profile_renderer import ProfileRenderer, RuntimeContext


def resolve_agent_prompt(
    *,
    agent_type: str,
    context: AgentContext,
    fallback: Callable[[], str],
    db_session_factory: Optional[Callable] = None,
    runtime_context_extras: Optional[Dict[str, Any]] = None,
    log_prefix: Optional[str] = None,
    suffix_builder: Optional[Callable[[], str]] = None,
) -> str:
    """Resolve a per-agent prompt from the active AgentProfile, else `fallback()`.

    `suffix_builder` is applied only on the profile branch — runtime context
    (pre-built data context, connector hints, dialect hints) that the fallback
    builder already includes itself.
    """
    import logging
    logger = logging.getLogger(log_prefix or __name__)

    if db_session_factory:
        try:
            db = db_session_factory()
            from backend.models.agent_profile import AgentProfile
            profile = db.query(AgentProfile).filter(
                AgentProfile.user_id == context.user_id,
                AgentProfile.agent_type == agent_type,
                AgentProfile.is_active.is_(True),
            ).first()
            if profile:
                rt_ctx = RuntimeContext(
                    available_connections=context.available_connections,
                    connection_metadata=context.connection_metadata,
                    **(runtime_context_extras or {}),
                )
                prompt = ProfileRenderer.render(profile, rt_ctx)
                db.close()
                if suffix_builder:
                    try:
                        prompt += suffix_builder()
                    except Exception as exc:
                        logger.warning(f"{agent_type} prompt suffix build failed: {exc}")
                return prompt
            db.close()
        except Exception as exc:
            logger.warning(f"{agent_type} profile load failed, using legacy: {exc}")
    return fallback()
