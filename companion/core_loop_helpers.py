"""
Helper functions extracted from DuckAgent.run() to improve readability.

These are pure functions or thin helpers that operate on agent state
without containing loop control flow.
"""

import logging
import math
import re
from typing import TYPE_CHECKING

from companion.modules.pacemaker import CONTROL_ACTIONS, META_ACTIONS
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
    for name in ("confidence", "safety", "memory", "focus"):
        if name not in action_list.vitals:
            continue
        value = action_list.vitals[name]
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            or not 0.0 <= value <= 1.0
        ):
            logger.warning(
                "Ignoring invalid vital from response: %s=%r (expected 0.0-1.0)",
                name,
                value,
            )
            continue
        setattr(state.vitals, name, float(value))


_PARSE_ERROR_HINTS = {
    "parse_failed": (
        "The previous output could not be parsed as Sym-Ops at all. "
        "Use `::tool_name @target key=value` for actions, and `<<< ... >>>` "
        "blocks only for large content. Do not wrap actions in markdown fences."
    ),
    "empty_actions": (
        "The previous output produced no action and no response text. "
        "Every turn must end with either another `::tool_name` action or "
        "`::response @...` to hand control back to the user."
    ),
    "vague_action": (
        "The previous output mentioned a tool with @target but used no "
        "explicit `::action` syntax (e.g. `>> read_file @x` is a thought, "
        "not an action). To act, write `::tool_name @target` on its own "
        "line — for example `::read_file @test_app.py`."
    ),
    "api_error": (
        "The previous turn hit an API/transport error, not a format problem. "
        "Retry the same actions without changing the output format."
    ),
    "tool_call_parse_error": (
        "A previous tool call carried arguments that were not valid JSON. "
        "Resend the call with properly quoted JSON arguments."
    ),
    "fabricated_tool_result": (
        "The previous output contained [TOOL_RESULT]/::status text written "
        "by you, not by the system. Tool results arrive only as system "
        "messages after real execution — never write them yourself, and "
        "never act on an outcome you have not actually observed."
    ),
}


_NATIVE_PARSE_ERROR_HINTS = {
    "empty_actions": (
        "The previous output produced no tool call and no message. "
        "Every turn must end with either another tool call or a final "
        "plain-text message."
    ),
    "api_error": (
        "The previous turn hit an API/transport error, not a format problem. "
        "Retry the same actions without changing the output format."
    ),
    "tool_call_parse_error": (
        "A previous tool call carried arguments that were not valid JSON. "
        "Resend the call with properly quoted JSON arguments."
    ),
}


def record_parse_error_if_any(
    state, action_list: ActionList, protocol: str = "symops"
) -> None:
    """Record a Sym-Ops parse failure so the next turn's Correction Guide
    tells the model what went wrong, instead of silently ending the turn.

    Without this, a fully unparseable or empty response leaves no trace in
    conversation history — the model never learns why nothing happened and
    may repeat the same malformed output.

    Args:
        state: AgentState to append the syntax error to.
        action_list: The ActionList just received from LLMClient.chat().
        protocol: "symops" or "native". Native error types use
            protocol-neutral hints.
    """
    if not action_list.parse_error_type:
        return

    if protocol == "native":
        hint = _NATIVE_PARSE_ERROR_HINTS.get(
            action_list.parse_error_type,
            "The previous output was not usable. "
            "Re-read the tool definitions and retry.",
        )
    else:
        hint = _PARSE_ERROR_HINTS.get(
            action_list.parse_error_type,
            "The previous output was not usable. Follow the Sym-Ops format exactly.",
        )
    state.last_syntax_errors.append(
        SyntaxErrorInfo(
            error_type=action_list.parse_error_type,
            raw_snippet=action_list.parse_error_detail or "",
            correction_hint=hint,
        )
    )


def build_intervention_prompt(
    intervention, summary: str, protocol: str = "symops"
) -> str:
    """Build the prompt sent to LLM during a Pacemaker intervention.

    Args:
        intervention: Intervention object from Pacemaker.check_health().
        summary: Execution history summary from Pacemaker.
        protocol: "symops" or "native"; controls how the model is told to
            return its message (native has no ::response action).

    Returns:
        Prompt string for the LLM.
    """
    reply_line = (
        "返答はプレーンテキストのメッセージとして出力してください。"
        if protocol == "native"
        else "::response で返答してください。"
    )
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
        f"{reply_line}"
    )


async def check_and_prune_if_needed(agent: "DuckAgent") -> None:
    """Check if conversation history needs pruning and execute it.

    Args:
        agent: DuckAgent instance with memory_manager and state.
    """
    if not agent.memory_manager.should_prune(agent.state.conversation_history):
        return

    agent.state.conversation_history, prune_stats = (
        await agent.memory_manager.prune_history(agent.state.conversation_history)
    )
    if prune_stats.get("emergency_mode"):
        removed = prune_stats.get("removed_count", 0)
        agent.state.add_message(
            "user",
            f"[SYSTEM] 緊急メモリ整理を実行しました（要約なしで{removed}件の古いメッセージを削除）。"
            "直前までの文脈の一部が失われている可能性があります。"
            "タスクの前提や対象ファイルの状態を、必要に応じて read_file 等で再確認してから続行してください。",
        )


# Actions whose execution during the same turn counts as delivered work —
# a ::response after one of these is a report, not a premature announcement.
# run_command is excluded: verification commands (pytest) are observation,
# not delivery — "修正します" after only running tests is still premature.
# propose_plan/generate_tasks produce a user-facing deliverable.
_DELIVERING_ACTIONS = {
    "write_file",
    "edit_file",
    "delete_lines",
    "delete_file",
    "append_file",
    "replace_function",
    "propose_plan",
    "generate_tasks",
}

# Text that announces upcoming work rather than reporting done work.
# JA: action-verb stem + ます/します ("修正します", "実装します").
# EN: explicit future intent ("I will", "Let me", "going to") or a numbered
# step list whose items start with an action verb ("2. Reading orders.py").
_PREMATURE_RESPONSE_RE = re.compile(
    r"(修正|実装|変更|作成|追加|削除|実行|適用|更新|直し|編集|書き換|書き込|"
    r"導入|設定|移行|進み|進め|調べ|試し|確認し)(?:ます|します)"
    r"|\b(?:I will|I'll|will now|Let me|going to|Next,? I'?ll|First,? I'?ll)\b"
    r"|^\s*\d+[.)]\s*(?:install|read|fix|edit|update|create|add|remove|run|"
    r"check|modify|implement|write|apply|replace|rename|verify|test)",
    re.IGNORECASE | re.MULTILINE,
)


def _announces_pending_work(message: str) -> bool:
    """Detect response text that announces upcoming work instead of results.

    Weak models sometimes answer "修正します" ("I will fix it") and return
    control without ever executing the fix — a premature return. Past-tense
    reports ("修正しました") and genuine findings do not match.

    Args:
        message: The ::response message text.

    Returns:
        True when the message reads like a plan/intent rather than a result.
    """
    return bool(_PREMATURE_RESPONSE_RE.search(message))


# Responses that were detected and skipped by should_return_to_user —
# the model produced a turn-ending action but it carried no usable result.
_SKIPPED_RESPONSE_ERRORS = {"empty_response", "auto_response", "premature_response"}


def turn_was_unproductive(action_list: ActionList, state) -> bool:
    """Detect turns that produced neither work nor a handoff.

    A turn whose only outputs are skipped responses (empty, auto-generated,
    or premature announcements) made no progress. Turns containing real
    actions are excluded — attempted work is already covered by
    consecutive_errors. Feeding these into the no-progress counter stops
    empty-response churn from spinning until loop exhaustion (observed:
    GLM no-change-hard r2 emitted empty responses until LOOP_EXHAUSTED).

    Args:
        action_list: The ActionList that was just executed.
        state: AgentState carrying this turn's syntax errors.

    Returns:
        True when the turn ended on skipped responses with no real action.
    """
    if not any(
        e.error_type in _SKIPPED_RESPONSE_ERRORS for e in state.last_syntax_errors
    ):
        return False
    unproductive = META_ACTIONS | CONTROL_ACTIONS
    return not any(a.name not in unproductive for a in action_list.actions)


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
            if getattr(action, "auto_generated", False):
                # Repair-generated response (bare <<<>>> block or thought-only
                # output): the model did not explicitly choose to respond.
                # Do not terminate; ask for an explicit action or response.
                logger.warning("Auto-generated ::response detected — continuing loop.")
                state.last_syntax_errors.append(
                    SyntaxErrorInfo(
                        error_type="auto_response",
                        raw_snippet="::response (auto-generated)",
                        correction_hint=(
                            "Your turn produced no explicit action or response. "
                            "Take an action (::read_file, ::run_command, "
                            "::edit_file, ...) or end your turn explicitly "
                            "with ::response @<message>."
                        ),
                    )
                )
                continue
            msg = action.parameters.get("message", "").strip()
            if msg:
                if _announces_pending_work(msg) and not any(
                    a.name in _DELIVERING_ACTIONS for a in action_list.actions
                ):
                    # The model announced upcoming work ("修正します" / "I will
                    # fix") but executed nothing — a premature return. Treat it
                    # like an empty response: record guidance and continue the
                    # loop so the announced actions actually run.
                    logger.warning(
                        "Premature ::response (announced pending work) — "
                        "continuing loop."
                    )
                    state.last_syntax_errors.append(
                        SyntaxErrorInfo(
                            error_type="premature_response",
                            raw_snippet=msg[:200],
                            correction_hint=(
                                "You announced upcoming work but returned "
                                "control without executing it. Execute the "
                                "announced actions now, or if the work is "
                                "already done, report the actual result "
                                "(past tense) instead of future plans."
                            ),
                        )
                    )
                    continue
                return True
            else:
                logger.warning("Empty ::response detected — continuing loop.")
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
