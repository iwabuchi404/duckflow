"""
Transition Controller for Duckflow v3

設計ドキュメント 6. 許可遷移表による制御の実装
- 遷移の暴走を防ぎ、1発話あたり遷移は最大1回
- 許可された遷移のみを実行
- エラー時の復旧処理
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from companion.state.agent_state import Step, Status


class TransitionController:
    """許可遷移表による制御システム"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 許可遷移表の定義
        self.allowed_transitions = {
            Step.PLANNING: [
                Step.EXECUTION,
                Step.REVIEW,
                Step.AWAITING_APPROVAL
            ],
            Step.EXECUTION: [
                Step.REVIEW,
                Step.AWAITING_APPROVAL,
                Step.PLANNING  # エラー時の復旧用
            ],
            Step.REVIEW: [
                Step.EXECUTION,
                Step.AWAITING_APPROVAL,
                "DONE"  # 完了状態
            ],
            Step.AWAITING_APPROVAL: [
                Step.EXECUTION,
                Step.PLANNING
            ]
        }
        
        # エラー時の特別遷移
        self.error_transitions = {
            Step.EXECUTION: Step.PLANNING,  # 実行エラー時は計画に戻る
            Step.REVIEW: Step.PLANNING      # レビューエラー時は計画に戻る
        }
        
        # 遷移履歴
        self.transition_history: List[Dict[str, Any]] = []
        self.max_history_size = 50
        
        # 遷移制限
        self.transition_limiter = TransitionLimiter()
    
    def is_transition_allowed(self, from_step: Step, to_step: Step) -> bool:
        """遷移が許可されているかをチェック
        
        Args:
            from_step: 現在のステップ
            to_step: 遷移先のステップ
            
        Returns:
            bool: 遷移が許可されているか
        """
        # 遷移制限のチェック
        if not self.transition_limiter.can_transition():
            self.logger.warning(f"遷移制限により遷移が拒否されました: {from_step.value} -> {to_step.value}")
            return False
        
        # 許可遷移表のチェック
        if from_step not in self.allowed_transitions:
            self.logger.warning(f"未定義のステップからの遷移: {from_step.value}")
            return False
        
        # 完了状態への遷移は特別処理
        if to_step == "DONE":
            return from_step == Step.REVIEW
        
        # 通常の遷移チェック
        allowed = to_step in self.allowed_transitions[from_step]
        
        if not allowed:
            self.logger.warning(f"許可されていない遷移: {from_step.value} -> {to_step.value}")
        
        return allowed
    
    def execute_transition(self, from_step: Step, to_step: Step, 
                          reason: str = "", context: Optional[Dict[str, Any]] = None) -> bool:
        """遷移を実行
        
        Args:
            from_step: 現在のステップ
            to_step: 遷移先のステップ
            reason: 遷移の理由
            context: 追加のコンテキスト
            
        Returns:
            bool: 遷移が成功したか
        """
        try:
            # 遷移の許可チェック
            if not self.is_transition_allowed(from_step, to_step):
                return False
            
            # 遷移制限の記録
            self.transition_limiter.record_transition()
            
            # 遷移履歴に記録
            transition_record = {
                "timestamp": datetime.now().isoformat(),
                "from_step": from_step.value,
                "to_step": to_step.value if to_step != "DONE" else "DONE",
                "reason": reason,
                "context": context or {},
                "success": True
            }
            
            self.transition_history.append(transition_record)
            
            # 履歴サイズの制限
            if len(self.transition_history) > self.max_history_size:
                self.transition_history = self.transition_history[-self.max_history_size:]
            
            self.logger.info(f"遷移実行成功: {from_step.value} -> {to_step.value} (理由: {reason})")
            return True
            
        except Exception as e:
            self.logger.error(f"遷移実行エラー: {e}")
            
            # エラー時の遷移記録
            error_record = {
                "timestamp": datetime.now().isoformat(),
                "from_step": from_step.value,
                "to_step": to_step.value if to_step != "DONE" else "DONE",
                "reason": reason,
                "context": context or {},
                "success": False,
                "error": str(e)
            }
            
            self.transition_history.append(error_record)
            return False
    
    def get_error_recovery_step(self, current_step: Step) -> Step:
        """エラー時の復旧ステップを取得
        
        Args:
            current_step: 現在のステップ
            
        Returns:
            Step: 復旧先のステップ
        """
        recovery_step = self.error_transitions.get(current_step, Step.PLANNING)
        self.logger.info(f"エラー復旧: {current_step.value} -> {recovery_step.value}")
        return recovery_step
    
    def get_transition_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """遷移履歴を取得
        
        Args:
            limit: 取得件数の制限
            
        Returns:
            List[Dict]: 遷移履歴
        """
        if limit is None:
            return self.transition_history.copy()
        
        return self.transition_history[-limit:] if len(self.transition_history) > limit else self.transition_history.copy()
    
    def get_transition_statistics(self) -> Dict[str, Any]:
        """遷移統計を取得"""
        if not self.transition_history:
            return {
                "total_transitions": 0,
                "successful_transitions": 0,
                "failed_transitions": 0,
                "most_common_transition": None,
                "average_transitions_per_minute": 0
            }
        
        total = len(self.transition_history)
        successful = len([t for t in self.transition_history if t.get("success", False)])
        failed = total - successful
        
        # 最も一般的な遷移パターン
        transition_patterns = {}
        for record in self.transition_history:
            pattern = f"{record['from_step']} -> {record['to_step']}"
            transition_patterns[pattern] = transition_patterns.get(pattern, 0) + 1
        
        most_common = max(transition_patterns.items(), key=lambda x: x[1]) if transition_patterns else None
        
        # 1分あたりの平均遷移数
        if len(self.transition_history) >= 2:
            first_time = datetime.fromisoformat(self.transition_history[0]["timestamp"])
            last_time = datetime.fromisoformat(self.transition_history[-1]["timestamp"])
            time_diff = (last_time - first_time).total_seconds() / 60  # 分単位
            avg_per_minute = total / time_diff if time_diff > 0 else 0
        else:
            avg_per_minute = 0
        
        return {
            "total_transitions": total,
            "successful_transitions": successful,
            "failed_transitions": failed,
            "success_rate": successful / total if total > 0 else 0,
            "most_common_transition": most_common[0] if most_common else None,
            "most_common_count": most_common[1] if most_common else 0,
            "average_transitions_per_minute": avg_per_minute
        }
    
    def reset_transition_history(self):
        """遷移履歴をリセット"""
        self.transition_history.clear()
        self.transition_limiter.reset()
        self.logger.info("遷移履歴をリセットしました")
    
    def get_allowed_transitions_for_step(self, step: Step) -> List[Step]:
        """指定されたステップから許可されている遷移先を取得"""
        if step not in self.allowed_transitions:
            return []
        
        allowed = self.allowed_transitions[step].copy()
        
        # DONEは特別処理
        if "DONE" in allowed:
            allowed.remove("DONE")
            allowed.append("DONE")
        
        return allowed
    
    def validate_transition_plan(self, current_step: Step, 
                               planned_transitions: List[Step]) -> Dict[str, Any]:
        """遷移計画の妥当性を検証"""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "recommendations": []
        }
        
        if not planned_transitions:
            validation_result["warnings"].append("遷移計画が空です")
            return validation_result
        
        # 連続遷移の妥当性チェック
        current = current_step
        for i, next_step in enumerate(planned_transitions):
            if not self.is_transition_allowed(current, next_step):
                validation_result["is_valid"] = False
                validation_result["errors"].append(
                    f"遷移{i+1}: {current.value} -> {next_step.value} は許可されていません"
                )
            
            current = next_step
        
        # 遷移数の制限チェック
        if len(planned_transitions) > 1:
            validation_result["warnings"].append(
                f"複数の遷移が計画されています（{len(planned_transitions)}件）。1発話1遷移を推奨します"
            )
        
        # 推奨事項
        if current_step == Step.PLANNING and Step.EXECUTION in planned_transitions:
            validation_result["recommendations"].append("計画完了後は実行ステップへの遷移が適切です")
        
        if current_step == Step.EXECUTION and Step.REVIEW in planned_transitions:
            validation_result["recommendations"].append("実行完了後はレビューステップへの遷移が適切です")
        
        return validation_result


class TransitionLimiter:
    """1発話あたり最大1回の遷移制限"""
    
    def __init__(self):
        self.last_transition_time: Optional[datetime] = None
        self.transition_count = 0
        self.max_transitions_per_utterance = 1
        self.reset_interval = 60  # 60秒でリセット
    
    def can_transition(self) -> bool:
        """遷移が可能かチェック"""
        current_time = datetime.now()
        
        # 時間リセットチェック
        if (self.last_transition_time and 
            (current_time - self.last_transition_time).total_seconds() > self.reset_interval):
            self.transition_count = 0
        
        return self.transition_count < self.max_transitions_per_utterance
    
    def record_transition(self):
        """遷移を記録"""
        self.transition_count += 1
        self.last_transition_time = datetime.now()
    
    def reset(self):
        """制限をリセット"""
        self.transition_count = 0
        self.last_transition_time = None
    
    def get_status(self) -> Dict[str, Any]:
        """現在の制限状態を取得"""
        return {
            "transition_count": self.transition_count,
            "max_transitions": self.max_transitions_per_utterance,
            "can_transition": self.can_transition(),
            "last_transition_time": self.last_transition_time.isoformat() if self.last_transition_time else None,
            "reset_interval_seconds": self.reset_interval
        }
