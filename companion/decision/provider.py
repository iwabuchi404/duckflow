"""Decision Provider — DecisionContext を判定して DecisionResult を返す。

初回実験ではエージェントと同じモデルを binary 判定に使う
SameModelDecisionProvider を提供する。Provider は差し替え可能
（OpenJev/logit 方式は後続実験で別 Provider として実装する）。
"""

import logging
import os
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

# v2: 構造化推論版。binary 即答ではなく、先に「結果を決める要素の列挙」と
# 「証拠（読んだファイル・計画）から複数解釈が生じるか」の検討を強制する。
# frontier-ambiguous-semantic のように、ファイル内容を見て初めて生じる
# 曖昧さ（dedup 基準等）を SameModel judge が見落とした v1/v2 の失敗への対策。
CLARIFICATION_JUDGE_PROMPT_V2 = """You are a decision module inside a coding agent. Your ONLY job is to judge whether the agent must ask the user a clarifying question BEFORE doing any work.

Think step by step, briefly:
1. RESTATE what concrete result the user expects (target, scope, selection criteria).
2. LIST every element of that result that is not explicitly specified in the task.
3. CHECK the provided evidence (workspace files, file excerpts, current plan): does the data itself allow multiple plausible readings of an unspecified element? Examples: several valid dedup keys, filters, units, orderings, or "which items count" rules.
4. CHECK whether the user delegated that choice to the agent ("your choice", "appropriate", "as needed" — or silence).
5. VERDICT: an unspecified element requires ASK only when at least two plausible readings would produce materially different results AND the user did not delegate the choice.

Do NOT answer ASK merely because multiple implementation approaches exist. Do NOT try to solve the task.

Reply in EXACTLY this format:
ANALYSIS: <2-4 short lines covering steps 1-4>
DECISION: CONTINUE
or
DECISION: ASK
FOCUS: <the single most important unresolved choice, one line>
"""

# 判定プロンプトのバリアント。既定は v1（既往ベースラインとの互換性維持）。
# DUCKFLOW_DECISION_PROMPT=v2 で構造化推論版に切替（実験用、eval meta に記録）。
_JUDGE_PROMPTS = {
    "v1": CLARIFICATION_JUDGE_PROMPT,
    "v2": CLARIFICATION_JUDGE_PROMPT_V2,
}


def judge_prompt_variant() -> str:
    """有効な判定プロンプトのバリアント名を返す。

    Returns:
        "v1" または "v2"。未知の指定値は v1 にフォールバック。
    """
    variant = os.environ.get("DUCKFLOW_DECISION_PROMPT", "v1").strip().lower()
    return variant if variant in _JUDGE_PROMPTS else "v1"


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
        {"role": "system", "content": _JUDGE_PROMPTS[judge_prompt_variant()]},
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
        # v2 prompt は ANALYSIS 行を先に出力するため余裕を持たせる
        max_tokens = 400 if judge_prompt_variant() == "v2" else 150
        raw = await self.llm.chat(messages, raw=True, max_tokens=max_tokens)
        return parse_binary_decision(raw if isinstance(raw, str) else str(raw))
