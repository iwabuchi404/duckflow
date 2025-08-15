"""
Task Profile Classifier

TaskProfile分類システム
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from companion.intent_understanding.llm_intent_analyzer import LLMIntentAnalyzer, IntentAnalysis, IntentType
# LLMクライアントは動的にインポート（既存アダプターまたは新クライアント）


class TaskProfileType(Enum):
    """TaskProfileの種類"""
    INFORMATION_REQUEST = "information_request"
    ANALYSIS_REQUEST = "analysis_request"
    CREATION_REQUEST = "creation_request"
    MODIFICATION_REQUEST = "modification_request"
    SEARCH_REQUEST = "search_request"
    GUIDANCE_REQUEST = "guidance_request"


@dataclass
class TaskProfileResult:
    """TaskProfile分類結果"""
    profile_type: TaskProfileType
    confidence: float
    reasoning: str
    detected_intent: str
    complexity_assessment: str
    suggested_approach: str
    context_requirements: List[str]
    detected_targets: List[str]
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.context_requirements is None:
            self.context_requirements = []
        if self.detected_targets is None:
            self.detected_targets = []
        if self.metadata is None:
            self.metadata = {}


class RuleBasedClassifier:
    """ルールベースのフォールバック分類器"""
    
    def __init__(self):
        """ルールベース分類器を初期化"""
        self.keyword_patterns = self._load_keyword_patterns()
    
    def _load_keyword_patterns(self) -> Dict[TaskProfileType, List[str]]:
        """キーワードパターンを読み込み"""
        return {
            TaskProfileType.INFORMATION_REQUEST: [
                "見て", "教えて", "内容", "確認", "表示", "説明", "とは", "について",
                "show", "tell", "explain", "what", "how", "describe"
            ],
            TaskProfileType.ANALYSIS_REQUEST: [
                "分析", "評価", "診断", "チェック", "品質", "問題", "改善",
                "analyze", "evaluate", "check", "quality", "problem", "improve"
            ],
            TaskProfileType.CREATION_REQUEST: [
                "作成", "作って", "実装", "書いて", "構築", "新規", "追加",
                "create", "implement", "write", "build", "new", "add"
            ],
            TaskProfileType.MODIFICATION_REQUEST: [
                "修正", "変更", "改善", "直して", "更新", "編集", "調整",
                "modify", "change", "fix", "update", "edit", "adjust"
            ],
            TaskProfileType.SEARCH_REQUEST: [
                "検索", "探して", "見つけて", "調べて", "特定", "発見",
                "search", "find", "look", "discover", "locate"
            ],
            TaskProfileType.GUIDANCE_REQUEST: [
                "説明", "教えて", "案内", "手順", "方法", "相談", "アドバイス",
                "guide", "help", "advice", "how-to", "tutorial"
            ]
        }
    
    def classify(self, user_input: str) -> TaskProfileResult:
        """ルールベース分類の実行"""
        input_lower = user_input.lower()
        
        # 各TaskProfileのスコアを計算
        scores = {}
        for profile_type, keywords in self.keyword_patterns.items():
            score = sum(1 for keyword in keywords if keyword in input_lower)
            scores[profile_type] = score
        
        # 最高スコアのTaskProfileを選択
        if scores:
            best_profile = max(scores.items(), key=lambda x: x[1])
            profile_type = best_profile[0]
            confidence = min(0.8, 0.5 + (best_profile[1] * 0.1))  # 0.5-0.8の範囲
        else:
            profile_type = TaskProfileType.INFORMATION_REQUEST
            confidence = 0.5
        
        return TaskProfileResult(
            profile_type=profile_type,
            confidence=confidence,
            reasoning=f"ルールベース分類: キーワードマッチング",
            detected_intent=self._get_intent_description(profile_type),
            complexity_assessment="moderate",
            suggested_approach="基本的な処理",
            context_requirements=["基本的な情報"],
            detected_targets=[],
            metadata={"classification_method": "rule_based"}
        )
    
    def _get_intent_description(self, profile_type: TaskProfileType) -> str:
        """意図の説明を取得"""
        descriptions = {
            TaskProfileType.INFORMATION_REQUEST: "情報の確認・表示・説明",
            TaskProfileType.ANALYSIS_REQUEST: "コード・データの分析・評価",
            TaskProfileType.CREATION_REQUEST: "新規ファイル・機能の作成",
            TaskProfileType.MODIFICATION_REQUEST: "既存コード・設定の修正",
            TaskProfileType.SEARCH_REQUEST: "特定の要素・パターンの検索",
            TaskProfileType.GUIDANCE_REQUEST: "手順・方法の案内・相談"
        }
        return descriptions.get(profile_type, "意図が特定できません")


class TaskProfileClassifier:
    """TaskProfile分類システム"""
    
    def __init__(self, llm_client):
        """TaskProfile分類器を初期化"""
        self.llm_analyzer = LLMIntentAnalyzer(llm_client)
        self.rule_classifier = RuleBasedClassifier()
        self.logger = logging.getLogger(__name__)
        
        # 分類設定
        self.use_llm_classification = True
        self.llm_confidence_threshold = 0.7
        self.fallback_to_rule = True
    
    async def classify(
        self, 
        user_input: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> TaskProfileResult:
        """
        TaskProfile分類の実行
        
        Args:
            user_input: ユーザーの入力
            context: 追加コンテキスト情報
            
        Returns:
            TaskProfile分類結果
        """
        try:
            if self.use_llm_classification:
                # LLM分類を試行
                intent_analysis = await self.llm_analyzer.analyze_intent(user_input, context)
                
                # 信頼度が閾値を超えている場合
                if intent_analysis.confidence_score >= self.llm_confidence_threshold:
                    return self._convert_intent_to_task_profile(intent_analysis)
                else:
                    self.logger.info(f"LLM分類の信頼度が低い: {intent_analysis.confidence_score}")
            
            # LLM分類が失敗または信頼度が低い場合
            if self.fallback_to_rule:
                self.logger.info("ルールベース分類にフォールバック")
                return self.rule_classifier.classify(user_input)
            else:
                # フォールバックなしの場合はLLM結果を使用
                return self._convert_intent_to_task_profile(intent_analysis)
                
        except Exception as e:
            self.logger.error(f"TaskProfile分類エラー: {e}")
            
            # エラー時はルールベースにフォールバック
            if self.fallback_to_rule:
                return self.rule_classifier.classify(user_input)
            else:
                # エラー用の結果
                return TaskProfileResult(
                    profile_type=TaskProfileType.INFORMATION_REQUEST,
                    confidence=0.0,
                    reasoning=f"分類エラー: {str(e)}",
                    detected_intent="分類に失敗しました",
                    complexity_assessment="unknown",
                    suggested_approach="エラー処理",
                    context_requirements=["エラー解決"],
                    detected_targets=[],
                    metadata={"error": str(e)}
                )
    
    def _convert_intent_to_task_profile(self, intent_analysis: IntentAnalysis) -> TaskProfileResult:
        """意図分析結果をTaskProfile結果に変換"""
        
        # IntentTypeからTaskProfileTypeへのマッピング
        intent_to_profile = {
            IntentType.INFORMATION_REQUEST: TaskProfileType.INFORMATION_REQUEST,
            IntentType.ANALYSIS_REQUEST: TaskProfileType.ANALYSIS_REQUEST,
            IntentType.CREATION_REQUEST: TaskProfileType.CREATION_REQUEST,
            IntentType.MODIFICATION_REQUEST: TaskProfileType.MODIFICATION_REQUEST,
            IntentType.SEARCH_REQUEST: TaskProfileType.SEARCH_REQUEST,
            IntentType.GUIDANCE_REQUEST: TaskProfileType.GUIDANCE_REQUEST
        }
        
        profile_type = intent_to_profile.get(intent_analysis.primary_intent, TaskProfileType.INFORMATION_REQUEST)
        
        # 複雑度の変換
        complexity_map = {
            "simple": "simple",
            "moderate": "moderate", 
            "complex": "complex"
        }
        complexity = complexity_map.get(intent_analysis.execution_complexity.value, "moderate")
        
        return TaskProfileResult(
            profile_type=profile_type,
            confidence=intent_analysis.confidence_score,
            reasoning=intent_analysis.reasoning,
            detected_intent=intent_analysis.primary_intent.value,
            complexity_assessment=complexity,
            suggested_approach=intent_analysis.suggested_approach,
            context_requirements=intent_analysis.context_requirements,
            detected_targets=intent_analysis.detected_targets,
            metadata={
                "classification_method": "llm_based",
                "llm_analysis": intent_analysis.metadata
            }
        )
    
    def get_profile_description(self, profile_type: TaskProfileType) -> str:
        """TaskProfileの説明を取得"""
        descriptions = {
            TaskProfileType.INFORMATION_REQUEST: "情報要求: ファイル内容の確認、説明、表示",
            TaskProfileType.ANALYSIS_REQUEST: "分析要求: コード品質、パフォーマンス、問題の分析",
            TaskProfileType.CREATION_REQUEST: "作成要求: 新規ファイル、機能、コンポーネントの作成",
            TaskProfileType.MODIFICATION_REQUEST: "修正要求: 既存コード、設定の変更・改善",
            TaskProfileType.SEARCH_REQUEST: "検索要求: 特定の要素、パターン、ファイルの検索",
            TaskProfileType.GUIDANCE_REQUEST: "ガイダンス要求: 手順説明、ベストプラクティス、相談"
        }
        return descriptions.get(profile_type, "不明なTaskProfile")
    
    def get_profile_requirements(self, profile_type: TaskProfileType) -> List[str]:
        """TaskProfile別の要件を取得"""
        requirements = {
            TaskProfileType.INFORMATION_REQUEST: [
                "対象ファイルの特定",
                "ファイル内容の読み取り",
                "情報の整理・表示"
            ],
            TaskProfileType.ANALYSIS_REQUEST: [
                "分析対象の特定",
                "分析基準の設定",
                "結果の評価・提案"
            ],
            TaskProfileType.CREATION_REQUEST: [
                "作成仕様の明確化",
                "実装方法の決定",
                "新規ファイルの作成"
            ],
            TaskProfileType.MODIFICATION_REQUEST: [
                "修正対象の特定",
                "変更内容の決定",
                "既存ファイルの更新"
            ],
            TaskProfileType.SEARCH_REQUEST: [
                "検索条件の設定",
                "検索範囲の決定",
                "結果の整理・表示"
            ],
            TaskProfileType.GUIDANCE_REQUEST: [
                "相談内容の理解",
                "関連情報の収集",
                "適切なアドバイスの提供"
            ]
        }
        return requirements.get(profile_type, ["基本的な処理"])
    
    def set_classification_mode(self, use_llm: bool, confidence_threshold: float = 0.7):
        """分類モードを設定"""
        self.use_llm_classification = use_llm
        self.llm_confidence_threshold = max(0.0, min(1.0, confidence_threshold))
        self.logger.info(f"分類モード設定: LLM={use_llm}, 閾値={confidence_threshold}")
    
    def enable_fallback(self, enable: bool = True):
        """フォールバック機能の有効化/無効化"""
        self.fallback_to_rule = enable
        self.logger.info(f"フォールバック機能: {enable}")
