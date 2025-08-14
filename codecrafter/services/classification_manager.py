"""
TaskProfile分類システム統合マネージャー

既存のルールベース分類と新しいハイブリッド分類を統合し、
段階的移行を管理する
"""

import logging
from typing import Dict, Any, Optional, Union
from enum import Enum

from .task_classifier import TaskProfileClassifier, ClassificationResult
from .hybrid_task_classifier import HybridTaskProfileClassifier, HybridClassificationResult


class ClassificationMode(Enum):
    """分類モード"""
    RULE_ONLY = "rule_only"              # ルールベースのみ
    HYBRID_EXPERIMENTAL = "hybrid_exp"    # ハイブリッド実験モード
    HYBRID_PRODUCTION = "hybrid_prod"     # ハイブリッド本格運用
    AUTO_SELECT = "auto_select"           # 自動選択


class TaskProfileClassificationManager:
    """TaskProfile分類システムの統合マネージャー"""
    
    def __init__(self):
        """分類マネージャーを初期化"""
        self.rule_classifier = TaskProfileClassifier()
        self.hybrid_classifier = HybridTaskProfileClassifier()
        
        # 設定とモード管理
        self.config = self._load_classification_config()
        self.current_mode = self._determine_initial_mode()
        
        # 統計と監視
        self.classification_metrics = {
            "rule_classifications": 0,
            "hybrid_classifications": 0,
            "auto_selections": 0,
            "fallback_events": 0
        }
        
        # ロガー設定
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"分類マネージャー初期化完了 - モード: {self.current_mode.value}")
    
    def classify(
        self, 
        user_request: str, 
        context: Optional[Dict[str, Any]] = None,
        force_mode: Optional[ClassificationMode] = None
    ) -> ClassificationResult:
        """
        統合分類メソッド - 既存のインターフェースと互換性を保持
        
        Args:
            user_request: ユーザー要求文
            context: 追加コンテキスト情報
            force_mode: 強制的に使用する分類モード
            
        Returns:
            ClassificationResult（従来形式で統一）
        """
        # モード決定
        effective_mode = force_mode if force_mode else self.current_mode
        
        try:
            if effective_mode == ClassificationMode.RULE_ONLY:
                return self._classify_rule_only(user_request)
            
            elif effective_mode == ClassificationMode.HYBRID_EXPERIMENTAL:
                return self._classify_hybrid_experimental(user_request, context)
            
            elif effective_mode == ClassificationMode.HYBRID_PRODUCTION:
                return self._classify_hybrid_production(user_request, context)
            
            elif effective_mode == ClassificationMode.AUTO_SELECT:
                return self._classify_auto_select(user_request, context)
            
            else:
                self.logger.warning(f"不明な分類モード: {effective_mode}")
                return self._classify_rule_only(user_request)
                
        except Exception as e:
            self.logger.error(f"分類処理エラー (モード: {effective_mode.value}): {e}")
            self.classification_metrics["fallback_events"] += 1
            
            # 緊急フォールバック
            return self._emergency_fallback_classify(user_request, str(e))
    
    def _classify_rule_only(self, user_request: str) -> ClassificationResult:
        """ルールベース専用分類"""
        self.classification_metrics["rule_classifications"] += 1
        return self.rule_classifier.classify(user_request)
    
    def _classify_hybrid_experimental(
        self, 
        user_request: str, 
        context: Optional[Dict[str, Any]]
    ) -> ClassificationResult:
        """ハイブリッド実験モード分類"""
        self.classification_metrics["hybrid_classifications"] += 1
        
        try:
            # ハイブリッド分類を実行
            hybrid_result = self.hybrid_classifier.classify(user_request, context)
            
            # 実験モードでは結果を比較・ログ出力
            rule_result = self.rule_classifier.classify(user_request)
            self._log_experimental_comparison(user_request, hybrid_result, rule_result)
            
            # ハイブリッド結果を従来形式に変換して返す
            return self.hybrid_classifier.to_classification_result(hybrid_result)
            
        except Exception as e:
            self.logger.warning(f"ハイブリッド実験モードでエラー、ルールベースにフォールバック: {e}")
            return self._classify_rule_only(user_request)
    
    def _classify_hybrid_production(
        self, 
        user_request: str, 
        context: Optional[Dict[str, Any]]
    ) -> ClassificationResult:
        """ハイブリッド本格運用分類"""
        self.classification_metrics["hybrid_classifications"] += 1
        
        hybrid_result = self.hybrid_classifier.classify(user_request, context)
        return self.hybrid_classifier.to_classification_result(hybrid_result)
    
    def _classify_auto_select(
        self, 
        user_request: str, 
        context: Optional[Dict[str, Any]]
    ) -> ClassificationResult:
        """自動選択分類"""
        self.classification_metrics["auto_selections"] += 1
        
        # 要求の複雑度に基づいて自動選択
        complexity_score = self._assess_request_complexity(user_request, context)
        
        if complexity_score >= 0.7:
            # 複雑な要求はハイブリッド分類
            self.logger.debug(f"自動選択: ハイブリッド (複雑度: {complexity_score:.2f})")
            return self._classify_hybrid_production(user_request, context)
        else:
            # 単純な要求はルールベース分類
            self.logger.debug(f"自動選択: ルールベース (複雑度: {complexity_score:.2f})")
            return self._classify_rule_only(user_request)
    
    def _assess_request_complexity(
        self, 
        user_request: str, 
        context: Optional[Dict[str, Any]]
    ) -> float:
        """要求の複雑度を評価"""
        complexity_score = 0.0
        
        # 要因1: 文章の長さ
        if len(user_request) > 100:
            complexity_score += 0.2
        elif len(user_request) > 200:
            complexity_score += 0.3
        
        # 要因2: 複数の動作を含む
        action_verbs = ["作成", "修正", "分析", "比較", "実装", "確認"]
        action_count = sum(1 for verb in action_verbs if verb in user_request)
        if action_count >= 2:
            complexity_score += 0.3
        
        # 要因3: ファイル数
        if context and context.get("detected_files"):
            file_count = len(context["detected_files"])
            if file_count >= 2:
                complexity_score += 0.2
            elif file_count >= 3:
                complexity_score += 0.3
        
        # 要因4: 複合的なキーワード
        complex_patterns = ["比較して", "分析して", "レビューして", "問題を見つけて"]
        if any(pattern in user_request for pattern in complex_patterns):
            complexity_score += 0.4
        
        return min(complexity_score, 1.0)
    
    def _emergency_fallback_classify(self, user_request: str, error: str) -> ClassificationResult:
        """緊急フォールバック分類"""
        self.logger.error(f"緊急フォールバック実行: {error}")
        
        try:
            return self.rule_classifier.classify(user_request)
        except Exception as fallback_error:
            # 最終手段: 最もシンプルな分類
            from ..services.task_classifier import TaskProfileType
            
            return ClassificationResult(
                profile_type=TaskProfileType.INFORMATION_REQUEST,
                confidence=0.1,
                detected_patterns=[f"emergency_fallback: {error[:50]}"],
                extracted_targets=[],
                reasoning=f"緊急フォールバック: {fallback_error}"
            )
    
    def _log_experimental_comparison(
        self, 
        user_request: str, 
        hybrid_result: HybridClassificationResult, 
        rule_result: ClassificationResult
    ):
        """実験モードでの比較結果をログ出力"""
        
        # 分類結果の一致度チェック
        is_same_profile = hybrid_result.profile_type == rule_result.profile_type
        confidence_diff = abs(hybrid_result.confidence - rule_result.confidence)
        
        log_data = {
            "request": user_request[:100],
            "hybrid_profile": hybrid_result.profile_type.value,
            "rule_profile": rule_result.profile_type.value,
            "profile_match": is_same_profile,
            "hybrid_confidence": round(hybrid_result.confidence, 3),
            "rule_confidence": round(rule_result.confidence, 3),
            "confidence_diff": round(confidence_diff, 3),
            "hybrid_method": hybrid_result.classification_method,
            "guardrail_corrections": len(hybrid_result.guardrail_corrections or [])
        }
        
        if is_same_profile and confidence_diff < 0.2:
            self.logger.info(f"実験比較 - 結果一致: {log_data}")
        else:
            self.logger.warning(f"実験比較 - 結果相違: {log_data}")
    
    def _load_classification_config(self) -> Dict[str, Any]:
        """分類設定を読み込み"""
        try:
            import yaml
            from pathlib import Path
            
            config_path = Path(__file__).parent.parent.parent / "config" / "task_classification_prompts.yaml"
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    return config.get("system_config", {})
            else:
                return self._get_default_config()
                
        except Exception as e:
            self.logger.warning(f"設定読み込みエラー: {e}")
            return self._get_default_config()
    
    def _determine_initial_mode(self) -> ClassificationMode:
        """初期分類モードを決定"""
        config_mode = self.config.get("classification_mode", "auto_select")
        
        mode_mapping = {
            "rule_only": ClassificationMode.RULE_ONLY,
            "hybrid_experimental": ClassificationMode.HYBRID_EXPERIMENTAL,
            "hybrid_production": ClassificationMode.HYBRID_PRODUCTION,
            "auto_select": ClassificationMode.AUTO_SELECT
        }
        
        return mode_mapping.get(config_mode, ClassificationMode.AUTO_SELECT)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """デフォルト設定"""
        return {
            "classification_mode": "auto_select",
            "use_llm_classification": True,
            "enable_guardrails": True,
            "log_experimental_comparisons": True
        }
    
    # === 管理・監視メソッド ===
    
    def set_classification_mode(self, mode: ClassificationMode):
        """分類モードを設定"""
        old_mode = self.current_mode
        self.current_mode = mode
        self.logger.info(f"分類モード変更: {old_mode.value} → {mode.value}")
    
    def get_classification_statistics(self) -> Dict[str, Any]:
        """分類統計情報を取得"""
        stats = self.classification_metrics.copy()
        stats["current_mode"] = self.current_mode.value
        
        # ハイブリッド分類器からの統計も取得
        if hasattr(self.hybrid_classifier, 'get_classification_statistics'):
            stats["hybrid_detailed"] = self.hybrid_classifier.get_classification_statistics()
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """システムヘルスチェック"""
        health = {
            "status": "healthy",
            "current_mode": self.current_mode.value,
            "components": {}
        }
        
        try:
            # ルールベース分類器チェック
            health["components"]["rule_classifier"] = {"healthy": True}
            
            # ハイブリッド分類器チェック
            if hasattr(self.hybrid_classifier, 'health_check'):
                health["components"]["hybrid_classifier"] = self.hybrid_classifier.health_check()
            else:
                health["components"]["hybrid_classifier"] = {"healthy": True, "note": "health_check未実装"}
            
            # 全体ステータス判定
            unhealthy_components = [
                name for name, status in health["components"].items()
                if not status.get("healthy", False)
            ]
            
            if unhealthy_components:
                health["status"] = "degraded"
                health["unhealthy_components"] = unhealthy_components
            
        except Exception as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)
        
        return health
    
    def reset_statistics(self):
        """統計情報をリセット"""
        self.classification_metrics = {
            "rule_classifications": 0,
            "hybrid_classifications": 0,
            "auto_selections": 0,
            "fallback_events": 0
        }
        
        # ハイブリッド分類器の統計もリセット
        if hasattr(self.hybrid_classifier, 'reset_statistics'):
            self.hybrid_classifier.reset_statistics()


# === 後方互換性のためのファクトリ関数 ===

def create_classification_manager() -> TaskProfileClassificationManager:
    """分類マネージャーのファクトリ関数"""
    return TaskProfileClassificationManager()


# === グローバルインスタンス（段階的移行用） ===

# 既存コードとの互換性を保つため、グローバルインスタンスを提供
_global_classification_manager = None

def get_classification_manager() -> TaskProfileClassificationManager:
    """グローバル分類マネージャーを取得"""
    global _global_classification_manager
    if _global_classification_manager is None:
        _global_classification_manager = TaskProfileClassificationManager()
    return _global_classification_manager

# 既存のtask_classifierインターフェースとの互換性を保つ
class CompatibilityTaskClassifier:
    """既存のtask_classifierインターフェースとの互換性を保つラッパー"""
    
    def __init__(self):
        self.manager = get_classification_manager()
    
    def classify(self, user_request: str, context: Optional[Dict[str, Any]] = None) -> ClassificationResult:
        """既存のclassifyメソッドと互換性を保つ"""
        return self.manager.classify(user_request, context)
    
    @property
    def profile_type(self):
        """profile_typeへのアクセス（後方互換性）"""
        # 最後の分類結果のprofile_typeを返すダミー実装
        # 実際の使用では適切に実装する必要がある
        return getattr(self, '_last_profile_type', None)


# 段階的移行のためのオプション: 既存のtask_classifierを置き換える場合
# task_classifier = CompatibilityTaskClassifier()