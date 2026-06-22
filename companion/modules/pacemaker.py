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
        タスクの種類と実測バイタルに応じて最大ループ回数を計算する。
        申告バイタル（confidence/safety）は制御に使用しない（V-A2）。
        実測値（success_rate, progress）ベースで算出する。
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

        # 実測係数の計算（execution_history ベース）
        vitals_factor = self._calculate_measured_factor()

        # 最終計算
        calculated = int(base_loops * vitals_factor)
        final_loops = max(3, min(calculated, 35))

        logger.info(
            f"Pacemaker: max_loops={final_loops} "
            f"(base={base_loops}, measured_factor={vitals_factor:.2f})"
        )

        return final_loops

    def _calculate_measured_factor(self) -> float:
        """
        execution_history から実測ファクターを算出する。
        停滞がなければループ上限を緩める（反復は悪ではない原則）。
        """
        if not self.execution_history:
            return 1.0  # 履歴なしは中立

        recent = self.execution_history[-10:]
        total = len(recent)
        errors = sum(1 for item in recent if item["is_error"])
        success_rate = (total - errors) / total

        # 停滞検知: 同じ結果が繰り返されている場合は係数を下げる
        is_stagnating = self._detect_stagnation()

        if is_stagnating:
            return 0.7
        elif success_rate >= 0.8:
            return 1.2  # 順調なら延長
        elif success_rate < 0.3:
            return 0.7  # エラー多い場合は短縮
        else:
            return 1.0

    def update_vitals(self, action: Action, result: Any, is_error: bool):
        """
        アクション実行結果に基づいて履歴を記録する。
        申告バイタルの更新は行わない（V-A2: decay廃止、実測ベース化）。
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
            self.consecutive_errors += 1
            logger.debug("Error recorded (consecutive=%d)", self.consecutive_errors)
        else:
            self.consecutive_errors = 0

    def check_health(self) -> Optional[InterventionReason]:
        """健康状態を診断し、介入が必要ならその理由を返す。
        V-A2: 申告バイタル（safety/confidence/focus）由来の監視を廃止。
        実測値（error_rate, stagnation, hypothesis_attempts）のみで判定する。
        """
        # 1. ループ回数超過
        if self.loop_count >= self.max_loops:
            return InterventionReason(
                type="LOOP_EXHAUSTED",
                message=f"最大試行回数（{self.max_loops}回）に到達しました。",
                severity="high",
            )

        # 2. Investigationモードの仮説失敗 (Stuck Protocol)
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

        # 3. エラー連鎖
        if self._detect_error_cascade():
            return InterventionReason(
                type="ERROR_CASCADE",
                message="エラーが頻発しています。方針を見直すべきです。",
                severity="high",
            )

        # 4. スタック検知（停滞）
        if self._detect_stagnation():
            return InterventionReason(
                type="STAGNATION",
                message="同じ操作または結果が繰り返されており、進捗がありません。",
                severity="medium",
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

        # 実測統計
        if self.execution_history:
            recent = self.execution_history[-10:]
            total = len(recent)
            errors = sum(1 for item in recent if item["is_error"])
            success_rate = (total - errors) / total
            lines.append(
                f"\n📊 実測: success_rate={success_rate:.0%} "
                f"({total - errors}/{total}) | Loop: {self.loop_count}/{self.max_loops}"
            )

        return "\n".join(lines)

    def intervene(self, reason: InterventionReason, summary: str = "") -> Action:
        """介入アクションを生成する。"""
        logger.info(f"Pacemaker intervention: {reason.type} - {reason.message}")

        vitals_info = (
            f"\n\n📊 ループ: {self.loop_count}/{self.max_loops}"
            f" | 連続エラー: {self.consecutive_errors}"
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
        logger.debug("Pacemaker reset")
