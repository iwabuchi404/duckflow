#!/usr/bin/env python3
"""
状態遷移一元管理ステートマシン

EnhancedDualLoopSystem内で、AgentStateのStepとStatusを一元的に管理する
明確なステートマシンを実装。LLMの応答やタスクの結果に応じて、
必ずこのステートマシンを通してのみ状態が変更される。
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


class Step(Enum):
    """システムの実行ステップ"""
    IDLE = "IDLE"           # 待機状態
    PLANNING = "PLANNING"   # 計画立案
    EXECUTION = "EXECUTION" # 実行
    REVIEW = "REVIEW"       # レビュー
    AWAITING_APPROVAL = "AWAITING_APPROVAL"  # 承認待ち
    COMPLETED = "COMPLETED" # 完了
    ERROR = "ERROR"         # エラー


class Status(Enum):
    """各ステップの実行ステータス"""
    PENDING = "PENDING"     # 待機中
    RUNNING = "RUNNING"     # 実行中
    SUCCESS = "SUCCESS"     # 成功
    FAILED = "FAILED"       # 失敗
    CANCELLED = "CANCELLED" # キャンセル


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


class StateMachine:
    """状態遷移一元管理ステートマシン"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 現在の状態
        self.current_step = Step.IDLE
        self.current_status = Status.PENDING
        
        # 状態履歴
        self.state_history: List[StateHistory] = []
        self.max_history = 100
        
        # 状態遷移ルール
        self.transitions: List[StateTransition] = self._initialize_transitions()
        
        # 状態変更コールバック
        self.state_change_callbacks: List[Callable[[Step, Status, str], None]] = []
        
        # 初期状態を履歴に記録
        self._record_state_change(Step.IDLE, Status.PENDING, "初期化")
        
        self.logger.info("ステートマシン初期化完了")
    
    def _initialize_transitions(self) -> List[StateTransition]:
        """状態遷移ルールを初期化"""
        transitions = [
            # IDLE → PLANNING
            StateTransition(
                from_step=Step.IDLE,
                from_status=Status.PENDING,
                to_step=Step.PLANNING,
                to_status=Status.RUNNING,
                description="ユーザー要求受信による計画立案開始"
            ),
            
            # PLANNING → EXECUTION
            StateTransition(
                from_step=Step.PLANNING,
                from_status=Status.SUCCESS,
                to_step=Step.EXECUTION,
                to_status=Status.RUNNING,
                description="計画完了による実行開始"
            ),
            
            # PLANNING → ERROR
            StateTransition(
                from_step=Step.PLANNING,
                from_status=Status.FAILED,
                to_step=Step.ERROR,
                to_status=Status.FAILED,
                description="計画立案失敗によるエラー状態"
            ),
            
            # EXECUTION → REVIEW
            StateTransition(
                from_step=Step.EXECUTION,
                from_status=Status.SUCCESS,
                to_step=Step.REVIEW,
                to_status=Status.RUNNING,
                description="実行完了によるレビュー開始"
            ),
            
            # EXECUTION → ERROR
            StateTransition(
                from_step=Step.EXECUTION,
                from_status=Status.FAILED,
                to_step=Step.ERROR,
                to_status=Status.FAILED,
                description="実行失敗によるエラー状態"
            ),
            
            # REVIEW → COMPLETED
            StateTransition(
                from_step=Step.REVIEW,
                from_status=Status.SUCCESS,
                to_step=Step.COMPLETED,
                to_status=Status.SUCCESS,
                description="レビュー完了によるタスク完了"
            ),
            
            # REVIEW → EXECUTION
            StateTransition(
                from_step=Step.REVIEW,
                from_status=Status.FAILED,
                to_step=Step.EXECUTION,
                to_status=Status.RUNNING,
                description="レビュー失敗による再実行"
            ),
            
            # ERROR → IDLE
            StateTransition(
                from_step=Step.ERROR,
                from_status=Status.FAILED,
                to_step=Step.IDLE,
                to_status=Status.PENDING,
                description="エラー回復による待機状態復帰"
            ),
            
            # COMPLETED → IDLE
            StateTransition(
                from_step=Step.COMPLETED,
                from_status=Status.SUCCESS,
                to_step=Step.IDLE,
                to_status=Status.PENDING,
                description="タスク完了による待機状態復帰"
            ),
            
            # キャンセル処理
            StateTransition(
                from_step=Step.PLANNING,
                from_status=Status.RUNNING,
                to_step=Step.IDLE,
                to_status=Status.CANCELLED,
                description="計画立案のキャンセル"
            ),
            
            StateTransition(
                from_step=Step.EXECUTION,
                from_status=Status.RUNNING,
                to_step=Step.IDLE,
                to_status=Status.CANCELLED,
                description="実行のキャンセル"
            ),
            
            StateTransition(
                from_step=Step.REVIEW,
                from_status=Status.RUNNING,
                to_step=Step.IDLE,
                to_status=Status.CANCELLED,
                description="レビューのキャンセル"
            )
        ]
        
        return transitions
    
    def can_transition_to(self, target_step: Step, target_status: Status, 
                         context: Optional[Dict[str, Any]] = None) -> bool:
        """指定された状態への遷移が可能かチェック"""
        for transition in self.transitions:
            if (transition.from_step == self.current_step and 
                transition.from_status == self.current_status and
                transition.to_step == target_step and
                transition.to_status == target_status):
                
                # 条件チェック
                if transition.condition:
                    if context is None:
                        context = {}
                    if not transition.condition(context):
                        self.logger.debug(f"遷移条件不満足: {transition.description}")
                        return False
                
                return True
        
        self.logger.debug(f"遷移不可能: {self.current_step}.{self.current_status} → {target_step}.{target_status}")
        return False
    
    def transition_to(self, target_step: Step, target_status: Status, 
                     trigger: str = "", context: Optional[Dict[str, Any]] = None) -> bool:
        """状態遷移を実行"""
        try:
            if not self.can_transition_to(target_step, target_status, context):
                self.logger.warning(f"状態遷移失敗: {self.current_step}.{self.current_status} → {target_step}.{target_status}")
                return False
            
            # 遷移前の状態を保存
            previous_step = self.current_step
            previous_status = self.current_status
            
            # 状態を更新
            self.current_step = target_step
            self.current_status = target_status
            
            # 履歴に記録
            self._record_state_change(target_step, target_status, trigger, context)
            
            # コールバックを実行
            self._notify_state_change_callbacks(previous_step, previous_status, target_step, target_status, trigger)
            
            self.logger.info(f"状態遷移成功: {previous_step}.{previous_status} → {target_step}.{target_status} (トリガー: {trigger})")
            return True
            
        except Exception as e:
            self.logger.error(f"状態遷移エラー: {e}")
            return False
    
    def _record_state_change(self, step: Step, status: Status, trigger: str, 
                           context: Optional[Dict[str, Any]] = None):
        """状態変更を履歴に記録"""
        history = StateHistory(
            step=step,
            status=status,
            timestamp=datetime.now(),
            trigger=trigger,
            metadata=context or {}
        )
        
        self.state_history.append(history)
        
        # 最大履歴数を超えた場合、古い履歴を削除
        if len(self.state_history) > self.max_history:
            self.state_history = self.state_history[-self.max_history:]
    
    def _notify_state_change_callbacks(self, from_step: Step, from_status: Status,
                                     to_step: Step, to_status: Status, trigger: str):
        """状態変更コールバックを実行"""
        for callback in self.state_change_callbacks:
            try:
                callback(to_step, to_status, trigger)
            except Exception as e:
                self.logger.error(f"状態変更コールバックエラー: {e}")
    
    def add_state_change_callback(self, callback: Callable[[Step, Status, str], None]):
        """状態変更コールバックを追加"""
        self.state_change_callbacks.append(callback)
    
    def remove_state_change_callback(self, callback: Callable[[Step, Status, str], None]):
        """状態変更コールバックを削除"""
        if callback in self.state_change_callbacks:
            self.state_change_callbacks.remove(callback)
    
    def get_current_state(self) -> Dict[str, Any]:
        """現在の状態を取得"""
        return {
            'step': self.current_step.value,
            'status': self.current_status.value,
            'step_enum': self.current_step,
            'status_enum': self.current_status
        }
    
    def get_state_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """状態履歴を取得"""
        history = self.state_history
        if limit:
            history = history[-limit:]
        
        return [
            {
                'step': h.step.value,
                'status': h.status.value,
                'timestamp': h.timestamp.isoformat(),
                'trigger': h.trigger,
                'metadata': h.metadata
            }
            for h in history
        ]
    
    def get_available_transitions(self) -> List[Dict[str, Any]]:
        """現在の状態から可能な遷移を取得"""
        available = []
        
        for transition in self.transitions:
            if (transition.from_step == self.current_step and 
                transition.from_status == self.current_status):
                available.append({
                    'to_step': transition.to_step.value,
                    'to_status': transition.to_status.value,
                    'description': transition.description,
                    'has_condition': transition.condition is not None
                })
        
        return available
    
    def reset_to_idle(self):
        """IDLE状態にリセット"""
        self.transition_to(Step.IDLE, Status.PENDING, "システムリセット")
    
    def force_transition(self, target_step: Step, target_status: Status, 
                        trigger: str = "強制遷移", context: Optional[Dict[str, Any]] = None) -> bool:
        """強制的な状態遷移（通常の遷移ルールを無視）"""
        try:
            # 遷移前の状態を保存
            previous_step = self.current_step
            previous_status = self.current_status
            
            # 状態を更新
            self.current_step = target_step
            self.current_status = target_status
            
            # 履歴に記録（強制遷移としてマーク）
            self._record_state_change(target_step, target_status, f"{trigger} (強制)", context)
            
            # コールバックを実行
            self._notify_state_change_callbacks(previous_step, previous_status, target_step, target_status, trigger)
            
            self.logger.warning(f"強制状態遷移: {previous_step}.{previous_status} → {target_step}.{target_status} (トリガー: {trigger})")
            return True
            
        except Exception as e:
            self.logger.error(f"強制状態遷移エラー: {e}")
            return False
    
    def is_in_final_state(self) -> bool:
        """最終状態（COMPLETED、ERROR）にあるかチェック"""
        return self.current_step in [Step.COMPLETED, Step.ERROR]
    
    def is_in_error_state(self) -> bool:
        """エラー状態にあるかチェック"""
        return self.current_step == Step.ERROR
    
    def get_system_health(self) -> Dict[str, Any]:
        """システムの健全性を評価"""
        # 最近の状態変更を分析
        recent_history = self.state_history[-10:] if self.state_history else []
        
        # エラー状態の頻度
        error_count = sum(1 for h in recent_history if h.step == Step.ERROR)
        total_count = len(recent_history)
        error_rate = (error_count / total_count * 100) if total_count > 0 else 0
        
        # 状態変更の頻度
        if len(recent_history) >= 2:
            time_span = (recent_history[-1].timestamp - recent_history[0].timestamp).total_seconds()
            change_frequency = len(recent_history) / time_span if time_span > 0 else 0
        else:
            change_frequency = 0
        
        return {
            'current_state': self.get_current_state(),
            'error_rate': round(error_rate, 2),
            'change_frequency': round(change_frequency, 2),
            'available_transitions': len(self.get_available_transitions()),
            'system_stable': error_rate < 20 and change_frequency < 1.0,  # 20%未満のエラー率、1回/秒未満の変更頻度
            'recommendations': self._generate_health_recommendations(error_rate, change_frequency)
        }
    
    def _generate_health_recommendations(self, error_rate: float, change_frequency: float) -> List[str]:
        """健全性に基づく推奨事項を生成"""
        recommendations = []
        
        if error_rate > 30:
            recommendations.append("エラー率が高いため、システムの安定性を確認してください")
        
        if change_frequency > 2.0:
            recommendations.append("状態変更が頻繁すぎるため、処理の最適化を検討してください")
        
        if self.is_in_error_state():
            recommendations.append("現在エラー状態です。システムの復旧を試行してください")
        
        if not recommendations:
            recommendations.append("システムは正常に動作しています")
        
        return recommendations
    
    def to_dict(self) -> Dict[str, Any]:
        """ステートマシンの状態を辞書形式で取得"""
        return {
            'current_state': self.get_current_state(),
            'available_transitions': self.get_available_transitions(),
            'state_history_count': len(self.state_history),
            'system_health': self.get_system_health(),
            'callbacks_count': len(self.state_change_callbacks)
        }
