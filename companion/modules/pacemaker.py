"""
Duck Pacemaker - エージェントの健康状態と実行状況を監視し、介入を行う
"""

from typing import List, Optional, Any, Dict
import logging
from companion.state.agent_state import (
    AgentState,
    Action,
    InterventionReason,
    MAX_HYPOTHESIS_ATTEMPTS,
)
from companion.config.config_loader import config

logger = logging.getLogger(__name__)


class DuckPacemaker:
    """
    エージェントの健康状態と実行状況を監視し、介入を行う自律調整システム。

    主な機能：
    - ループ回数の動的計算と監視
    - バイタル（Mood, Focus, Stamina）の更新と監視
    - 異常検知（ループ枯渇、バイタル枯渇、エラー連鎖、停滞）
    - 介入アクションの生成
    """

    def __init__(self, state: AgentState):
        self.state = state
        self.loop_count = 0
        self.max_loops = config.get("agent.max_loops", 10)
        self.execution_history: List[Dict[str, Any]] = (
            []
        )  # {action, result_summary, is_error}
        self.consecutive_errors = 0

    def calculate_max_loops(self) -> int:
        """
        タスクの種類とバイタルに応じて最大ループ回数を計算する。
        Sym-Ops v3.1: confidence/safety/memory/focus を使用。
        """
        # ベース値の決定
        if self.state.current_plan:
            current_step = self.state.current_plan.get_current_step()
            if current_step and current_step.tasks:
                base_loops = min(15 + len(current_step.tasks) // 2, 35)
            else:
                base_loops = 20
        else:
            base_loops = 10

        # バイタル係数の計算 (v3.1: c/s/m/f)
        vitals = self.state.vitals
        vitals_score = (
            vitals.confidence * 0.3
            + vitals.focus * 0.4
            + vitals.safety * 0.2
            + vitals.memory * 0.1
        )

        if vitals_score < 0.4:
            vitals_factor = 0.7
        elif vitals_score > 0.8:
            vitals_factor = 1.2
        else:
            vitals_factor = 1.0

        # 最終計算
        calculated = int(base_loops * vitals_factor)
        final_loops = max(3, min(calculated, 35))

        logger.info(
            f"Pacemaker: max_loops={final_loops} "
            f"(base={base_loops}, vitals_factor={vitals_factor:.2f})"
        )

        return final_loops

    def update_vitals(self, action: Action, result: Any, is_error: bool):
        """
        アクション実行結果に基づいてバイタルを更新し、履歴を記録する。
        Sym-Ops v3.1: safety / confidence を使用。
        """
        # 履歴の記録
        result_str = str(result)
        summary = result_str[:200] + "..." if len(result_str) > 200 else result_str

        self.execution_history.append(
            {"action": action, "result_summary": summary, "is_error": is_error}
        )
        if len(self.execution_history) > 20:
            self.execution_history = self.execution_history[-20:]

        if is_error:
            # エラー時は safety と focus が低下
            self.state.vitals.safety = max(0.0, self.state.vitals.safety - 0.1)
            self.state.vitals.focus = max(0.0, self.state.vitals.focus - 0.05)
            self.consecutive_errors += 1
            logger.debug("Vitals decreased (error)")
        else:
            # 成功時は緩やかに回復
            self.state.vitals.safety = min(1.0, self.state.vitals.safety + 0.02)
            self.consecutive_errors = 0

        # 通常のdecay
        self.state.vitals.decay(0.03)

    def check_health(self) -> Optional[InterventionReason]:
        """健康状態を診断し、介入が必要ならその理由を返す。
        Sym-Ops v3.1: safety/confidence/focus を監視、Investigationモードの仮説失敗も検知。
        """
        vitals = self.state.vitals

        # 1. Safety枯渇（最優先）
        if vitals.safety < 0.1:
            return InterventionReason(
                type="SAFETY_DEPLETED",
                message="安全スコアが限界です。これ以上の作業は危険です。",
                severity="critical",
            )

        # 2. ループ回数超過
        if self.loop_count >= self.max_loops:
            return InterventionReason(
                type="LOOP_EXHAUSTED",
                message=f"最大試行回数（{self.max_loops}回）に到達しました。",
                severity="high",
            )

        # 3. Investigationモードの仮説失敗 (Stuck Protocol)
        if (
            self.state.investigation_state is not None
            and self.state.investigation_state.hypothesis_attempts
            >= MAX_HYPOTHESIS_ATTEMPTS
        ):
            return InterventionReason(
                type="INVESTIGATION_STUCK",
                message=(
                    f"仮説の検証に{self.state.investigation_state.hypothesis_attempts}回失敗しました。"
                    " 新たな視点が必要です。"
                ),
                severity="high",
            )

        # 4. エラー連鎖
        if self._detect_error_cascade():
            return InterventionReason(
                type="ERROR_CASCADE",
                message="エラーが頻発しています。方針を見直すべきです。",
                severity="high",
            )

        # 5. スタック検知（停滞）
        if self._detect_stagnation():
            return InterventionReason(
                type="STAGNATION",
                message="同じ操作または結果が繰り返されており、進捗がありません。",
                severity="medium",
            )

        # 6. Focus低下
        if vitals.focus < 0.3:
            return InterventionReason(
                type="FOCUS_LOST",
                message="思考が停滞しています。別のアプローチが必要かもしれません。",
                severity="medium",
            )

        # 7. Confidence低下
        if vitals.confidence < 0.4:
            return InterventionReason(
                type="CONFIDENCE_LOW",
                message="現在の計画に自信が持てていません。",
                severity="low",
            )

        return None

    def _detect_stagnation(self) -> bool:
        """停滞検知：同じアクションや結果の繰り返し"""
        if len(self.execution_history) < 4:
            return False

        recent = self.execution_history[-4:]

        # 1. 完全一致アクションの繰り返し
        actions = [item["action"] for item in recent]
        action_names = [a.name for a in actions]

        if len(set(action_names)) == 1:
            # 提案ツール（propose_plan）は除外（内容が異なるため）
            if action_names[0] != "propose_plan":
                # パラメータもチェック
                # Action.parameters は Dict なので文字列化して比較
                params = [str(a.parameters) for a in actions]
                if len(set(params)) == 1:
                    logger.warning(
                        "Stagnation: Same action and params repeated 3 times"
                    )
                    return True

        # 2. 同じ結果の繰り返し
        results = [item["result_summary"] for item in recent]
        if len(set(results)) == 1:
            logger.warning("Stagnation: Same result repeated 3 times")
            return True

        return False

    def _detect_error_cascade(self) -> bool:
        """エラー連鎖検知"""
        # 連続3回エラー
        if self.consecutive_errors >= 3:
            return True

        # 直近10回中5回以上エラー（50%以上のエラー率）
        if len(self.execution_history) >= 10:
            recent_errors = sum(
                1 for item in self.execution_history[-10:] if item["is_error"]
            )
            if recent_errors >= 5:
                logger.warning(
                    f"Error cascade: {recent_errors}/10 recent actions failed"
                )
                return True

        return False

    def build_intervention_summary(self) -> str:
        """
        直近の実行履歴を人間が読める形式で組み立てる。
        Pacemaker介入時にユーザーとLLMに状況を伝えるために使用する。

        Returns:
            フォーマット済みの実行履歴サマリー文字列
        """
        lines = []

        # 直近の実行履歴（最大5件）
        recent = self.execution_history[-5:] if self.execution_history else []
        if recent:
            lines.append(f"直近の実行履歴 ({len(recent)}件):")
            for i, item in enumerate(recent, 1):
                action = item["action"]
                is_error = item["is_error"]
                status = "❌" if is_error else "✅"
                summary = item["result_summary"]
                # 結果を短く切り詰め
                if len(summary) > 80:
                    summary = summary[:77] + "..."

                # アクション名とパラメータ
                params_str = ""
                if hasattr(action, "parameters") and action.parameters:
                    param_parts = [
                        f"{k}={v}"
                        for k, v in action.parameters.items()
                        if k not in ("content",) and len(str(v)) < 50
                    ]
                    if param_parts:
                        params_str = f' ({", ".join(param_parts)})'

                lines.append(f'  {i}. {status} {action.name}{params_str} → "{summary}"')
        else:
            lines.append("直近の実行履歴: なし")

        # 検知パターン
        if self.consecutive_errors >= 3:
            lines.append(
                f"\n⚠️ 検知パターン: 同一エラーが{self.consecutive_errors}回連続"
            )
        elif self._detect_stagnation():
            lines.append("\n⚠️ 検知パターン: 同じ操作が繰り返されている（停滞）")

        # バイタル
        v = self.state.vitals
        lines.append(
            f"\n📊 バイタル: C={v.confidence:.2f} S={v.safety:.2f} "
            f"M={v.memory:.2f} F={v.focus:.2f} | Loop: {self.loop_count}/{self.max_loops}"
        )

        return "\n".join(lines)

    def intervene(self, reason: InterventionReason, summary: str = "") -> Action:
        """介入アクションを生成する。"""
        logger.info(f"Pacemaker intervention: {reason.type} - {reason.message}")

        vitals_info = (
            f"\n\n📊 現在のバイタル:\n"
            f"  Confidence: {self.state.vitals.confidence:.2f}\n"
            f"  Safety: {self.state.vitals.safety:.2f}\n"
            f"  Memory: {self.state.vitals.memory:.2f}\n"
            f"  Focus: {self.state.vitals.focus:.2f}\n"
            f"  ループ: {self.loop_count}/{self.max_loops}"
        )

        summary_section = f"\n\n📋 {summary}" if summary else ""

        full_message = (
            f"⚠️  Pacemaker介入 ({reason.severity})\n\n"
            f"理由: {reason.type}\n"
            f"{reason.message}"
            f"{vitals_info}"
            f"{summary_section}\n\n"
            f"どうしますか？"
        )

        return Action(
            name="duck_call",
            parameters={"message": full_message},
            thought=f"Pacemakerの介入により、ユーザーに相談します（理由: {reason.type}）",
        )

    def reset(self):
        """セッション終了時にカウンターをリセット"""
        self.loop_count = 0
        self.consecutive_errors = 0
        self.execution_history = []
        self.state.vitals.recover(0.2)
        logger.debug("Pacemaker reset")
