"""
Duck Pacemaker - エージェントの健康状態と実行状況を監視し、介入を行う
"""

from typing import List, Optional, Any, Dict
import json
import logging
import re
from companion.state.agent_state import (
    AgentState,
    Action,
    InterventionReason,
    MAX_HYPOTHESIS_ATTEMPTS,
)
from companion.config.config_loader import config
from companion.config.tier_profile import TierProfile

logger = logging.getLogger(__name__)

# Repeated-failure escalation thresholds.
# WARN: at the Nth identical failure the Correction Guide is escalated to a
#       "stop, change form" message instead of the standard per-error hint.
# BLOCK: a verbatim repeat — or a call carrying the same inspectable form
#        defect — of a call that already failed N times with a contract
#        (format/permission) error is refused BEFORE execution; resending
#        deterministic failures cannot succeed.
# CASCADE: N repeated failures of one signature feed ERROR_CASCADE even
#          when successes interleave and reset consecutive_errors.
REPEAT_WARN_THRESHOLD = 3
REPEAT_BLOCK_THRESHOLD = 3
REPEAT_CASCADE_THRESHOLD = 5

# Error kinds that fail deterministically regardless of workspace state.
# Only these are eligible for the pre-execution hard block. State-dependent
# failures (SEARCH mismatch, command exit codes, file-not-found) must never
# be blocked — rerunning after a fix is legitimate and may succeed.
_CONTRACT_ERROR_MARKERS = (
    "no find/replace details",
    "missing required",
    "unexpected param",
    "unknown tool",
    "invalid regex",
    "does not accept parameter",
    "outside workspace",
    "access denied",
)


def _is_contract_error(error_kind: str) -> bool:
    """Return whether an error kind is a deterministic contract failure.

    Contract errors (malformed call, wrong params, denied path) cannot
    succeed on a verbatim retry; state-dependent errors can.

    Args:
        error_kind: Normalized error-kind token from _error_kind.

    Returns:
        True when the error is inherent to the call form itself.
    """
    kind = error_kind.lower()
    return any(marker in kind for marker in _CONTRACT_ERROR_MARKERS)


def _call_has_same_defect(action: Action, error_kind: str) -> bool:
    """Return whether a pending call repeats the defect behind an error.

    Only defects inspectable from the call itself qualify — currently the
    edit_file empty-body pattern ("no find/replace details"), where the
    emitted call carries no edit body at all. Rotating the target file
    defeats verbatim-signature blocking, so the defect itself must match.

    Args:
        action: Action about to be executed.
        error_kind: Dominant prior error kind for this tool.

    Returns:
        True when the call carries the same deterministic defect.
    """
    if "no find/replace details" in error_kind:
        if action.parameters.get("find"):
            return False
        content = str(action.parameters.get("content") or "")
        return "SEARCH" not in content and "find:" not in content
    return False


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
        # Repeated-failure signature tracking. Unlike consecutive_errors
        # these survive interleaved successes — a success only clears the
        # counters of the tool that succeeded.
        #   _call_failures: "name|params" -> (count, last error kind)
        #   _kind_failures: (name, error kind) -> count
        self._call_failures: dict[str, tuple] = {}
        self._kind_failures: dict[tuple, int] = {}

    def calculate_max_loops(self, tier_profile: Optional[TierProfile] = None) -> int:
        """
        タスクの種類と実測バイタルに応じて最大ループ回数を計算する。
        申告バイタル（confidence/safety）は制御に使用しない（V-A2）。
        実測値（success_rate, progress）ベースで算出する。

        Args:
            tier_profile: 現在のモデルの TierProfile。渡された場合、
                `tier_profile.max_loops` が暴走許容量の上限（ceiling）になる
                （docs/agent_surface_redesign_design.md §5.2）。省略時は
                従来どおり 35 を上限とする（呼び出し側が tier を意識しない
                既存コード・テストとの後方互換）。
        """
        ceiling = tier_profile.max_loops if tier_profile is not None else 35

        # ベース値の決定
        if self.state.current_plan:
            current_step = self.state.current_plan.get_current_step()
            if current_step and current_step.tasks:
                base_loops = min(15 + len(current_step.tasks) // 2, ceiling)
            else:
                base_loops = min(20, ceiling)
        else:
            base_loops = min(10, ceiling)

        # 実測係数の計算（execution_history ベース）
        vitals_factor = self._calculate_measured_factor()

        # 最終計算
        calculated = int(base_loops * vitals_factor)
        final_loops = max(3, min(calculated, ceiling))

        logger.info(
            f"Pacemaker: max_loops={final_loops} "
            f"(base={base_loops}, ceiling={ceiling}, measured_factor={vitals_factor:.2f})"
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
            self._record_failure_signature(action, summary)
            logger.debug("Error recorded (consecutive=%d)", self.consecutive_errors)
        else:
            self.consecutive_errors = 0
            self._clear_failure_signatures(action.name)

    def _call_signature(self, action: Action) -> str:
        """Signature identifying a verbatim-repeat call (tool + params).

        Args:
            action: The action being checked.

        Returns:
            "name|normalized-params" string; identical when the model
            resends literally the same call.
        """
        params = {k: str(v).strip()[:200] for k, v in (action.parameters or {}).items()}
        return f"{action.name}|{self._normalize_params(params)}"

    @staticmethod
    def _error_kind(result_summary: str) -> str:
        """Extract a stable error-category token from a failure result.

        Args:
            result_summary: The recorded error message
                ("Action 'x' failed: Reason: ...").

        Returns:
            Lowercased kind token — the "Reason:" line when present,
            otherwise the normalized payload prefix.
        """
        match = re.search(r"Reason:\s*([^\n]+)", result_summary)
        if match:
            return " ".join(match.group(1).split()).lower()[:100]
        text = result_summary.split("failed:", 1)[-1]
        return " ".join(text.split()).lower()[:100]

    def _record_failure_signature(self, action: Action, summary: str) -> None:
        """Count this failure under its call and error-kind signatures.

        Args:
            action: The failed action.
            summary: Recorded result summary containing the error text.
        """
        kind = self._error_kind(summary)
        sig = self._call_signature(action)
        count, _ = self._call_failures.get(sig, (0, ""))
        self._call_failures[sig] = (count + 1, kind)
        kind_key = (action.name, kind)
        self._kind_failures[kind_key] = self._kind_failures.get(kind_key, 0) + 1

    def _clear_failure_signatures(self, tool_name: str) -> None:
        """Drop failure counters for a tool that just succeeded.

        Per-tool clearing preserves other tools' counts — a successful
        read_file between failed edits must not forgive the edit errors.

        Args:
            tool_name: Name of the tool whose counters are reset.
        """
        self._call_failures = {
            sig: entry
            for sig, entry in self._call_failures.items()
            if not sig.startswith(f"{tool_name}|")
        }
        self._kind_failures = {
            key: count
            for key, count in self._kind_failures.items()
            if key[0] != tool_name
        }

    def repeated_call_count(self, action: Action) -> int:
        """Failures recorded for this exact call (tool + same params).

        Args:
            action: Action to check against recorded failures.

        Returns:
            Number of previous identical-call failures (0 if none).
        """
        return self._call_failures.get(self._call_signature(action), (0, ""))[0]

    def repeated_kind_count(self, action: Action) -> int:
        """Highest failure count among this tool's error kinds.

        Args:
            action: Action to check against recorded failures.

        Returns:
            Max count over (name, kind) entries for this tool — catches
            "same error, different args" misuse patterns.
        """
        counts = [
            count
            for (name, _kind), count in self._kind_failures.items()
            if name == action.name
        ]
        return max(counts, default=0)

    def repeat_escalation_count(self, action: Action) -> int:
        """Repeat count driving Correction Guide escalation, or 0.

        Args:
            action: Action that just failed.

        Returns:
            The larger of call-signature and kind-signature counts when
            it reaches REPEAT_WARN_THRESHOLD, otherwise 0.
        """
        count = max(self.repeated_call_count(action), self.repeated_kind_count(action))
        return count if count >= REPEAT_WARN_THRESHOLD else 0

    def check_repeat_block(self, action: Action) -> str | None:
        """Refuse a verbatim repeat of a deterministically-doomed call.

        Only contract errors (format/params/permission) are blocked — an
        identical call can never succeed. State-dependent failures
        (SEARCH mismatch, command exit codes) are never blocked because
        the workspace may have changed between attempts.

        Args:
            action: Action about to be executed.

        Returns:
            A refusal message when the call should be skipped, else None.
        """
        count, kind = self._call_failures.get(self._call_signature(action), (0, ""))
        if count < REPEAT_BLOCK_THRESHOLD or not _is_contract_error(kind):
            # The verbatim signature is below threshold — but a call that
            # still carries the same *form defect* as this tool's dominant
            # repeated contract failure is just as doomed. Rotating target
            # filenames defeats verbatim matching (observed: GLM sent the
            # same empty-body edit_file to different files).
            dominant = self._dominant_kind_failure(action.name)
            if (
                dominant is None
                or dominant[1] < REPEAT_BLOCK_THRESHOLD
                or not _is_contract_error(dominant[0])
                or not _call_has_same_defect(action, dominant[0])
            ):
                return None
            count, kind = dominant[1], dominant[0]
        target = str(
            action.parameters.get("path") or action.parameters.get("command") or ""
        )
        return (
            f"[BLOCKED] '{action.name}' was refused: the identical call "
            f"already failed {count} times with the same error — resending "
            f"it cannot succeed. Recovery: (1) ::read_file @{target or 'path'} "
            "to re-confirm the current state, (2) emit a DIFFERENT call form "
            "— for edit_file include a <<< >>> body with <<<<<<< SEARCH / "
            "======= / >>>>>>> REPLACE markers, or use ::write_file to "
            "rewrite the file."
        )

    def _dominant_kind_failure(self, tool_name: str) -> tuple[str, int] | None:
        """Return the most-failed error kind recorded for a tool.

        Args:
            tool_name: Tool whose kind counters to scan.

        Returns:
            (kind, count) of the highest-count entry, or None when the
            tool has no recorded failures.
        """
        entries = [
            (kind, count)
            for (name, kind), count in self._kind_failures.items()
            if name == tool_name
        ]
        return max(entries, key=lambda kv: kv[1]) if entries else None

    def _max_repeated_failures(self) -> int:
        """Largest repeated-failure count across both signature levels.

        Returns:
            Max of verbatim-call counts and tool+kind counts.
        """
        call_max = max((c for c, _ in self._call_failures.values()), default=0)
        kind_max = max(self._kind_failures.values(), default=0)
        return max(call_max, kind_max)

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

    @staticmethod
    def _normalize_params(parameters: Dict[str, Any]) -> str:
        """パラメータ辞書をキー順に依存しない形で正規化する。

        Args:
            parameters: Action.parameters の辞書。

        Returns:
            キー順序の揺れを吸収した比較用文字列。
        """
        try:
            return json.dumps(parameters, sort_keys=True, default=str)
        except TypeError:
            return str(sorted(parameters.items(), key=lambda kv: kv[0]))

    def _detect_stagnation(self) -> bool:
        """停滞検知：同じアクション・同じパラメータ・同じ結果の繰り返し。

        読み取り系ツール（read_file等）も対象に含める。同じファイルを
        同じ引数で読み続けて同じ内容しか返らないなら、それは調査の進展
        ではなく停滞であるため。パラメータが異なる場合（別ファイルを読む
        等）は探索として扱い、停滞とはみなさない。
        """
        if len(self.execution_history) < 4:
            return False

        recent = self.execution_history[-4:]
        actions = [item["action"] for item in recent]
        action_names = [a.name for a in actions]

        if len(set(action_names)) != 1:
            return False

        action_name = action_names[0]
        # 提案ツール（propose_plan）は内容が毎回異なりうるため除外
        if action_name == "propose_plan":
            return False

        normalized_params = [self._normalize_params(a.parameters) for a in actions]
        results = [item["result_summary"] for item in recent]

        if len(set(normalized_params)) == 1 and len(set(results)) == 1:
            logger.warning(
                f"Stagnation: '{action_name}' repeated with identical params and result"
            )
            return True

        return False

    def _detect_error_cascade(self) -> bool:
        """エラー連鎖検知"""
        # 連続3回エラー
        if self.consecutive_errors >= 3:
            return True

        # 同一シグネチャの連発 — 成功を挟んで consecutive_errors が
        # リセットされても検出できる（Correction Guideが無視されている）。
        # 閾値は warn/block より高く、ガイド付き回復に先に機会を与える。
        if self._max_repeated_failures() >= REPEAT_CASCADE_THRESHOLD:
            logger.warning("Error cascade: repeated identical failure signature")
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
        self._call_failures = {}
        self._kind_failures = {}
        logger.debug("Pacemaker reset")
