"""
TaskObjective - ユーザー要求の構造化追跡

統合タスクループアーキテクチャにおけるタスク状態管理
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field

from .llm_service import RequirementItem, SatisfactionEvaluation


@dataclass
class AttemptResult:
    """個別試行の結果"""
    attempt_number: int
    strategy: str                               # 使用した戦略
    execution_plan: Dict[str, Any]              # 実行計画  
    results: Dict[str, Any]                     # 実行結果
    satisfaction_score: float                   # 満足度スコア
    errors: List[str] = field(default_factory=list)         # 発生エラー
    lessons_learned: List[str] = field(default_factory=list) # 学んだ教訓
    timestamp: datetime = field(default_factory=datetime.now)
    duration: float = 0.0                       # 実行時間（秒）
    
    def __post_init__(self):
        # errorsが文字列の場合はリストに変換
        if isinstance(self.errors, str):
            self.errors = [self.errors] if self.errors else []
        elif self.errors is None:
            self.errors = []
        
        # lessons_learnedが文字列の場合はリストに変換
        if isinstance(self.lessons_learned, str):
            self.lessons_learned = [self.lessons_learned] if self.lessons_learned else []
        elif self.lessons_learned is None:
            self.lessons_learned = []


@dataclass
class ContinuationContext:
    """継続実行のためのコンテキスト情報"""
    
    # 前回実行情報
    previous_attempts: List[AttemptResult] = field(default_factory=list)
    execution_errors: List[str] = field(default_factory=list)
    partial_successes: List[Dict[str, Any]] = field(default_factory=list)
    
    # 改善指針
    identified_problems: List[str] = field(default_factory=list)
    suggested_improvements: List[str] = field(default_factory=list) 
    alternative_strategies: List[str] = field(default_factory=list)
    
    # 制約情報
    unavailable_resources: List[str] = field(default_factory=list)
    failed_approaches: List[str] = field(default_factory=list)
    learned_limitations: List[str] = field(default_factory=list)
    
    # 不足情報（MissingInfoAnalysisから）
    missing_info: Optional[Any] = None  # MissingInfoAnalysis型（循環インポート回避）
    
    def __post_init__(self):
        """文字列フィールドをリストに変換する処理"""
        
        # 各リストフィールドを確認して文字列の場合は変換
        list_fields = [
            'execution_errors', 'identified_problems', 'suggested_improvements',
            'alternative_strategies', 'unavailable_resources', 'failed_approaches',
            'learned_limitations'
        ]
        
        for field_name in list_fields:
            value = getattr(self, field_name)
            if isinstance(value, str):
                setattr(self, field_name, [value] if value else [])
            elif value is None:
                setattr(self, field_name, [])


@dataclass
class TaskObjective:
    """ユーザー要求の構造化された追跡オブジェクト"""
    
    # 基本情報
    original_query: str                                    # 元のユーザー要求
    extracted_requirements: List[RequirementItem] = field(default_factory=list)  # LLMが抽出した要件リスト
    created_at: datetime = field(default_factory=datetime.now)
    
    # 進捗追跡
    iteration_count: int = 0                              # 実行回数
    max_iterations: int = 3                               # 最大試行回数  
    current_satisfaction: float = 0.0                     # 現在の満足度 (0.0-1.0)
    target_satisfaction: float = 0.8                      # 目標満足度
    
    # 情報蓄積
    accumulated_results: Dict[str, Any] = field(default_factory=dict)  # 蓄積された実行結果
    learned_constraints: List[str] = field(default_factory=list)       # 学習した制約・教訓
    attempted_strategies: List[str] = field(default_factory=list)      # 試行済み戦略
    
    # 試行履歴
    attempt_history: List[AttemptResult] = field(default_factory=list)
    
    # 現在の満足度評価
    latest_evaluation: Optional[SatisfactionEvaluation] = None
    
    def __post_init__(self):
        """リストフィールドの型安全性を確保"""
        # learned_constraintsが文字列の場合はリストに変換
        if isinstance(self.learned_constraints, str):
            self.learned_constraints = [self.learned_constraints] if self.learned_constraints else []
        elif self.learned_constraints is None:
            self.learned_constraints = []
        
        # attempted_strategiesが文字列の場合はリストに変換  
        if isinstance(self.attempted_strategies, str):
            self.attempted_strategies = [self.attempted_strategies] if self.attempted_strategies else []
        elif self.attempted_strategies is None:
            self.attempted_strategies = []
        
        # extracted_requirementsが文字列の場合はリストに変換
        if isinstance(self.extracted_requirements, str):
            self.extracted_requirements = []  # 文字列の場合は空リストに
        elif self.extracted_requirements is None:
            self.extracted_requirements = []
        
        # attempt_historyが文字列の場合はリストに変換
        if isinstance(self.attempt_history, str):
            self.attempt_history = []  # 文字列の場合は空リストに
        elif self.attempt_history is None:
            self.attempt_history = []
        
        # accumulated_resultsが辞書でない場合は辞書に変換
        if not isinstance(self.accumulated_results, dict):
            self.accumulated_results = {}
    
    def add_attempt_result(self, attempt: AttemptResult) -> None:
        """試行結果を追加"""
        self.attempt_history.append(attempt)
        self.iteration_count = len(self.attempt_history)
        
        # 戦略と制約の学習
        if attempt.strategy not in self.attempted_strategies:
            self.attempted_strategies.append(attempt.strategy)
        
        # lessons_learnedが確実にリストであることを保証
        if isinstance(attempt.lessons_learned, list):
            self.learned_constraints.extend(attempt.lessons_learned)
        elif isinstance(attempt.lessons_learned, str) and attempt.lessons_learned:
            self.learned_constraints.append(attempt.lessons_learned)
        
        # 結果の蓄積
        if attempt.results:
            for key, value in attempt.results.items():
                # keyが存在しないか、リスト以外の場合は新しいリストを作成
                if key not in self.accumulated_results or not isinstance(self.accumulated_results[key], list):
                    self.accumulated_results[key] = []
                
                self.accumulated_results[key].append({
                    'value': value,
                    'attempt': attempt.attempt_number,
                    'timestamp': attempt.timestamp
                })
    
    def update_satisfaction(self, evaluation: SatisfactionEvaluation) -> None:
        """満足度評価を更新"""
        self.latest_evaluation = evaluation
        self.current_satisfaction = evaluation.overall_score
        
        # 要件別満足度を更新
        for req in self.extracted_requirements:
            if req.requirement in evaluation.requirement_scores:
                req.satisfaction_level = evaluation.requirement_scores[req.requirement]
    
    def is_completed(self) -> bool:
        """タスクが完了したかの判定"""
        return self.current_satisfaction >= self.target_satisfaction
    
    def is_at_max_iterations(self) -> bool:
        """最大試行回数に達したかの判定"""
        return self.iteration_count >= self.max_iterations
    
    def should_continue(self) -> bool:
        """継続すべきかの判定"""
        return not self.is_completed() and not self.is_at_max_iterations()
    
    def get_continuation_context(self) -> ContinuationContext:
        """継続コンテキストの生成"""
        context = ContinuationContext()
        
        # 試行履歴からの学習
        context.previous_attempts = self.attempt_history.copy()
        
        # エラーと制約の集約
        for attempt in self.attempt_history:
            # errorsが文字列の場合はリストに変換
            errors = attempt.errors if isinstance(attempt.errors, list) else [attempt.errors] if attempt.errors else []
            context.execution_errors.extend(errors)
            if attempt.satisfaction_score > 0.3:  # 部分的成功
                context.partial_successes.append(attempt.results)
        
        # 失敗戦略の記録
        context.failed_approaches = [
            attempt.strategy for attempt in self.attempt_history 
            if attempt.satisfaction_score < 0.5
        ]
        
        # learned_constraintsが文字列の場合はリストに変換
        constraints = self.learned_constraints if isinstance(self.learned_constraints, list) else [self.learned_constraints] if self.learned_constraints else []
        context.learned_limitations = constraints.copy()
        
        # 最新の評価から改善指針を抽出
        if self.latest_evaluation:
            # missing_aspectsが文字列の場合はリストに変換
            missing_aspects = self.latest_evaluation.missing_aspects
            if isinstance(missing_aspects, list):
                context.identified_problems = missing_aspects.copy()
            elif isinstance(missing_aspects, str) and missing_aspects:
                context.identified_problems = [missing_aspects]
            else:
                context.identified_problems = []
        
        return context
    
    def get_status_summary(self) -> Dict[str, Any]:
        """現在状況の要約"""
        return {
            'original_query': self.original_query,
            'iteration_count': f"{self.iteration_count}/{self.max_iterations}",
            'current_satisfaction': f"{self.current_satisfaction:.2f}/{self.target_satisfaction}",
            'completion_status': 'completed' if self.is_completed() else 'in_progress',
            'total_requirements': len(self.extracted_requirements),
            'satisfied_requirements': sum(1 for req in self.extracted_requirements if req.satisfaction_level >= 0.8),
            'attempted_strategies': len(self.attempted_strategies),
            'accumulated_data_types': list(self.accumulated_results.keys()),
            'latest_problems': self.latest_evaluation.missing_aspects if self.latest_evaluation else [],
        }
    
    def reset_for_retry(self, preserve_learning: bool = True) -> None:
        """再試行のためのリセット"""
        if not preserve_learning:
            self.learned_constraints.clear()
            self.attempted_strategies.clear()
        
        # 状態のリセット（学習内容は保持）
        self.current_satisfaction = 0.0
        
        # 最新の評価はリセット（履歴は保持）
        self.latest_evaluation = None


class TaskObjectiveManager:
    """TaskObjectiveの管理クラス"""
    
    def __init__(self):
        self.current_objective: Optional[TaskObjective] = None
        self.completed_objectives: List[TaskObjective] = []
    
    def create_new_objective(self, user_query: str, max_iterations: int = 3) -> TaskObjective:
        """新しいTaskObjectiveを作成"""
        # 既存のObjectiveがあれば完了リストに移動
        if self.current_objective:
            self.completed_objectives.append(self.current_objective)
        
        self.current_objective = TaskObjective(
            original_query=user_query,
            max_iterations=max_iterations
        )
        
        return self.current_objective
    
    def get_current_objective(self) -> Optional[TaskObjective]:
        """現在のTaskObjectiveを取得"""
        return self.current_objective
    
    def complete_current_objective(self) -> Optional[TaskObjective]:
        """現在のObjectiveを完了として記録"""
        if self.current_objective:
            completed = self.current_objective
            self.completed_objectives.append(completed)
            self.current_objective = None
            return completed
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報の取得"""
        total_objectives = len(self.completed_objectives) + (1 if self.current_objective else 0)
        completed_count = len(self.completed_objectives)
        
        if self.completed_objectives:
            avg_iterations = sum(obj.iteration_count for obj in self.completed_objectives) / len(self.completed_objectives)
            avg_satisfaction = sum(obj.current_satisfaction for obj in self.completed_objectives) / len(self.completed_objectives)
        else:
            avg_iterations = 0
            avg_satisfaction = 0
        
        return {
            'total_objectives': total_objectives,
            'completed_objectives': completed_count,
            'success_rate': completed_count / total_objectives if total_objectives > 0 else 0,
            'average_iterations': round(avg_iterations, 2),
            'average_satisfaction': round(avg_satisfaction, 2),
            'current_objective_status': self.current_objective.get_status_summary() if self.current_objective else None
        }


# グローバルTaskObjectiveマネージャー
task_objective_manager = TaskObjectiveManager()