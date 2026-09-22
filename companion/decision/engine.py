"""Decision Engine — Pacemaker 発火 → Context Compiler → Provider 判定。

design: Decision Engine の最小実装（H-1 初回実験）。
Agent 本体の Think-Decide-Execute とは独立して動き、判定結果は
Core が解釈して介入する。
"""

import logging
import os
import time
from typing import Any

from companion.decision.compiler import ContextCompiler
from companion.decision.models import (
    DecisionRequest,
    DecisionResult,
)
from companion.decision.provider import DecisionProvider, SameModelDecisionProvider

logger = logging.getLogger(__name__)


def decision_engine_enabled() -> bool:
    """Decision Engine 実験フラグ（DUCKFLOW_DECISION_ENGINE=1）を返す。

    Returns:
        フラグが有効なら True。
    """
    return os.environ.get("DUCKFLOW_DECISION_ENGINE", "").lower() in (
        "1",
        "true",
        "on",
    )


class DecisionEngine:
    """Pacemaker の発火に応じて Decision Provider を呼び出す。"""

    def __init__(self, llm: Any, provider: DecisionProvider | None = None) -> None:
        """Args:
        llm: SameModel provider 用の LLMClient（provider 未指定時に使用）。
        provider: 差し替え用 Decision Provider。None なら SameModel。
        """
        self.llm = llm
        self.compiler = ContextCompiler()
        self.provider: DecisionProvider = provider or SameModelDecisionProvider(llm)
        self.log: list[dict[str, Any]] = []

    async def check(
        self,
        request_type: str,
        *,
        task: str,
        state: Any,
        workspace_root: str | None = None,
    ) -> DecisionResult:
        """1つの判断要求を評価する。

        Provider 呼び出しが失敗した場合は安全側として continue を返す
        （判断層の故障でエージェントの通常動作を止めない）。

        Args:
            request_type: 判断の種別（"needs_clarification" 等）。
            task: 発火点となったユーザー要求本文。
            state: 現在の AgentState。
            workspace_root: workspace ルートパス（探索後発火で
                ファイル一覧を context に含めるために使用）。

        Returns:
            DecisionResult。
        """
        request = DecisionRequest(type=request_type, task=task)
        context = self.compiler.build(state, task, workspace_root=workspace_root)
        start = time.monotonic()
        error = ""
        try:
            result = await self.provider.decide(context, request)
        except Exception as e:
            logger.warning(f"Decision provider failed ({request_type}): {e}")
            result = DecisionResult(reason=f"provider error: {e}")
            error = str(e)
        entry = {
            "type": request_type,
            "action": result.action,
            "focus": result.focus,
            "reason": result.reason,
            "latency_ms": round((time.monotonic() - start) * 1000),
            "raw": result.raw,
        }
        if error:
            entry["error"] = error
        self.log.append(entry)
        logger.info(
            f"Decision Engine [{request_type}] -> {result.action}"
            + (f" (focus: {result.focus})" if result.focus else "")
        )
        return result


def build_clarification_note(result: DecisionResult) -> str:
    """ask_user 判定をエージェント向けの注入ノートに変換する。

    Agent はこのノートを受けて duck_call（または直接の質問文）で
    ユーザーに確認する。結果そのものの代行はしない — 聞くべきという
    判定だけを伝える。

    Args:
        result: action == "ask_user" の DecisionResult。

    Returns:
        会話履歴に注入するテキスト。
    """
    lines = [
        "[DECISION ENGINE] Interpretation check judged this request unresolved:",
        f"- Unresolved: {result.focus or 'the intended result is ambiguous'}",
    ]
    if result.reason:
        lines.append(f"- Reason: {result.reason}")
    lines += [
        "Before doing any work, ask the user a clarifying question about this",
        "(via ::duck_call / the duck_call tool, or a direct question ending",
        'with "?"). Do NOT guess the answer.',
    ]
    return "\n".join(lines)
