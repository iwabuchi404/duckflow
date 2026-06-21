"""
Helper functions extracted from DuckAgent.run() to improve readability.

These are pure functions or thin helpers that operate on agent state
without containing loop control flow.
"""

import logging
from typing import TYPE_CHECKING

from companion.state.agent_state import ActionList, SyntaxErrorInfo

if TYPE_CHECKING:
    from companion.core import DuckAgent

logger = logging.getLogger(__name__)


def update_vitals_from_response(state, action_list: ActionList) -> None:
    """Update vitals from LLM response action_list.

    Args:
        state: AgentState to update.
        action_list: Parsed ActionList containing vitals dict.
    """
    if not action_list.vitals:
        return

    logger.info(f"Updating vitals from response: {action_list.vitals}")
    if "confidence" in action_list.vitals:
        state.vitals.confidence = action_list.vitals["confidence"]
    if "safety" in action_list.vitals:
        state.vitals.safety = action_list.vitals["safety"]
    if "memory" in action_list.vitals:
        state.vitals.memory = action_list.vitals["memory"]
    if "focus" in action_list.vitals:
        state.vitals.focus = action_list.vitals["focus"]


def build_intervention_prompt(intervention, summary: str) -> str:
    """Build the prompt sent to LLM during a Pacemaker intervention.

    Args:
        intervention: Intervention object from Pacemaker.check_health().
        summary: Execution history summary from Pacemaker.

    Returns:
        Prompt string for the LLM.
    """
    return (
        "## Pacemaker Intervention\n"
        f"Type: {intervention.type} | Severity: {intervention.severity}\n"
        f"{intervention.message}\n\n"
        f"## Recent Execution History\n{summary}\n\n"
        "## Your Task\n"
        "ユーザーに何が起きているか簡潔に説明してください:\n"
        "1. 何をしようとしていたか\n"
        "2. 何が問題だったか\n"
        "3. 続行/中止/方針変更の選択肢を提示\n"
        "::response で返答してください。"
    )


async def check_and_prune_if_needed(agent: "DuckAgent") -> None:
    """Check if conversation history needs pruning and execute it.

    Args:
        agent: DuckAgent instance with memory_manager and state.
    """
    if not agent.memory_manager.should_prune(agent.state.conversation_history):
        return

    agent.state.conversation_history, prune_stats = (
        await agent.memory_manager.prune_history(
            agent.state.conversation_history
        )
    )
    if prune_stats.get("emergency_mode"):
        removed = prune_stats.get("removed_count", 0)
        agent.state.add_message(
            "user",
            f"[SYSTEM] 緊急メモリ整理を実行しました（要約なしで{removed}件の古いメッセージを削除）。"
            "直前までの文脈の一部が失われている可能性があります。"
            "タスクの前提や対象ファイルの状態を、必要に応じて read_file 等で再確認してから続行してください。",
        )


def should_return_to_user(action_list: ActionList, state) -> bool:
    """Determine if the autonomous loop should return control to the user.

    Returns True if a terminal action (response with content, exit, duck_call)
    was executed, False otherwise.

    Args:
        action_list: The ActionList that was just executed.
        state: AgentState for recording syntax errors.

    Returns:
        True if the loop should break and return to user.
    """
    for action in action_list.actions:
        if action.name in ["exit", "duck_call"]:
            return True
        if action.name == "response":
            msg = action.parameters.get("message", "").strip()
            if msg:
                return True
            else:
                logger.warning(
                    "Empty ::response detected — continuing loop."
                )
                state.last_syntax_errors.append(
                    SyntaxErrorInfo(
                        error_type="empty_response",
                        raw_snippet="::response (empty)",
                        correction_hint=(
                            "::response was called with no message. "
                            "If investigation is in progress, continue observing. "
                            "Use ::response only when you have a result to deliver."
                        ),
                    )
                )
    return False
