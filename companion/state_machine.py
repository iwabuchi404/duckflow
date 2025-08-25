from enum import Enum
from typing import Dict, List, Callable, Any, Optional
import logging
from datetime import datetime

# 状態管理のコアとなるStepとStatusをインポート
from .state.enums import Step, Status

class TransitionController:
    """許可された状態遷移を管理する"""
    def __init__(self):
        self.allowed_transitions: Dict[Step, List[Step]] = {
            Step.IDLE: [Step.THINKING, Step.PLANNING, Step.EXECUTION, Step.REVIEW],
            Step.THINKING: [Step.PLANNING, Step.EXECUTION, Step.REVIEW, Step.AWAITING_USER_INPUT],
            Step.PLANNING: [Step.EXECUTION, Step.REVIEW, Step.AWAITING_APPROVAL],
            Step.EXECUTION: [Step.REVIEW, Step.AWAITING_APPROVAL, Step.COMPLETED, Step.IDLE],
            Step.REVIEW: [Step.PLANNING, Step.EXECUTION, Step.COMPLETED, Step.IDLE],
            Step.AWAITING_APPROVAL: [Step.EXECUTION, Step.PLANNING],
            Step.AWAITING_USER_INPUT: [Step.THINKING, Step.PLANNING],
            Step.COMPLETED: [Step.IDLE],
        }
        self.error_recovery_step = Step.IDLE

    def is_transition_allowed(self, from_step: Step, to_step: Step) -> bool:
        """指定された遷移が許可されているかを確認する"""
        allowed = to_step in self.allowed_transitions.get(from_step, [])
        if not allowed:
            self.logger.debug(f"遷移制御: {from_step.value} -> {to_step.value} は許可されていません")
        return allowed

class StateMachine:
    """
    StepとStatusに基づいた状態管理マシン。
    v3設計に基づき、コールバック機能と許可遷移表による制御を実装。
    """
    def __init__(self, initial_step: Step = Step.IDLE, initial_status: Status = Status.PENDING):
        self.logger = logging.getLogger(__name__)
        self.current_step = initial_step
        self.current_status = initial_status
        self.history: List[Dict[str, Any]] = []
        self.transition_controller = TransitionController()
        self.callbacks: List[Callable[[Step, Status, str], None]] = []
        self._log_state_change("initialization")

    def add_state_change_callback(self, callback: Callable[[Step, Status, str], None]):
        """状態変更時に呼び出されるコールバック関数を登録する"""
        if callback not in self.callbacks:
            self.callbacks.append(callback)
            self.logger.info(f"コールバックを登録しました: {callback.__name__}")

    def _notify_callbacks(self, trigger: str):
        """登録されたすべてのコールバックに状態変更を通知する"""
        if not self.callbacks:
            self.logger.debug("通知するコールバックがありません。")
            return
            
        self.logger.debug(f"コールバックを通知中 (トリガー: {trigger})...")
        for callback in self.callbacks:
            try:
                callback(self.current_step, self.current_status, trigger)
            except Exception as e:
                self.logger.error(f"コールバック実行中にエラーが発生しました ({callback.__name__}): {e}", exc_info=True)

    def set_state(self, new_step: Optional[Step] = None, new_status: Optional[Status] = None, trigger: Optional[str] = "unknown") -> bool:
        """
        状態を安全に設定する。
        Stepの遷移は許可されている場合のみ実行される。
        """
        state_changed = False
        
        if new_step is not None and new_step != self.current_step:
            if self.transition_controller.is_transition_allowed(self.current_step, new_step):
                self.current_step = new_step
                state_changed = True
                self.logger.info(f"Stepが {self.current_step.value} に遷移しました (トリガー: {trigger})")
            else:
                self.logger.warning(f"許可されていないStep遷移が試みられました: {self.current_step.value} -> {new_step.value} (トリガー: {trigger})")
                # エラー状態からの復旧を試みる
                if self.current_status == Status.ERROR:
                    self.logger.info(f"エラー状態からの復旧を試みます: {self.current_step.value} -> {new_step.value}")
                    self.current_step = new_step
                    self.current_status = Status.PENDING
                    state_changed = True
                else:
                    self.current_status = Status.ERROR
                    self._log_state_change(f"invalid_transition_attempt_by_{trigger}")
                    self._notify_callbacks(f"invalid_transition_by_{trigger}")
                    return False  # 遷移失敗

        if new_status is not None and new_status != self.current_status:
            self.current_status = new_status
            state_changed = True
            self.logger.info(f"Statusが {self.current_status.value} に変更されました (トリガー: {trigger})")

        if state_changed:
            self._log_state_change(trigger)
            self._notify_callbacks(trigger)
        
        return True  # 遷移成功または状態変更あり

    def _log_state_change(self, trigger: str):
        """状態変更を履歴に記録する"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "step": self.current_step.value,
            "status": self.current_status.value,
            "trigger": trigger
        }
        self.history.append(log_entry)
        self.logger.debug(f"状態変更を記録: {log_entry}")

    def get_current_state(self) -> Dict[str, str]:
        """現在の状態を辞書形式で返す"""
        return {
            "step": self.current_step.value,
            "status": self.current_status.value
        }

    def handle_error(self, error_message: str, trigger: str = "error_handler"):
        """エラー状態を処理し、復旧を試みる"""
        self.logger.error(f"エラー発生: {error_message} (トリガー: {trigger})")
        self.current_status = Status.ERROR
        
        recovery_step = self.transition_controller.error_recovery_step
        if self.transition_controller.is_transition_allowed(self.current_step, recovery_step):
            self.current_step = recovery_step
            self.logger.info(f"エラーから復旧し、Stepを {recovery_step.value} に遷移しました")
        else:
            self.logger.critical(f"エラーからの復旧に失敗しました。現在のStep: {self.current_step.value}")
            self.current_step = Step.IDLE

        self._log_state_change(f"error_recovery_by_{trigger}")
        self._notify_callbacks(f"error_recovery_by_{trigger}")