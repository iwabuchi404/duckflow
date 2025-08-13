"""
4ノード統合アーキテクチャ用のPromptContextとデータクラス

このモジュールは、7ノード→4ノード統合に対応した新しいPromptContextと
各段階の結果を保持するデータクラスを定義します。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

from ..state.agent_state import ConversationMessage


class NodeType(Enum):
    """4ノードの種類"""
    UNDERSTANDING = "understanding"  # 理解・計画ノード
    GATHERING = "gathering"         # 情報収集ノード  
    EXECUTION = "execution"         # 安全実行ノード
    EVALUATION = "evaluation"       # 評価・継続ノード


class NextAction(Enum):
    """次のアクション種別 (5ノードアーキテクチャ対応)"""
    COMPLETE = "complete"      # タスク完了
    CONTINUE = "continue"      # 継続実行
    RETRY = "retry"           # 再試行
    ERROR = "error"           # エラー終了
    # 5ノードアーキテクチャ専用アクション
    RESPONSE_GENERATION = "response_generation"  # 応答生成へ進む
    REPLAN = "replan"                           # 再計画が必要
    COLLECT_MORE_INFO = "collect_more_info"     # 追加情報収集が必要
    EXECUTE_ADDITIONAL = "execute_additional"   # 追加実行が必要
    END = "end"                                 # 処理終了
    DUCK_CALL = "duck_call"                     # 人間相談が必要


class RiskLevel(Enum):
    """リスクレベル"""
    LOW = "low"       # 低リスク
    MEDIUM = "medium" # 中リスク  
    HIGH = "high"     # 高リスク


@dataclass
class ExecutionPlan:
    """実行計画"""
    summary: str                           # 計画の概要
    steps: List[str]                      # 実行ステップ
    required_tools: List[str]             # 必要なツール
    expected_files: List[str]             # 対象ファイル
    estimated_complexity: str             # 予想される複雑度
    success_criteria: str                 # 成功基準


@dataclass
class FileContent:
    """ファイル内容情報"""
    path: str                            # ファイルパス
    content: str                         # ファイル内容
    encoding: str                        # エンコーディング
    size: int                           # ファイルサイズ
    last_modified: datetime              # 最終更新日時
    relevance_score: float = 0.0         # 関連度スコア


@dataclass 
class RAGResult:
    """RAG検索結果"""
    query: str                           # 検索クエリ
    results: List[Dict[str, Any]]        # 検索結果
    confidence: float                    # 信頼度
    total_matches: int                   # 総マッチ数


@dataclass
class ProjectContext:
    """プロジェクト文脈情報"""
    project_type: str                    # プロジェクトタイプ
    main_languages: List[str]            # 主要言語
    frameworks: List[str]                # 使用フレームワーク
    architecture_pattern: str           # アーキテクチャパターン
    key_directories: List[str]           # 重要ディレクトリ
    recent_changes: List[str]            # 最近の変更


@dataclass
class RiskAssessment:
    """リスク評価結果"""
    overall_risk: RiskLevel              # 総合リスクレベル
    risk_factors: List[str]              # リスク要因
    mitigation_measures: List[str]       # 軽減策
    approval_required: bool              # 承認必要性
    reasoning: str                       # 評価理由


@dataclass
class ApprovalStatus:
    """承認状況"""
    requested: bool                      # 承認要求有無
    granted: bool                        # 承認取得有無
    timestamp: datetime                  # 承認日時
    approval_message: str                # 承認メッセージ
    conditions: List[str] = field(default_factory=list)  # 承認条件


@dataclass
class ToolResult:
    """ツール実行結果"""
    tool_name: str                       # ツール名
    success: bool                        # 実行成功有無
    output: str                          # 出力結果
    error_message: Optional[str] = None  # エラーメッセージ
    execution_time: float = 0.0          # 実行時間


@dataclass
class ExecutionError:
    """実行エラー情報"""
    error_type: str                      # エラータイプ
    message: str                         # エラーメッセージ
    file_path: Optional[str] = None      # エラー発生ファイル
    line_number: Optional[int] = None    # エラー発生行
    stack_trace: Optional[str] = None    # スタックトレース


@dataclass
class ErrorAnalysis:
    """エラー分析結果"""
    root_cause: str                      # 根本原因
    suggested_fixes: List[str]           # 修正提案
    confidence: float                    # 分析信頼度
    similar_patterns: List[str]          # 類似パターン
    prevention_measures: List[str]       # 予防策


@dataclass
class TaskStep:
    """タスクステップ"""
    step_id: str                         # ステップID
    user_message: str                    # ユーザーメッセージ
    timestamp: datetime                  # タイムスタンプ
    context: Dict[str, Any] = field(default_factory=dict)  # 文脈情報


@dataclass
class RetryContext:
    """再試行文脈"""
    retry_count: int                     # 再試行回数
    previous_errors: List[ExecutionError] # 前回のエラー
    failure_analysis: ErrorAnalysis      # 失敗分析
    modified_plan: Optional[ExecutionPlan] = None  # 修正された計画


@dataclass
class NodeExecution:
    """ノード実行記録"""
    node_name: str                       # ノード名
    timestamp: datetime                  # 実行時刻
    input_summary: str                   # 入力概要
    output_summary: str                  # 出力概要
    key_decisions: List[str]             # 主要決定事項
    confidence_score: float              # 信頼度スコア
    execution_time: float = 0.0          # 実行時間


@dataclass
class UnderstandingResult:
    """理解・計画ノードの出力"""
    requirement_analysis: str            # 要求分析結果
    execution_plan: ExecutionPlan        # 実行計画
    identified_risks: List[str]          # 特定されたリスク
    information_needs: List[str]         # 必要な情報
    confidence: float                    # 理解信頼度
    complexity_assessment: str           # 複雑度評価
    # 5ノードアーキテクチャ用の新フィールド
    task_profile_type: Optional[Any] = None      # TaskProfileType (циркулярインポート回避のためAny)
    content_structure_plan: Dict[str, Any] = field(default_factory=dict)  # コンテンツ構造計画
    extracted_targets: List[str] = field(default_factory=list)  # 抽出されたターゲット


@dataclass
class GatheredInfo:
    """情報収集ノードの出力"""
    collected_files: Dict[str, FileContent]  # 収集ファイル
    rag_results: List[RAGResult]         # RAG検索結果
    project_context: ProjectContext      # プロジェクト文脈
    confidence_scores: Dict[str, float]  # 信頼度スコア
    information_gaps: List[str]          # 情報不足箇所
    collection_strategy: str             # 収集戦略


@dataclass
class ExecutionResult:
    """安全実行ノードの出力"""
    risk_assessment: RiskAssessment      # リスク評価
    approval_status: ApprovalStatus      # 承認状況
    tool_results: List[ToolResult]       # ツール実行結果
    execution_errors: List[ExecutionError]  # 実行エラー
    partial_success: bool                # 部分的成功
    rollback_info: Optional[Dict[str, Any]] = None  # ロールバック情報


@dataclass
class EvaluationResult:
    """評価・継続ノードの出力 (5ノードアーキテクチャ強化版)"""
    # 基本評価情報
    overall_quality_score: float         # 総合品質スコア (0.0-1.0)
    task_completion_status: str          # タスク完了状況
    identified_issues: List[str]         # 特定された問題
    
    # 次アクション決定
    recommended_next_action: NextAction  # 推奨次アクション
    confidence_in_recommendation: float # 推奨への信頼度
    reasoning: str                       # 判定理由
    
    # Duck Vitals System 統合
    duck_vitals_assessment: Dict[str, float] = field(default_factory=dict)  # バイタル評価
    
    # 5ノードアーキテクチャ専用
    response_generation_readiness: bool = False   # 応答生成準備完了
    template_data_completeness: float = 0.0       # テンプレートデータ完全性
    quality_gate_passed: bool = False             # 品質ゲート通過
    
    # 従来互換性
    success_status: bool = True                   # 成功ステータス
    completion_percentage: float = 0.0            # 完了率
    quality_assessment: str = ""                  # 品質評価
    user_satisfaction_prediction: float = 0.0    # ユーザー満足度予測
    error_analysis: Optional[ErrorAnalysis] = None  # エラー分析
    continuation_plan: Optional[ExecutionPlan] = None  # 継続計画


@dataclass
class FourNodePromptContext:
    """4ノード対応の文脈継承PromptContext"""
    
    # 🎯 ノード識別情報
    current_node: NodeType               # 現在のノード
    execution_phase: int                 # 実行フェーズ（再試行対応）
    
    # 📂 基本情報
    workspace_path: Path                 # ワークスペースパス
    current_task: Optional[str] = None   # 現在のタスク
    operation_type: str = "chat"         # タスク種別（拡張版）
    
    # 📊 段階別蓄積情報
    understanding: Optional[UnderstandingResult] = None    # 1️⃣の結果
    gathered_info: Optional[GatheredInfo] = None          # 2️⃣の結果  
    execution_result: Optional[ExecutionResult] = None    # 3️⃣の結果
    evaluation: Optional[EvaluationResult] = None         # 4️⃣の結果
    
    # 🔄 継続性情報
    task_chain: List[TaskStep] = field(default_factory=list)  # タスクの連鎖
    retry_context: Optional[RetryContext] = None              # 再試行時の文脈
    execution_history: List[NodeExecution] = field(default_factory=list)  # 実行履歴
    
    # 💭 記憶・対話情報
    recent_messages: List[ConversationMessage] = field(default_factory=list)  # 直近メッセージ
    memory_summary: Optional[str] = None         # 記憶要約
    
    # ⚙️ 動的設定
    token_budget: int = 6000             # トークン予算（4ノードで増量）
    node_priorities: Dict[str, float] = field(default_factory=dict)  # ノード優先度
    compression_strategy: str = "importance_based"  # 圧縮戦略
    
    # 🛡️ 安全性・品質
    safety_flags: Dict[str, bool] = field(default_factory=dict)  # 安全性フラグ
    quality_thresholds: Dict[str, float] = field(default_factory=dict)  # 品質閾値

    def get_current_phase_info(self) -> str:
        """現在のフェーズ情報を取得"""
        phase_names = {
            NodeType.UNDERSTANDING: "要求理解・計画立案",
            NodeType.GATHERING: "情報収集・文脈構築", 
            NodeType.EXECUTION: "安全実行・承認",
            NodeType.EVALUATION: "結果評価・継続判断"
        }
        return f"{phase_names.get(self.current_node, '不明')} (Phase {self.execution_phase})"
    
    def has_previous_results(self, node: NodeType) -> bool:
        """指定ノードの実行結果が存在するか確認"""
        result_map = {
            NodeType.UNDERSTANDING: self.understanding,
            NodeType.GATHERING: self.gathered_info,
            NodeType.EXECUTION: self.execution_result, 
            NodeType.EVALUATION: self.evaluation
        }
        return result_map.get(node) is not None
    
    def get_token_allocation(self) -> Dict[str, int]:
        """ノードごとのトークン配分を計算"""
        base_allocation = {
            NodeType.UNDERSTANDING: self.token_budget // 4,    # 25%
            NodeType.GATHERING: self.token_budget // 2,        # 50% (情報量多い)
            NodeType.EXECUTION: self.token_budget // 6,        # 16%
            NodeType.EVALUATION: self.token_budget // 12       # 8%
        }
        
        # 優先度に基づく調整
        if self.node_priorities:
            for node_type, priority in self.node_priorities.items():
                if hasattr(NodeType, node_type.upper()):
                    node = NodeType[node_type.upper()]
                    base_allocation[node] = int(base_allocation[node] * priority)
        
        return {node.value: allocation for node, allocation in base_allocation.items()}
    
    def should_request_approval(self) -> bool:
        """承認が必要かどうかを判定"""
        if self.execution_result and self.execution_result.risk_assessment:
            risk_level = self.execution_result.risk_assessment.overall_risk
            return risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]
        return False
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """実行サマリーを取得"""
        return {
            "phase": self.get_current_phase_info(),
            "completed_nodes": [node.value for node in NodeType if self.has_previous_results(node)],
            "retry_count": self.retry_context.retry_count if self.retry_context else 0,
            "total_executions": len(self.execution_history),
            "token_usage": self.get_token_allocation(),
            "safety_status": self.safety_flags
        }