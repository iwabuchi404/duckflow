"""Decision Provider — DecisionContext を判定して DecisionResult を返す。

初回実験ではエージェントと同じモデルを binary 判定に使う
SameModelDecisionProvider を提供する。Provider は差し替え可能
（OpenJev/logit 方式は後続実験で別 Provider として実装する）。
"""

import logging
from typing import Any, Protocol

from companion.decision.models import (
    ACTION_ASK_USER,
    ACTION_CONTINUE,
    DecisionContext,
    DecisionRequest,
    DecisionResult,
)

logger = logging.getLogger(__name__)

# needs_clarification 用の binary 判定プロンプト。
# Interpretation Gate（静的な注意書き）とは異なり、こちらは判定専用の
# 別呼び出しであり、出力フォーマットを強制する。
CLARIFICATION_JUDGE_PROMPT = """You are a decision module inside a coding agent. Your ONLY job is to judge whether the agent must ask the user a clarifying question BEFORE doing any work.

Judge using these rules:
1. Answer ASK only when the user's intended result cannot be determined safely — i.e. an unresolved choice about the target, scope, quantity, unit, or selection criteria can materially change the outcome.
2. Answer CONTINUE when the request is fully specified, or when the only open choices are implementation details the agent may decide itself.
3. Do NOT answer ASK merely because multiple implementation approaches exist.
4. Do NOT try to solve the task yourself. Output only the judgment.

Reply in EXACTLY this format:
DECISION: CONTINUE
or
DECISION: ASK
FOCUS: <the single most important unresolved choice, one line>
"""


class DecisionProvider(Protocol):
    """Decision Provider のプロトコル。実装は差し替え可能。"""

    async def decide(
        self, context: DecisionContext, request: DecisionRequest
    ) -> DecisionResult:
        """コンテキストを判定して DecisionResult を返す。"""
        ...


def render_decision_messages(
    context: DecisionContext, request: DecisionRequest
) -> list[dict[str, str]]:
    """DecisionContext を判定用メッセージ列にレンダリングする。

    Args:
        context: 判断用コンテキスト。
        request: 判断要求。

    Returns:
        LLM 呼び出し用の messages。
    """
    parts = [f"Request type: {request.type}", "", "User task:", context.user_request]
    if context.recent_actions:
        parts += ["", "Recent actions: " + ", ".join(context.recent_actions)]
    if context.workspace_files:
        parts += ["", "Workspace files:"] + [f"- {f}" for f in context.workspace_files]
    if context.file_excerpts:
        parts += ["", "Files already read:"]
        parts += context.file_excerpts
    if context.current_plan:
        parts += ["", "Current plan:", context.current_plan]
    if context.known_facts:
        parts += ["", "Known facts:"] + [f"- {f}" for f in context.known_facts]
    if context.assumptions:
        parts += ["", "Unresolved assumptions:"] + [
            f"- {a}" for a in context.assumptions
        ]
    return [
        {"role": "system", "content": CLARIFICATION_JUDGE_PROMPT},
        {"role": "user", "content": "\n".join(parts)},
    ]


def parse_binary_decision(raw: str) -> DecisionResult:
    """Provider の生出力を DecisionResult にパースする。

    "DECISION: ASK" / "DECISION: CONTINUE" と任意の "FOCUS:" 行を読む。
    判別不能な出力は安全側（continue）に倒す。

    Args:
        raw: プロバイダの生テキスト出力。

    Returns:
        DecisionResult。action は "ask_user" または "continue"。
    """
    result = DecisionResult(raw=raw)
    decision_token = ""
    for line in raw.splitlines():
        line = line.strip()
        if line.upper().startswith("DECISION:"):
            decision_token = line.split(":", 1)[1].strip().upper()
        elif line.upper().startswith("FOCUS:"):
            result.focus = line.split(":", 1)[1].strip()
        elif line.upper().startswith("REASON:"):
            result.reason = line.split(":", 1)[1].strip()
    if "ASK" in decision_token:
        result.action = ACTION_ASK_USER
    else:
        # "CONTINUE" 明示でもパース不能でも、判断に失敗した場合は
        # エージェントの通常動作を止めないよう continue に倒す。
        result.action = ACTION_CONTINUE
    return result


class SameModelDecisionProvider:
    """エージェントと同じ LLM を binary 判定に使う Provider（H-1 初回実験）。"""

    def __init__(self, llm: Any) -> None:
        """Args: llm: エージェントと同じ LLMClient インスタンス。"""
        self.llm = llm

    async def decide(
        self, context: DecisionContext, request: DecisionRequest
    ) -> DecisionResult:
        """同モデルに binary 判定を問い合わせる。

        raw=True で構造化パースを回避し、短い判定テキストだけを取る。

        Args:
            context: 判断用コンテキスト。
            request: 判断要求。

        Returns:
            DecisionResult。失敗時は例外を上位に伝える（Engine 側で
            continue フォールバックする）。
        """
        messages = render_decision_messages(context, request)
        raw = await self.llm.chat(messages, raw=True, max_tokens=150)
        return parse_binary_decision(raw if isinstance(raw, str) else str(raw))
