#!/usr/bin/env python3
"""
状態遷移一元管理ステートマシン

EnhancedDualLoopSystem内で、AgentStateのStepとStatusを一元的に管理する
明確なステートマシンを実装。LLMの応答やタスクの結果に応じて、
必ずこのステートマシンを通してのみ状態が変更される。

設計ドキュメント4.4節の要求に基づく状態同期システムを実装。
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from companion.state.enums import Step, Status


@dataclass
class StateTransition:
    """状態遷移の定義"""
    from_step: Step
    from_status: Status
    to_step: Step
    to_status: Status
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StateHistory:
    """状態変更履歴"""
    step: Step
    status: Status
    timestamp: datetime
    trigger: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateSyncInfo:
    """状態同期の情報"""
    step: Step
    status: Status
    trigger: str
    timestamp: datetime
    sync_success: bool
    error_message: Optional[str] = None


class StateMachine:
    """状態遷移一元管理ステートマシン（状態同期強化版）"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        
        self.current_step = Step.IDLE
        self.current_status = Status.PENDING
        
        self.state_history: List[StateHistory] = []
        self.sync_history: List[StateSyncInfo] = []
        self.max_history = 100
        
        self.transitions: List[StateTransition] = self._initialize_transitions()
        
        # 状態変更コールバック（設計ドキュメント4.4.2の要求）
        self.state_change_callbacks: List[Callable[[Step, Status, str], None]] = []
        
        # 状態同期コールバック（新規追加）
        self.state_sync_callbacks: List[Callable[[StateSyncInfo], None]] = []
        
        # 状態整合性チェックフラグ
        self.enable_integrity_check = True
        
        self._record_state_change(Step.IDLE, Status.PENDING, "初期化")
        
        self.logger.info("ステートマシン初期化完了（状態同期強化版）")
    
    def _initialize_transitions(self) -> List[StateTransition]:
        """状態遷移ルールを初期化"""
        return [
            StateTransition(from_step=Step.IDLE, from_status=Status.PENDING, to_step=Step.PLANNING, to_status=Status.IN_PROGRESS, description="ユーザー要求受信による計画立案開始"),
            StateTransition(from_step=Step.PLANNING, from_status=Status.IN_PROGRESS, to_step=Step.PLANNING, to_status=Status.SUCCESS, description="計画立案完了"),
            StateTransition(from_step=Step.PLANNING, from_status=Status.SUCCESS, to_step=Step.EXECUTION, to_status=Status.IN_PROGRESS, description="計画完了による実行開始"),
            StateTransition(from_step=Step.PLANNING, from_status=Status.ERROR, to_step=Step.ERROR, to_status=Status.ERROR, description="計画立案失敗によるエラー状態"),
            StateTransition(from_step=Step.EXECUTION, from_status=Status.IN_PROGRESS, to_step=Step.EXECUTION, to_status=Status.SUCCESS, description="実行完了"),
            StateTransition(from_step=Step.EXECUTION, from_status=Status.SUCCESS, to_step=Step.REVIEW, to_status=Status.IN_PROGRESS, description="実行完了によるレビュー開始"),
            StateTransition(from_step=Step.EXECUTION, from_status=Status.ERROR, to_step=Step.ERROR, to_status=Status.ERROR, description="実行失敗によるエラー状態"),
            StateTransition(from_step=Step.REVIEW, from_status=Status.IN_PROGRESS, to_step=Step.REVIEW, to_status=Status.SUCCESS, description="レビュー完了"),
            StateTransition(from_step=Step.REVIEW, from_status=Status.SUCCESS, to_step=Step.COMPLETED, to_status=Status.SUCCESS, description="レビュー完了によるタスク完了"),
            StateTransition(from_step=Step.REVIEW, from_status=Status.ERROR, to_step=Step.EXECUTION, to_status=Status.IN_PROGRESS, description="レビュー失敗による再実行"),
            StateTransition(from_step=Step.ERROR, from_status=Status.ERROR, to_step=Step.IDLE, to_status=Status.PENDING, description="エラー状態からの復帰"),
            StateTransition(from_step=Step.COMPLETED, from_status=Status.SUCCESS, to_step=Step.IDLE, to_status=Status.PENDING, description="完了状態からのリセット"),
            StateTransition(from_step=Step.PLANNING, from_status=Status.IN_PROGRESS, to_step=Step.IDLE, to_status=Status.CANCELLED, description="計画立案のキャンセル"),
            StateTransition(from_step=Step.EXECUTION, from_status=Status.IN_PROGRESS, to_step=Step.IDLE, to_status=Status.CANCELLED, description="実行のキャンセル"),
            StateTransition(from_step=Step.REVIEW, from_status=Status.IN_PROGRESS, to_step=Step.IDLE, to_status=Status.CANCELLED, description="レビューのキャンセル"),
        ]
    
    def can_transition_to(self, target_step: Step, target_status: Status, context: Optional[Dict[str, Any]] = None) -> bool:
        """指定された状態への遷移が可能かチェック"""
        for transition in self.transitions:
            if (transition.from_step == self.current_step and
                transition.from_status == self.current_status and
                transition.to_step == target_step and
                transition.to_status == target_status):
                
                if transition.condition and not transition.condition(context or {}):
                    return False
                return True
        return False
    
    def transition_to(self, target_step: Step, target_status: Status, trigger: str = "", context: Optional[Dict[str, Any]] = None) -> bool:
        """状態遷移を実行（状態同期強化版）"""
        if self.current_step == target_step and self.current_status == target_status:
            return True

        if self.can_transition_to(target_step, target_status, context):
            previous_step = self.current_step
            previous_status = self.current_status
            
            # 状態整合性チェック（設計ドキュメント4.4.2の要求）
            if self.enable_integrity_check:
                if not self._validate_state_integrity(target_step, target_status):
                    self.logger.error(f"状態整合性チェック失敗: {target_step.value}.{target_status.value}")
                    return False
            
            # 状態変更
            self.current_step = target_step
            self.current_status = target_status
            
            # 履歴記録
            self._record_state_change(target_step, target_status, trigger, context)
            
            # コールバック通知（設計ドキュメント4.4.3の要求）
            self._notify_state_change_callbacks(previous_step, previous_status, target_step, target_status, trigger)
            
            # 状態同期の記録
            self._record_sync_info(target_step, target_status, trigger, True)
            
            self.logger.info(f"状態遷移成功: {previous_step.value}.{previous_status.value} → {target_step.value}.{target_status.value} (トリガー: {trigger})")
            return True
        else:
            self.logger.warning(f"状態遷移失敗: {self.current_step.value}.{self.current_status.value} → {target_step.value}.{target_status.value}")
            # 失敗時の同期情報記録
            self._record_sync_info(target_step, target_status, trigger, False, f"遷移ルール違反")
            return False

    def _validate_state_integrity(self, target_step: Step, target_status: Status) -> bool:
        """状態整合性チェック（設計ドキュメント4.4.2の要求）"""
        try:
            # 基本的な整合性チェック
            if target_step == Step.ERROR and target_status != Status.ERROR:
                return False
            
            if target_step == Step.COMPLETED and target_status != Status.SUCCESS:
                return False
            
            # 状態の論理的整合性チェック
            if target_step == Step.IDLE and target_status not in [Status.PENDING, Status.CANCELLED]:
                return False
            
            return True
        except Exception as e:
            self.logger.error(f"状態整合性チェックエラー: {e}")
            return False

    def _record_state_change(self, step: Step, status: Status, trigger: str, context: Optional[Dict[str, Any]] = None):
        """状態変更の履歴を記録"""
        history = StateHistory(step=step, status=status, timestamp=datetime.now(), trigger=trigger, metadata=context or {})
        self.state_history.append(history)
        if len(self.state_history) > self.max_history:
            self.state_history = self.state_history[-self.max_history:]

    def _record_sync_info(self, step: Step, status: Status, trigger: str, success: bool, error_message: Optional[str] = None):
        """状態同期情報を記録（設計ドキュメント4.4.2の要求）"""
        sync_info = StateSyncInfo(
            step=step,
            status=status,
            trigger=trigger,
            timestamp=datetime.now(),
            sync_success=success,
            error_message=error_message
        )
        self.sync_history.append(sync_info)
        if len(self.sync_history) > self.max_history:
            self.sync_history = self.sync_history[-self.max_history:]

    def _notify_state_change_callbacks(self, from_step: Step, from_status: Status, to_step: Step, to_status: Status, trigger: str):
        """状態変更コールバックを通知（設計ドキュメント4.4.3の要求）"""
        for callback in self.state_change_callbacks:
            try:
                # 設計ドキュメント4.4.3の実装イメージに従ったコールバック呼び出し
                callback(to_step, to_status, trigger)
            except Exception as e:
                self.logger.error(f"状態変更コールバックエラー: {e}")
                # エラー時の同期情報記録
                self._record_sync_info(to_step, to_status, trigger, False, f"コールバックエラー: {e}")

    def add_state_change_callback(self, callback: Callable[[Step, Status, str], None]):
        """状態変更コールバックを追加（設計ドキュメント4.4.3の要求）"""
        if callback not in self.state_change_callbacks:
            self.state_change_callbacks.append(callback)
            self.logger.debug(f"状態変更コールバック追加: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")

    def remove_state_change_callback(self, callback: Callable[[Step, Status, str], None]):
        """状態変更コールバックを削除"""
        if callback in self.state_change_callbacks:
            self.state_change_callbacks.remove(callback)
            self.logger.debug(f"状態変更コールバック削除: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")

    def add_state_sync_callback(self, callback: Callable[[StateSyncInfo], None]):
        """状態同期コールバックを追加（新規機能）"""
        if callback not in self.state_sync_callbacks:
            self.state_sync_callbacks.append(callback)
            self.logger.debug(f"状態同期コールバック追加: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")

    def remove_state_sync_callback(self, callback: Callable[[StateSyncInfo], None]):
        """状態同期コールバックを削除"""
        if callback in self.state_sync_callbacks:
            self.state_sync_callbacks.remove(callback)
            self.logger.debug(f"状態同期コールバック削除: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")

    def get_current_state(self) -> Dict[str, Any]:
        """現在の状態を取得"""
        return {'step': self.current_step, 'status': self.current_status}

    def get_state_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """状態変更履歴を取得"""
        history = self.state_history[-limit:] if limit else self.state_history
        return [h.__dict__ for h in history]

    def get_sync_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """状態同期履歴を取得（新規機能）"""
        history = self.sync_history[-limit:] if limit else self.sync_history
        return [h.__dict__ for h in history]

    def get_available_transitions(self) -> List[Dict[str, Any]]:
        """利用可能な遷移を取得"""
        available = []
        for transition in self.transitions:
            if (transition.from_step == self.current_step and transition.from_status == self.current_status):
                available.append({'to_step': transition.to_step.value, 'to_status': transition.to_status.value, 'description': transition.description})
        return available

    def reset_to_idle(self):
        """IDLE状態にリセット"""
        self.transition_to(Step.IDLE, Status.PENDING, "システムリセット")

    def force_transition(self, target_step: Step, target_status: Status, trigger: str = "強制遷移", context: Optional[Dict[str, Any]] = None) -> bool:
        """強制状態遷移（緊急時用）"""
        self.logger.warning(f"強制状態遷移: {self.current_step.value}.{self.current_status.value} → {target_step.value}.{target_status.value} (トリガー: {trigger})")
        
        previous_step = self.current_step
        previous_status = self.current_status
        
        self.current_step = target_step
        self.current_status = target_status
        
        self._record_state_change(target_step, target_status, f"{trigger} (強制)", context)
        self._notify_state_change_callbacks(previous_step, previous_status, target_step, target_status, trigger)
        self._record_sync_info(target_step, target_status, trigger, True, "強制遷移")
        
        return True

    def get_sync_status(self) -> Dict[str, Any]:
        """状態同期の状況を取得（新規機能）"""
        return {
            'total_callbacks': len(self.state_change_callbacks),
            'total_sync_callbacks': len(self.state_sync_callbacks),
            'last_sync': self.sync_history[-1].__dict__ if self.sync_history else None,
            'sync_success_rate': self._calculate_sync_success_rate()
        }

    def _calculate_sync_success_rate(self) -> float:
        """同期成功率を計算"""
        if not self.sync_history:
            return 0.0
        
        successful_syncs = sum(1 for sync in self.sync_history if sync.sync_success)
        return (successful_syncs / len(self.sync_history)) * 100

    def enable_integrity_checks(self, enable: bool = True):
        """状態整合性チェックの有効/無効を設定"""
        self.enable_integrity_check = enable
        self.logger.info(f"状態整合性チェック: {'有効' if enable else '無効'}")

    def validate_current_state(self) -> bool:
        """現在の状態の整合性を検証"""
        return self._validate_state_integrity(self.current_step, self.current_status)