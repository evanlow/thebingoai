"""Layer-4 response-quality judge.

After the orchestrator produces a final answer, this judge evaluates whether
the answer actually resolves the user's question. If not, the orchestrator
retries once with the judge's directive.

Falls open on any error (judge timeout, provider failure, missing model config)
so chat never blocks on the judge itself.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from pydantic import BaseModel, Field

from backend.config import settings
from backend.llm.factory import get_provider
from backend.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class JudgeVerdict(BaseModel):
    """Structured verdict returned by the judge LLM."""

    resolved: bool = Field(
        description="True if the response fully answers the user's question; false if it dodged, offered a retry, leaked a technical error, or left the task incomplete.",
    )
    reason: str = Field(
        description="One short sentence explaining the verdict — used for logs and failure-case capture.",
    )
    suggested_directive: str = Field(
        default="",
        description="If resolved=false, a direct instruction to the assistant on how to finish the task (reference the fix it already proposed, tell it not to ask). Empty when resolved=true.",
    )
    highlighted_response: Optional[str] = Field(
        default=None,
        description="When resolved=true, a copy of the assistant response with meaningful whitespace-free numeric tokens wrapped in ==...== for downstream orange rendering. Do NOT change any wording, punctuation, capitalization, whitespace, or formatting — only insert == markers. Null when resolved=false or nothing qualifies.",
    )


_JUDGE_SYSTEM_PROMPT = """You evaluate whether an assistant's response fully resolves a user's question.

Mark `resolved: false` when ANY of these are true:
- The response offers to retry with a fix but asks the user for permission ("if you want, I can...", "shall I...", "would you like me to...")
- The response acknowledges it couldn't complete the task ("I couldn't fully compute", "I was unable to...", "the tool failed")
- The response leaks a technical error message (exception types, stack traces, serialization errors like Decimal/JSON, SQL error codes)
- The response gives partial data where a full answer was asked for, without the user having limited scope — **only applicable when the context shows no tools were used to fetch the data**
- **Deliverable mismatch on build/create/setup intent:** the user asked the assistant to BUILD, CREATE, SET UP, or MAKE a runtime artifact (dashboard, pipeline, connector, schedule, chart, widget, report, sync, etc.) AND the response contains fenced SQL code blocks (```sql), fenced JSON code blocks (```json), pseudo-JSON configuration dumps, "here is the spec you can adapt", "you can copy-paste this into your editor", or any other "I wrote the building blocks for you to assemble" pattern. The user wanted the artifact running, not its source code. Dumping SQL or JSON config back to the user is offloading the work — mark it unresolved even if the response sounds confident and complete. Exception: the user EXPLICITLY asked to see the SQL/JSON ("show me the SQL", "give me the JSON config", "what query is this using") — that's a legitimate code-disclosure request, not a build request.

Mark `resolved: true` when:
- The response directly answers what the user asked
- The response asks a SEMANTIC clarification the user must answer (e.g., "which of these two tables?", "include canceled orders?") — that's a legitimate question, not a failure
- The response explains a terminal limitation in plain language and offers a real next step (NOT a retry-with-fix offer)
- The user explicitly asked to see code/config and the response shows that code/config (not a build/create request)
- **The context shows tools were invoked to fetch or compute data AND the response summarises or presents that data** — a response that presents tool-fetched data is resolved even if it could have included more detail

STRICTNESS: retries are expensive — only mark `resolved: false` when you are genuinely confident the response fails one of the rules above. When the context shows several tools were invoked (a complex, multi-tool turn), that is evidence of real work done; do not mark `resolved: false` on vague dissatisfaction, missing polish, or "could have been more thorough" — reserve it for clear-cut failures (asks permission, admits failure, leaks an error, dumps SQL/JSON instead of building). If you are on the fence, prefer `resolved: true`.

When `resolved: false`, write `suggested_directive` as a direct instruction to the assistant on how to complete the task. Reference the fix the assistant already proposed (if present), and tell it to proceed without asking for permission. For deliverable-mismatch failures, the directive should be: "Do not include SQL or JSON in your reply. Use the appropriate tool to actually build the artifact. If a tool returns partial failures, retry the failing items with corrected input rather than describing them in prose." """


_HIGHLIGHT_RULES = """

HIGHLIGHTING RULES (applies only when resolved=true):

Populate `highlighted_response` with a copy of the assistant response where meaningful headline numbers are wrapped in `==...==` for downstream orange rendering. Strict rules:
- Only wrap single **whitespace-free** tokens. Examples: `==4,863==`, `==17==`, `==RM500==`, `==12.5%==`, `==$1.2M==`.
- NEVER place whitespace inside `==...==`. `==4,863 units==` is INVALID.
- Focus on aggregate metrics, counts, percentages, and currency figures — the numbers a reader would screenshot. Skip years (e.g. 2021), page numbers, row IDs, footnote markers.
- Skip numbers inside fenced code blocks (```...```) or markdown table cells.
- Cap at roughly 8 marks per response. If nothing qualifies, leave `highlighted_response` null.
- Do NOT change any wording, punctuation, capitalization, whitespace, or formatting. Only insert `==` markers. The unmarked text must be byte-identical to the original.

When `resolved=false`, leave `highlighted_response` null."""


_JUDGE_RESPONSE_MAX_CHARS = 2000


async def judge_response(
    user_question: str,
    response: str,
    llm_provider: Optional[BaseLLMProvider] = None,
    tool_result_count: int = 0,
) -> JudgeVerdict:
    """Evaluate whether `response` resolves `user_question`.

    Returns a `JudgeVerdict`. Always returns — falls open (resolved=True) on
    any exception, timeout, or missing config so the judge never blocks chat.

    Args:
        user_question: The user's original question for this turn.
        response: The orchestrator's final answer (already redacted/sanitized).
        llm_provider: Optional override; normally the judge resolves its own
            provider from settings.judge_llm_provider.
    """
    if not settings.judge_enabled:
        return JudgeVerdict(resolved=True, reason="judge disabled")
    if not settings.judge_llm_model:
        logger.warning(
            "JUDGE_LLM_MODEL not configured in .env — Layer-4 judge disabled, falling open"
        )
        return JudgeVerdict(resolved=True, reason="judge model not configured")
    if not response or not response.strip():
        return JudgeVerdict(resolved=True, reason="empty response, nothing to judge")

    provider_name = settings.judge_llm_provider or settings.default_llm_provider
    try:
        provider = llm_provider or get_provider(provider_name)
        llm = provider.get_langchain_llm(model=settings.judge_llm_model)
        structured_llm = llm.with_structured_output(JudgeVerdict)

        system_prompt = _JUDGE_SYSTEM_PROMPT
        if settings.judge_highlight_enabled:
            system_prompt += _HIGHLIGHT_RULES

        # Truncate response to avoid slow judge calls on large outputs (Fix 3)
        truncated = response[:_JUDGE_RESPONSE_MAX_CHARS]
        truncation_note = (
            f"\n[Note: response truncated to {_JUDGE_RESPONSE_MAX_CHARS} chars for evaluation]"
            if len(response) > _JUDGE_RESPONSE_MAX_CHARS else ""
        )

        # Tell judge about tool calls so it doesn't misfire on tool-backed responses (Fix 4)
        tool_context = (
            f"\n[Context: the assistant invoked {tool_result_count} tool(s) to produce this response]"
            if tool_result_count > 0 else ""
        )

        _t0 = time.perf_counter()
        verdict: JudgeVerdict = await asyncio.wait_for(
            structured_llm.ainvoke(
                [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"USER QUESTION:\n{user_question}"
                            f"{tool_context}"
                            f"\n\nASSISTANT RESPONSE:\n{truncated}{truncation_note}"
                        ),
                    },
                ]
            ),
            timeout=settings.judge_timeout_seconds,
        )
        logger.info(
            "[LATENCY][judge] LLM call: %dms (model=%s resolved=%s)",
            int((time.perf_counter() - _t0) * 1000),
            settings.judge_llm_model,
            verdict.resolved,
        )
        return verdict
    except asyncio.TimeoutError:
        logger.warning(
            "Response judge timed out after %ds — falling open", settings.judge_timeout_seconds
        )
        return JudgeVerdict(resolved=True, reason="judge timeout")
    except Exception as exc:
        logger.warning("Response judge failed, falling open: %s", exc)
        return JudgeVerdict(resolved=True, reason=f"judge error: {type(exc).__name__}")
