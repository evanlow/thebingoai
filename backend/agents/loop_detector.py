"""Pre-model hook that detects repeated tool calls.

Shared by orchestrator, data_agent, and dashboard_agent. Catches three patterns:
1. Identical consecutive calls (same tool + same args) → injects a SystemMessage.
2. Same tool called many times with different args (varied SQL against
   sqlite_master, etc.) → injects a SystemMessage.
3. Absolute total tool-call cap → raises LoopDetectedError so the orchestrator
   can surface it to the UI as a hard stop (the LLM cannot ignore an exception).
"""
import json
import logging

from langchain_core.messages import SystemMessage

from backend.agents.exceptions import LoopDetectedError

logger = logging.getLogger(__name__)


def make_loop_detector(max_repeats: int = 2, max_same_tool: int = 10, max_total_calls: int = 25):
    limit = max(max_repeats, max_same_tool)

    def detect_loop(state):
        messages = state.get("messages", [])
        recent_calls = []
        recent_tool_names = []
        for msg in reversed(messages):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    key = (tc.get("name"), json.dumps(tc.get("args", {}), sort_keys=True))
                    recent_calls.append(key)
                    recent_tool_names.append(tc.get("name"))
            if len(recent_calls) >= limit:
                break

        if len(recent_calls) >= max_repeats:
            if len(set(recent_calls[:max_repeats])) == 1:
                tool_name = recent_calls[0][0]
                logger.warning(f"Loop detected: {tool_name} called {max_repeats} times with same args, injecting stop")
                return {"messages": [SystemMessage(content=(
                    f"[Loop detected] You have called {tool_name} with the same arguments {max_repeats} times and got the same result. "
                    "Accept the result as final and respond to the user. Do not call this tool again."
                ))]}

        if len(recent_tool_names) >= max_same_tool:
            last_n = recent_tool_names[:max_same_tool]
            if len(set(last_n)) == 1:
                tool_name = last_n[0]
                logger.warning(f"Tool-family loop detected: {tool_name} called {max_same_tool} times with varying args, injecting stop")
                return {"messages": [SystemMessage(content=(
                    f"[Loop detected] You have called {tool_name} {max_same_tool} times in a row with different arguments "
                    "but no useful result. The information is not available through this approach. "
                    "Report this to the user and move on. Do NOT try more variations."
                ))]}

        if max_total_calls:
            total = sum(
                len(msg.tool_calls)
                for msg in messages
                if hasattr(msg, "tool_calls") and msg.tool_calls
            )
            if total >= max_total_calls:
                logger.warning(f"Tool-call budget exhausted: {total}/{max_total_calls} calls used, raising LoopDetectedError")
                raise LoopDetectedError(
                    f"Tool-call budget exhausted: {total}/{max_total_calls} calls used",
                    total_calls=total,
                )

        return {}

    return detect_loop
