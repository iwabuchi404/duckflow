# error_recovery_system.py
"""
Error Recovery System - エラー回復システム
Step 3: 高度なエラーハンドリングとリカバリ機能

タスク実行中のエラーを検出し、自動回復または
ユーザーとの対話による回復を行うシステム。
"""

import time
import uuid
from typing import Dict, List, Any, Optional, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging


class ErrorSeverity(Enum):
    """エラーの重要度"""
    LOW = "low"           # 軽微なエラー（警告レベル）
    MEDIUM = "medium"     # 中程度のエラー（注意が必要）
    HIGH = "high"         # 重大なエラー（即座の対応が必要）
    CRITICAL = "critical" # 致命的なエラー（システム停止レベル）


class RecoveryStrategy(Enum):
    """回復戦略"""
    RETRY = "retry"                    # 自動リトライ
    SKIP = "skip"                      # スキップして続行
    ALTERNATIVE = "alternative"        # 代替手段を試行
    USER_INTERVENTION = "user_input"   # ユーザー介入が必要
    ABORT = "abort"                    # タスクを中止


@dataclass
class ErrorContext:
    """エラーの文脈情報"""
    error_id: str
    error_message: str
    error_type: str
    severity: ErrorSeverity
    timestamp: datetime
    task_id: Optional[str] = None
    step_name: Optional[str] = None
    context_data: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "error_id": self.error_id,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "task_id": self.task_id,
            "step_name": self.step_name,
            "context_data": self.context_data,
            "stack_trace": self.stack_trace
        }


@dataclass
class RecoveryAction:
    """回復アクション"""
    action_id: str
    strategy: RecoveryStrategy
    description: str
    auto_executable: bool = True
    estimated_success_rate: float = 0.5  # 成功率の推定 (0.0-1.0)
    execution_time_estimate: int = 30     # 実行時間推定（秒）
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "action_id": self.action_id,
            "strategy": self.strategy.value,
            "description": self.description,
            "auto_executable": self.auto_executable,
            "estimated_success_rate": self.estimated_success_rate,
            "execution_time_estimate": self.execution_time_estimate,
            "parameters": self.parameters
        }


@dataclass
class RecoveryPlan:
    """回復計画"""
    plan_id: str
    error_context: ErrorContext
    actions: List[RecoveryAction]
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "pending"  # pending, executing, completed, failed
    selected_action: Optional[str] = None
    execution_result: Optional[str] = None
    
    def get_recommended_action(self) -> Optional[RecoveryAction]:
        """推奨アクションを取得"""
        if not self.actions:
            return None
        
        # 成功率の高い自動実行可能なアクションを優先
        auto_actions = [a for a in self.actions if a.auto_executable]
        if auto_actions:
            return max(auto_actions, key=lambda a: a.estimated_success_rate)
        
        # 自動実行できない場合は最初のアクション
        return self.actions[0]


class ErrorRecoverySystem:
    """Step 3: エラー回復システム"""
    
    def __init__(self):
        """初期化"""
        self.error_history: List[ErrorContext] = []
        self.recovery_plans: Dict[str, RecoveryPlan] = {}
        self.error_patterns: Dict[str, List[RecoveryAction]] = {}
        self.max_retry_attempts = 3
        self.retry_delay_base = 2.0  # 指数バックオフの基準秒数
        
        # ログ設定
        self.logger = logging.getLogger(__name__)
        
        # 標準的なエラーパターンを初期化
        self._initialize_error_patterns()
    
    def _initialize_error_patterns(self):
        """標準的なエラーパターンを初期化"""
        
        # ファイル操作エラー
        file_error_actions = [
            RecoveryAction(
                action_id="retry_file_op",
                strategy=RecoveryStrategy.RETRY,
                description="ファイル操作を再試行する",
                auto_executable=True,
                estimated_success_rate=0.7,
                execution_time_estimate=10
            ),
            RecoveryAction(
                action_id="check_permissions",
                strategy=RecoveryStrategy.ALTERNATIVE,
                description="ファイルのアクセス権限を確認し、必要に応じて調整する",
                auto_executable=False,
                estimated_success_rate=0.8,
                execution_time_estimate=30
            ),
            RecoveryAction(
                action_id="skip_file",
                strategy=RecoveryStrategy.SKIP,
                description="このファイルをスキップして続行する",
                auto_executable=True,
                estimated_success_rate=1.0,
                execution_time_estimate=5
            )
        ]
        
        # ネットワークエラー
        network_error_actions = [
            RecoveryAction(
                action_id="retry_with_delay",
                strategy=RecoveryStrategy.RETRY,
                description="少し待ってから接続を再試行する",
                auto_executable=True,
                estimated_success_rate=0.6,
                execution_time_estimate=30
            ),
            RecoveryAction(
                action_id="use_alternative_endpoint",
                strategy=RecoveryStrategy.ALTERNATIVE,
                description="別のエンドポイントを使用する",
                auto_executable=True,
                estimated_success_rate=0.4,
                execution_time_estimate=20
            ),
            RecoveryAction(
                action_id="offline_mode",
                strategy=RecoveryStrategy.ALTERNATIVE,
                description="オフラインモードで続行する",
                auto_executable=True,
                estimated_success_rate=0.8,
                execution_time_estimate=10
            )
        ]
        
        # LLMエラー
        llm_error_actions = [
            RecoveryAction(
                action_id="retry_llm",
                strategy=RecoveryStrategy.RETRY,
                description="LLMリクエストを再試行する",
                auto_executable=True,
                estimated_success_rate=0.8,
                execution_time_estimate=15
            ),
            RecoveryAction(
                action_id="fallback_model",
                strategy=RecoveryStrategy.ALTERNATIVE,
                description="フォールバックモデルを使用する",
                auto_executable=True,
                estimated_success_rate=0.7,
                execution_time_estimate=20
            ),
            RecoveryAction(
                action_id="manual_processing",
                strategy=RecoveryStrategy.USER_INTERVENTION,
                description="手動でタスクを処理する",
                auto_executable=False,
                estimated_success_rate=0.9,
                execution_time_estimate=300
            )
        ]
        
        # エラーパターンを登録
        self.error_patterns.update({
            "FileNotFoundError": file_error_actions,
            "PermissionError": file_error_actions,
            "ConnectionError": network_error_actions,
            "TimeoutError": network_error_actions,
            "APIError": llm_error_actions,
            "RateLimitError": llm_error_actions,
        })
    
    def capture_error(self, 
                     error: Exception, 
                     task_id: Optional[str] = None,
                     step_name: Optional[str] = None,
                     context_data: Optional[Dict[str, Any]] = None) -> ErrorContext:
        """エラーを捕捉して文脈情報を作成
        
        Args:
            error: 発生したエラー
            task_id: タスクID
            step_name: ステップ名
            context_data: 追加の文脈データ
            
        Returns:
            ErrorContext: エラー文脈情報
        """
        error_id = str(uuid.uuid4())[:8]
        error_type = type(error).__name__
        
        # エラーの重要度を判定
        severity = self._assess_error_severity(error_type, str(error))
        
        error_context = ErrorContext(
            error_id=error_id,
            error_message=str(error),
            error_type=error_type,
            severity=severity,
            timestamp=datetime.now(),
            task_id=task_id,
            step_name=step_name,
            context_data=context_data or {},
            stack_trace=self._get_stack_trace(error)
        )
        
        # エラー履歴に追加
        self.error_history.append(error_context)
        
        # 履歴の上限管理
        if len(self.error_history) > 100:
            self.error_history = self.error_history[-50:]
        
        self.logger.warning(f"エラーを捕捉: {error_id} - {error_type}: {str(error)}")
        
        return error_context
    
    def _assess_error_severity(self, error_type: str, error_message: str) -> ErrorSeverity:
        """エラーの重要度を評価
        
        Args:
            error_type: エラーの種類
            error_message: エラーメッセージ
            
        Returns:
            ErrorSeverity: 重要度
        """
        error_message_lower = error_message.lower()
        
        # 致命的なエラー
        if any(keyword in error_message_lower for keyword in 
               ['system', 'memory', 'disk full', 'critical', 'fatal']):
            return ErrorSeverity.CRITICAL
        
        # 重大なエラー
        if error_type in ['KeyboardInterrupt', 'SystemExit', 'MemoryError']:
            return ErrorSeverity.HIGH
        
        # 中程度のエラー
        if error_type in ['ConnectionError', 'TimeoutError', 'APIError']:
            return ErrorSeverity.MEDIUM
        
        # 軽微なエラー
        return ErrorSeverity.LOW
    
    def _get_stack_trace(self, error: Exception) -> Optional[str]:
        """スタックトレースを取得"""
        import traceback
        try:
            return traceback.format_exc()
        except:
            return None
    
    def create_recovery_plan(self, error_context: ErrorContext) -> RecoveryPlan:
        """回復計画を作成
        
        Args:
            error_context: エラー文脈情報
            
        Returns:
            RecoveryPlan: 作成された回復計画
        """
        plan_id = str(uuid.uuid4())[:8]
        
        # エラーパターンに基づいてアクションを選択
        actions = self._get_recovery_actions(error_context)
        
        # カスタムアクションを追加
        actions.extend(self._generate_custom_actions(error_context))
        
        recovery_plan = RecoveryPlan(
            plan_id=plan_id,
            error_context=error_context,
            actions=actions
        )
        
        self.recovery_plans[plan_id] = recovery_plan
        
        self.logger.info(f"回復計画を作成: {plan_id} - {len(actions)}個のアクション")
        
        return recovery_plan
    
    def _get_recovery_actions(self, error_context: ErrorContext) -> List[RecoveryAction]:
        """エラーパターンに基づく回復アクションを取得"""
        error_type = error_context.error_type
        
        # 完全一致のパターンを探す
        if error_type in self.error_patterns:
            return self.error_patterns[error_type].copy()
        
        # 部分一致のパターンを探す
        for pattern, actions in self.error_patterns.items():
            if pattern.lower() in error_type.lower():
                return actions.copy()
        
        # デフォルトアクション
        return [
            RecoveryAction(
                action_id="generic_retry",
                strategy=RecoveryStrategy.RETRY,
                description="操作を再試行する",
                auto_executable=True,
                estimated_success_rate=0.5,
                execution_time_estimate=20
            ),
            RecoveryAction(
                action_id="skip_and_continue",
                strategy=RecoveryStrategy.SKIP,
                description="このステップをスキップして続行する",
                auto_executable=True,
                estimated_success_rate=0.8,
                execution_time_estimate=5
            ),
            RecoveryAction(
                action_id="abort_task",
                strategy=RecoveryStrategy.ABORT,
                description="タスクを中止する",
                auto_executable=True,
                estimated_success_rate=1.0,
                execution_time_estimate=5
            )
        ]
    
    def _generate_custom_actions(self, error_context: ErrorContext) -> List[RecoveryAction]:
        """エラー文脈に基づくカスタムアクションを生成"""
        custom_actions = []
        
        # ファイル関連のエラーの場合
        if "file" in error_context.error_message.lower():
            custom_actions.append(RecoveryAction(
                action_id="create_missing_directory",
                strategy=RecoveryStrategy.ALTERNATIVE,
                description="必要なディレクトリを作成する",
                auto_executable=True,
                estimated_success_rate=0.9,
                execution_time_estimate=10
            ))
        
        # ネットワーク関連のエラーの場合
        if any(keyword in error_context.error_message.lower() 
               for keyword in ['connection', 'network', 'timeout']):
            custom_actions.append(RecoveryAction(
                action_id="check_network_connectivity",
                strategy=RecoveryStrategy.ALTERNATIVE,
                description="ネットワーク接続を確認する",
                auto_executable=False,
                estimated_success_rate=0.6,
                execution_time_estimate=60
            ))
        
        return custom_actions
    
    def get_recovery_options(self, plan_id: str) -> Optional[str]:
        """回復オプションをユーザー向けに整形
        
        Args:
            plan_id: 回復計画ID
            
        Returns:
            Optional[str]: 整形された回復オプション
        """
        plan = self.recovery_plans.get(plan_id)
        if not plan:
            return None
        
        error = plan.error_context
        actions = plan.actions
        
        options = f"""
🚨 **エラーが発生しました**

**エラー詳細:**
- 種類: {error.error_type}
- メッセージ: {error.error_message}
- 重要度: {error.severity.value.upper()}
- 発生時刻: {error.timestamp.strftime('%H:%M:%S')}
"""
        
        if error.step_name:
            options += f"- ステップ: {error.step_name}\n"
        
        options += f"""
**回復オプション:**
"""
        
        for i, action in enumerate(actions, 1):
            auto_mark = " (自動実行可能)" if action.auto_executable else " (手動対応が必要)"
            success_rate = f"{action.estimated_success_rate:.0%}"
            time_est = f"{action.execution_time_estimate}秒"
            
            options += f"\n{i}. **{action.description}**{auto_mark}"
            options += f"\n   成功率: {success_rate} | 推定時間: {time_est}"
        
        recommended = plan.get_recommended_action()
        if recommended:
            rec_index = actions.index(recommended) + 1
            options += f"\n\n**推奨:** オプション {rec_index} - {recommended.description}"
        
        options += f"""

**コマンド:**
- `1`, `2`, `3`... - 対応するオプションを実行
- `auto` - 推奨オプションを自動実行
- `abort` - タスクを中止
- `details` - エラーの詳細情報を表示
"""
        
        return options.strip()
    
    def execute_recovery_action(self, 
                               plan_id: str, 
                               action_id: str,
                               executor: Optional[Callable] = None) -> Tuple[bool, str]:
        """回復アクションを実行
        
        Args:
            plan_id: 回復計画ID
            action_id: アクションID
            executor: カスタム実行関数
            
        Returns:
            Tuple[bool, str]: (成功フラグ, 結果メッセージ)
        """
        plan = self.recovery_plans.get(plan_id)
        if not plan:
            return False, "回復計画が見つかりません"
        
        action = None
        for a in plan.actions:
            if a.action_id == action_id:
                action = a
                break
        
        if not action:
            return False, "指定されたアクションが見つかりません"
        
        plan.status = "executing"
        plan.selected_action = action_id
        
        try:
            self.logger.info(f"回復アクション実行開始: {action_id}")
            
            # カスタム実行関数がある場合はそれを使用
            if executor:
                success, message = executor(action)
            else:
                success, message = self._execute_default_action(action, plan.error_context)
            
            plan.status = "completed" if success else "failed"
            plan.execution_result = message
            
            self.logger.info(f"回復アクション完了: {action_id} - {'成功' if success else '失敗'}")
            
            return success, message
            
        except Exception as e:
            plan.status = "failed"
            plan.execution_result = f"実行中にエラー: {str(e)}"
            self.logger.error(f"回復アクション実行エラー: {e}")
            return False, f"実行中にエラーが発生しました: {str(e)}"
    
    def _execute_default_action(self, 
                               action: RecoveryAction, 
                               error_context: ErrorContext) -> Tuple[bool, str]:
        """デフォルトアクションの実行
        
        Args:
            action: 実行するアクション
            error_context: エラー文脈
            
        Returns:
            Tuple[bool, str]: (成功フラグ, 結果メッセージ)
        """
        strategy = action.strategy
        
        if strategy == RecoveryStrategy.RETRY:
            return True, "再試行を実行しました（実際の再試行は呼び出し元で実装）"
        
        elif strategy == RecoveryStrategy.SKIP:
            return True, "ステップをスキップしました"
        
        elif strategy == RecoveryStrategy.ABORT:
            return True, "タスクを中止しました"
        
        elif strategy == RecoveryStrategy.USER_INTERVENTION:
            return False, "ユーザーの手動介入が必要です"
        
        elif strategy == RecoveryStrategy.ALTERNATIVE:
            return True, "代替手段を実行しました（実際の代替処理は呼び出し元で実装）"
        
        else:
            return False, f"未対応の回復戦略: {strategy.value}"
    
    def should_auto_recover(self, error_context: ErrorContext) -> bool:
        """自動回復すべきかどうかを判定
        
        Args:
            error_context: エラー文脈
            
        Returns:
            bool: 自動回復すべき場合True
        """
        # 重要度が高い場合は自動回復しない
        if error_context.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            return False
        
        # 最近同じエラーが頻発している場合は自動回復しない
        recent_errors = [e for e in self.error_history 
                        if e.error_type == error_context.error_type and
                        (datetime.now() - e.timestamp).total_seconds() < 300]  # 5分以内
        
        if len(recent_errors) >= 3:
            return False
        
        return True
    
    def get_error_summary(self) -> Dict[str, Any]:
        """エラーサマリーを取得"""
        now = datetime.now()
        recent_errors = [e for e in self.error_history 
                        if (now - e.timestamp).total_seconds() < 3600]  # 1時間以内
        
        error_types = {}
        severities = {}
        
        for error in recent_errors:
            error_types[error.error_type] = error_types.get(error.error_type, 0) + 1
            severities[error.severity.value] = severities.get(error.severity.value, 0) + 1
        
        return {
            "total_errors": len(self.error_history),
            "recent_errors": len(recent_errors),
            "error_types": error_types,
            "severities": severities,
            "active_recovery_plans": len([p for p in self.recovery_plans.values() 
                                        if p.status in ["pending", "executing"]])
        }