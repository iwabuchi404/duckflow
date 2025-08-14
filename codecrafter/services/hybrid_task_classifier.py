"""
ハイブリッドTaskProfile分類システム

LLM分類 + ガードレール + ルールベースフォールバックの統合システム
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from .task_classifier import TaskProfileClassifier, ClassificationResult, TaskProfileType
from .llm_service import llm_service
from .task_profile_guardrail import task_profile_guardrail, confidence_adjuster


@dataclass
class HybridClassificationResult:
    """ハイブリッド分類の詳細結果"""
    profile_type: TaskProfileType
    confidence: float
    reasoning: str
    detected_patterns: List[str]
    extracted_targets: List[str]
    
    # ハイブリッド固有情報
    classification_method: str  # "llm", "rule", "hybrid"
    llm_result: Optional[Dict[str, Any]] = None
    rule_result: Optional[ClassificationResult] = None
    guardrail_corrections: Optional[List[Dict[str, Any]]] = None
    confidence_adjustments: Optional[Dict[str, float]] = None
    fallback_reason: Optional[str] = None


class HybridTaskProfileClassifier:
    """LLM + ガードレール + ルールベースのハイブリッド分類システム"""
    
    def __init__(self):
        """ハイブリッド分類システムを初期化"""
        self.llm_service = llm_service
        self.guardrail = task_profile_guardrail
        self.confidence_adjuster = confidence_adjuster
        self.fallback_classifier = TaskProfileClassifier()  # 既存のルールベース
        
        # 統計情報
        self.classification_stats = {
            "total_classifications": 0,
            "llm_success": 0,
            "rule_fallback": 0,
            "hybrid_merge": 0,
            "guardrail_corrections": 0
        }
        
        # 設定読み込み
        self.config = self._load_hybrid_config()
        
        # ロガー設定
        self.logger = logging.getLogger(__name__)
    
    def classify(
        self, 
        user_request: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> HybridClassificationResult:
        """
        ハイブリッド分類の実行
        
        Args:
            user_request: ユーザー要求文
            context: 追加コンテキスト情報
            
        Returns:
            ハイブリッド分類結果
        """
        self.classification_stats["total_classifications"] += 1
        start_time = datetime.now()
        
        try:
            # 設定チェック
            if not self.config.get("use_llm_classification", True):
                # LLM分類が無効の場合はルールベースのみ
                return self._classify_rule_only(user_request, context)
            
            # Step 1: LLM分類の実行
            llm_result = None
            try:
                llm_result = self.llm_service.classify_task_profile(user_request, context or {})
                
                # Step 2: ガードレール検証・修正
                if self.config.get("enable_guardrails", True):
                    validated_result = self.guardrail.validate_and_correct(
                        user_request, llm_result, context or {}
                    )
                    
                    if validated_result.get("guardrail_corrections"):
                        self.classification_stats["guardrail_corrections"] += 1
                else:
                    validated_result = llm_result
                
                # Step 3: 信頼度の動的調整
                base_confidence = validated_result.get("confidence", 0.5)
                adjusted_confidence = self.confidence_adjuster.adjust_confidence(
                    base_confidence, user_request, context or {}
                )
                
                confidence_adjustments = {
                    "original": base_confidence,
                    "adjusted": adjusted_confidence,
                    "adjustment_factor": adjusted_confidence / base_confidence if base_confidence > 0 else 1.0
                }
                
                # Step 4: 低信頼度の場合はハイブリッド処理
                llm_confidence_threshold = self.config.get("llm_confidence_threshold", 0.6)
                
                if adjusted_confidence < llm_confidence_threshold:
                    if self.config.get("fallback_to_rules", True):
                        return self._hybrid_merge_classification(
                            user_request, validated_result, adjusted_confidence, 
                            confidence_adjustments, context
                        )
                
                # Step 5: LLM分類成功
                self.classification_stats["llm_success"] += 1
                
                return self._build_hybrid_result(
                    validated_result, adjusted_confidence, confidence_adjustments,
                    method="llm", llm_result=validated_result
                )
                
            except Exception as llm_error:
                self.logger.warning(f"LLM分類エラー: {llm_error}")
                
                if not self.config.get("fallback_to_rules", True):
                    raise llm_error
                
                # Step 6: 完全フォールバック
                return self._classify_with_fallback(
                    user_request, context, str(llm_error), llm_result
                )
                
        except Exception as e:
            self.logger.error(f"ハイブリッド分類エラー: {e}")
            # 緊急フォールバック
            return self._emergency_fallback_classification(user_request, str(e))
        finally:
            # 処理時間記録
            processing_time = (datetime.now() - start_time).total_seconds()
            self.logger.debug(f"分類処理時間: {processing_time:.3f}秒")
    
    def _classify_rule_only(
        self, 
        user_request: str, 
        context: Optional[Dict[str, Any]]
    ) -> HybridClassificationResult:
        """ルールベース専用分類"""
        rule_result = self.fallback_classifier.classify(user_request)
        
        return HybridClassificationResult(
            profile_type=rule_result.profile_type,
            confidence=rule_result.confidence,
            reasoning=rule_result.reasoning,
            detected_patterns=rule_result.detected_patterns,
            extracted_targets=rule_result.extracted_targets,
            classification_method="rule",
            rule_result=rule_result,
            fallback_reason="LLM分類が設定で無効化されています"
        )
    
    def _hybrid_merge_classification(
        self,
        user_request: str,
        llm_result: Dict[str, Any],
        llm_confidence: float,
        confidence_adjustments: Dict[str, float],
        context: Optional[Dict[str, Any]]
    ) -> HybridClassificationResult:
        """LLM結果とルールベース結果のマージ"""
        
        # ルールベース分類を実行
        rule_result = self.fallback_classifier.classify(user_request)
        
        self.classification_stats["hybrid_merge"] += 1
        
        # より高い信頼度の結果を採用
        if llm_confidence >= rule_result.confidence:
            final_profile = TaskProfileType(llm_result["profile_type"])
            final_confidence = llm_confidence
            final_reasoning = f"LLMハイブリッド採用 (信頼度: {llm_confidence:.2f}): {llm_result.get('reasoning', '')}"
            classification_method = "hybrid_llm_primary"
        else:
            final_profile = rule_result.profile_type
            final_confidence = rule_result.confidence
            final_reasoning = f"ルールベースハイブリッド採用 (信頼度: {rule_result.confidence:.2f}): {rule_result.reasoning}"
            classification_method = "hybrid_rule_primary"
        
        return HybridClassificationResult(
            profile_type=final_profile,
            confidence=final_confidence,
            reasoning=final_reasoning,
            detected_patterns=[f"hybrid_merge: LLM={llm_confidence:.2f}, Rule={rule_result.confidence:.2f}"],
            extracted_targets=rule_result.extracted_targets,
            classification_method=classification_method,
            llm_result=llm_result,
            rule_result=rule_result,
            guardrail_corrections=llm_result.get("guardrail_corrections"),
            confidence_adjustments=confidence_adjustments
        )
    
    def _classify_with_fallback(
        self,
        user_request: str,
        context: Optional[Dict[str, Any]],
        error_message: str,
        partial_llm_result: Optional[Dict[str, Any]]
    ) -> HybridClassificationResult:
        """エラー時のフォールバック分類"""
        
        rule_result = self.fallback_classifier.classify(user_request)
        self.classification_stats["rule_fallback"] += 1
        
        return HybridClassificationResult(
            profile_type=rule_result.profile_type,
            confidence=rule_result.confidence * 0.9,  # フォールバックペナルティ
            reasoning=f"フォールバック分類: {rule_result.reasoning}",
            detected_patterns=rule_result.detected_patterns + [f"llm_fallback: {error_message[:50]}"],
            extracted_targets=rule_result.extracted_targets,
            classification_method="rule_fallback",
            rule_result=rule_result,
            llm_result=partial_llm_result,
            fallback_reason=error_message
        )
    
    def _emergency_fallback_classification(
        self, 
        user_request: str, 
        error_message: str
    ) -> HybridClassificationResult:
        """緊急フォールバック分類"""
        
        # 最もシンプルなキーワード分類
        request_lower = user_request.lower()
        
        if any(kw in request_lower for kw in ["作成", "実装", "書いて"]):
            profile_type = TaskProfileType.CREATION_REQUEST
        elif any(kw in request_lower for kw in ["修正", "変更", "直して"]):
            profile_type = TaskProfileType.MODIFICATION_REQUEST
        elif any(kw in request_lower for kw in ["分析", "レビュー", "評価"]):
            profile_type = TaskProfileType.ANALYSIS_REQUEST
        elif any(kw in request_lower for kw in ["探して", "検索", "見つけて"]):
            profile_type = TaskProfileType.SEARCH_REQUEST
        else:
            profile_type = TaskProfileType.INFORMATION_REQUEST  # デフォルト
        
        return HybridClassificationResult(
            profile_type=profile_type,
            confidence=0.3,  # 緊急フォールバックは低信頼度
            reasoning=f"緊急フォールバック分類: {profile_type.value}",
            detected_patterns=[f"emergency_fallback: {error_message[:50]}"],
            extracted_targets=[],
            classification_method="emergency_fallback",
            fallback_reason=error_message
        )
    
    def _build_hybrid_result(
        self,
        llm_result: Dict[str, Any],
        confidence: float,
        confidence_adjustments: Dict[str, float],
        method: str = "llm",
        **kwargs
    ) -> HybridClassificationResult:
        """ハイブリッド結果オブジェクトの構築"""
        
        return HybridClassificationResult(
            profile_type=TaskProfileType(llm_result["profile_type"]),
            confidence=confidence,
            reasoning=llm_result.get("reasoning", ""),
            detected_patterns=llm_result.get("guardrail_corrections", []),
            extracted_targets=self._extract_targets_from_llm(llm_result),
            classification_method=method,
            confidence_adjustments=confidence_adjustments,
            guardrail_corrections=llm_result.get("guardrail_corrections"),
            **kwargs
        )
    
    def _extract_targets_from_llm(self, llm_result: Dict[str, Any]) -> List[str]:
        """LLM結果から対象を抽出"""
        # LLM結果に含まれる可能性のある対象情報を抽出
        # 現在は基本的な実装のみ
        detected_intent = llm_result.get("detected_intent", "")
        suggested_approach = llm_result.get("suggested_approach", "")
        
        targets = []
        
        # 簡単なファイル名抽出
        import re
        file_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z]{1,4})'
        
        for text in [detected_intent, suggested_approach]:
            matches = re.findall(file_pattern, text)
            targets.extend(matches)
        
        return list(set(targets))  # 重複除去
    
    def _load_hybrid_config(self) -> Dict[str, Any]:
        """ハイブリッド設定を読み込み"""
        try:
            import yaml
            from pathlib import Path
            
            config_path = Path(__file__).parent.parent.parent / "config" / "task_classification_prompts.yaml"
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    return config.get("system_config", {})
            else:
                return self._get_default_hybrid_config()
                
        except Exception as e:
            self.logger.warning(f"ハイブリッド設定読み込みエラー: {e}")
            return self._get_default_hybrid_config()
    
    def _get_default_hybrid_config(self) -> Dict[str, Any]:
        """デフォルトハイブリッド設定"""
        return {
            "use_llm_classification": True,
            "llm_confidence_threshold": 0.6,
            "enable_guardrails": True,
            "fallback_to_rules": True,
            "llm_timeout_seconds": 5,
            "log_classification_details": True
        }
    
    # === 互換性メソッド ===
    
    def to_classification_result(
        self, 
        hybrid_result: HybridClassificationResult
    ) -> ClassificationResult:
        """ハイブリッド結果を従来のClassificationResultに変換"""
        return ClassificationResult(
            profile_type=hybrid_result.profile_type,
            confidence=hybrid_result.confidence,
            detected_patterns=hybrid_result.detected_patterns,
            extracted_targets=hybrid_result.extracted_targets,
            reasoning=hybrid_result.reasoning
        )
    
    # === 統計・診断メソッド ===
    
    def get_classification_statistics(self) -> Dict[str, Any]:
        """分類統計情報を取得"""
        stats = self.classification_stats.copy()
        
        if stats["total_classifications"] > 0:
            stats["llm_success_rate"] = stats["llm_success"] / stats["total_classifications"]
            stats["rule_fallback_rate"] = stats["rule_fallback"] / stats["total_classifications"]
            stats["hybrid_merge_rate"] = stats["hybrid_merge"] / stats["total_classifications"]
        else:
            stats.update({
                "llm_success_rate": 0.0,
                "rule_fallback_rate": 0.0,
                "hybrid_merge_rate": 0.0
            })
        
        # ガードレール統計を追加
        if hasattr(self.guardrail, 'get_correction_statistics'):
            stats["guardrail_stats"] = self.guardrail.get_correction_statistics()
        
        return stats
    
    def reset_statistics(self):
        """統計情報をリセット"""
        self.classification_stats = {
            "total_classifications": 0,
            "llm_success": 0,
            "rule_fallback": 0,
            "hybrid_merge": 0,
            "guardrail_corrections": 0
        }
    
    def health_check(self) -> Dict[str, Any]:
        """システムヘルスチェック"""
        health = {"status": "healthy", "issues": []}
        
        try:
            # 設定チェック
            config_status = self._check_configuration_health()
            health["config"] = config_status
            
            # LLMサービスチェック
            llm_status = self._check_llm_service_health()
            health["llm_service"] = llm_status
            
            # ガードレールチェック
            guardrail_status = self._check_guardrail_health()
            health["guardrail"] = guardrail_status
            
            # 全体ステータス判定
            if not all([config_status["healthy"], llm_status["healthy"], guardrail_status["healthy"]]):
                health["status"] = "degraded"
                health["issues"] = (
                    config_status.get("issues", []) +
                    llm_status.get("issues", []) +
                    guardrail_status.get("issues", [])
                )
            
        except Exception as e:
            health["status"] = "unhealthy"
            health["issues"].append(f"ヘルスチェック失敗: {e}")
        
        return health
    
    def _check_configuration_health(self) -> Dict[str, Any]:
        """設定の健全性チェック"""
        try:
            required_keys = ["use_llm_classification", "llm_confidence_threshold", "enable_guardrails"]
            missing_keys = [key for key in required_keys if key not in self.config]
            
            if missing_keys:
                return {
                    "healthy": False,
                    "issues": [f"設定キー不足: {missing_keys}"]
                }
            
            return {"healthy": True}
            
        except Exception as e:
            return {
                "healthy": False,
                "issues": [f"設定チェックエラー: {e}"]
            }
    
    def _check_llm_service_health(self) -> Dict[str, Any]:
        """LLMサービスの健全性チェック"""
        try:
            if not hasattr(self.llm_service, 'classify_task_profile'):
                return {
                    "healthy": False,
                    "issues": ["LLMServiceにclassify_task_profileメソッドが存在しません"]
                }
            
            return {"healthy": True}
            
        except Exception as e:
            return {
                "healthy": False,
                "issues": [f"LLMサービスチェックエラー: {e}"]
            }
    
    def _check_guardrail_health(self) -> Dict[str, Any]:
        """ガードレールの健全性チェック"""
        try:
            if not hasattr(self.guardrail, 'validate_and_correct'):
                return {
                    "healthy": False,
                    "issues": ["ガードレールにvalidate_and_correctメソッドが存在しません"]
                }
            
            return {"healthy": True}
            
        except Exception as e:
            return {
                "healthy": False,
                "issues": [f"ガードレールチェックエラー: {e}"]
            }


# グローバルインスタンス
hybrid_task_classifier = HybridTaskProfileClassifier()