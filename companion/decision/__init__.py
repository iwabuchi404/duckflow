"""Decision Engine（H-1）— Agent本体とは独立した判断レイヤー。

Pacemaker が発火点を検出し、Context Compiler が判断用コンテキストを
構築し、Decision Provider が ASK/CONTINUE 等の判定を返す。
初回実験では Provider としてエージェントと同じモデルを binary 判定に
使う SameModelDecisionProvider を用いる（OpenJev 方式は後続実験）。
"""

from companion.decision.engine import DecisionEngine, decision_engine_enabled
from companion.decision.models import (
    DECISION_NEEDS_CLARIFICATION,
    DecisionContext,
    DecisionRequest,
    DecisionResult,
)

__all__ = [
    "DECISION_NEEDS_CLARIFICATION",
    "DecisionContext",
    "DecisionEngine",
    "DecisionRequest",
    "DecisionResult",
    "decision_engine_enabled",
]
