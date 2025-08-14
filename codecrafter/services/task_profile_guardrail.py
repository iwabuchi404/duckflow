"""
TaskProfile分類ガードレールシステム

LLM分類結果の検証と修正を行い、致命的な誤分類を防止する
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from ..services.task_classifier import TaskProfileType


@dataclass
class GuardrailCorrection:
    """ガードレール修正記録"""
    original_value: str
    corrected_value: str
    correction_type: str
    reason: str
    confidence_impact: float = 0.0  # 信頼度への影響(-1.0 ~ +1.0)


class TaskProfileGuardrail:
    """LLM分類結果の検証と修正システム"""
    
    def __init__(self):
        """ガードレールシステムを初期化"""
        self.correction_history: List[GuardrailCorrection] = []
        self._load_guardrail_config()
    
    def validate_and_correct(
        self, 
        user_request: str, 
        llm_result: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        LLM分類結果を検証し、必要に応じて修正
        
        Args:
            user_request: 元のユーザー要求
            llm_result: LLMの分類結果
            context: 追加コンテキスト
            
        Returns:
            修正された分類結果（guardrail_correctionsフィールド追加）
        """
        corrected_result = llm_result.copy()
        corrections_made = []
        
        # ガードレール1: 明確な動詞パターンチェック
        verb_corrections = self._check_explicit_verb_patterns(user_request, corrected_result)
        corrections_made.extend(verb_corrections)
        
        # ガードレール2: ファイル数と範囲の整合性チェック
        if context:
            scope_corrections = self._check_file_scope_consistency(user_request, context, corrected_result)
            corrections_made.extend(scope_corrections)
        
        # ガードレール3: 否定的キーワードの強制修正
        negative_corrections = self._check_negative_keyword_override(user_request, corrected_result)
        corrections_made.extend(negative_corrections)
        
        # ガードレール4: 複合パターン検証
        compound_corrections = self._check_compound_patterns(user_request, corrected_result)
        corrections_made.extend(compound_corrections)
        
        # ガードレール5: TaskProfile間の一貫性チェック
        consistency_corrections = self._check_profile_consistency(corrected_result)
        corrections_made.extend(consistency_corrections)
        
        # 修正が行われた場合の信頼度調整
        if corrections_made:
            original_confidence = corrected_result.get("confidence", 0.5)
            
            # 修正の重要度に基づく信頼度調整
            confidence_adjustment = self._calculate_confidence_adjustment(corrections_made)
            adjusted_confidence = max(0.1, min(1.0, original_confidence * confidence_adjustment))
            
            corrected_result["confidence"] = adjusted_confidence
            corrected_result["guardrail_corrections"] = [
                {
                    "type": corr.correction_type,
                    "original": corr.original_value,
                    "corrected": corr.corrected_value,
                    "reason": corr.reason
                }
                for corr in corrections_made
            ]
            
            # 修正履歴に追加
            self.correction_history.extend(corrections_made)
        
        return corrected_result
    
    def _check_explicit_verb_patterns(
        self, 
        user_request: str, 
        result: Dict[str, Any]
    ) -> List[GuardrailCorrection]:
        """明確な動詞パターンの検証"""
        corrections = []
        request_lower = user_request.lower()
        current_profile = result.get("profile_type", "")
        
        # 作成・実装の明確な指示
        creation_verbs = self.creation_verbs
        if any(verb in request_lower for verb in creation_verbs):
            if current_profile != "CREATION_REQUEST":
                corrections.append(GuardrailCorrection(
                    original_value=current_profile,
                    corrected_value="CREATION_REQUEST",
                    correction_type="explicit_verb_override",
                    reason=f"明確な作成動詞を検出: {[v for v in creation_verbs if v in request_lower]}",
                    confidence_impact=-0.1
                ))
                result["profile_type"] = "CREATION_REQUEST"
        
        # 修正・変更の明確な指示  
        modification_verbs = self.modification_verbs
        if any(verb in request_lower for verb in modification_verbs):
            if current_profile not in ["MODIFICATION_REQUEST", "CREATION_REQUEST"]:
                corrections.append(GuardrailCorrection(
                    original_value=current_profile,
                    corrected_value="MODIFICATION_REQUEST",
                    correction_type="explicit_verb_override",
                    reason=f"明確な修正動詞を検出: {[v for v in modification_verbs if v in request_lower]}",
                    confidence_impact=-0.1
                ))
                result["profile_type"] = "MODIFICATION_REQUEST"
        
        # 分析・評価の明確な指示
        analysis_verbs = self.analysis_verbs
        if any(verb in request_lower for verb in analysis_verbs):
            # "見て"等の情報参照動詞と一緒にある場合のみ修正
            info_verbs = self.info_verbs
            has_info_verb = any(verb in request_lower for verb in info_verbs)
            
            if current_profile == "INFORMATION_REQUEST" and has_info_verb:
                corrections.append(GuardrailCorrection(
                    original_value=current_profile,
                    corrected_value="ANALYSIS_REQUEST",
                    correction_type="explicit_verb_override",
                    reason=f"分析動詞と情報動詞の組み合わせを検出: 分析が優先",
                    confidence_impact=-0.05
                ))
                result["profile_type"] = "ANALYSIS_REQUEST"
        
        return corrections
    
    def _check_file_scope_consistency(
        self, 
        user_request: str, 
        context: Dict[str, Any], 
        result: Dict[str, Any]
    ) -> List[GuardrailCorrection]:
        """ファイル範囲の整合性チェック"""
        corrections = []
        detected_files = context.get("detected_files", [])
        request_lower = user_request.lower()
        current_profile = result.get("profile_type", "")
        
        # 複数ファイルが検出されているのに単一ファイル処理の場合
        if len(detected_files) >= 2:
            comparison_keywords = ["比較", "違い", "差分", "差", "対比", "vs"]
            has_comparison = any(keyword in request_lower for keyword in comparison_keywords)
            
            if has_comparison and current_profile == "INFORMATION_REQUEST":
                corrections.append(GuardrailCorrection(
                    original_value=current_profile,
                    corrected_value="ANALYSIS_REQUEST",
                    correction_type="file_scope_consistency",
                    reason=f"複数ファイル({len(detected_files)}個)の比較要求のため、ANALYSIS_REQUESTに修正",
                    confidence_impact=-0.1
                ))
                result["profile_type"] = "ANALYSIS_REQUEST"
        
        # ファイルが全く検出されていないのに、ファイル操作を要求している場合
        if not detected_files:
            file_operation_keywords = ["ファイル", "コード", ".py", ".js", ".ts", ".md"]
            has_file_mention = any(keyword in request_lower for keyword in file_operation_keywords)
            
            if has_file_mention and current_profile in ["MODIFICATION_REQUEST", "CREATION_REQUEST"]:
                # 実際にはファイル探索が必要かもしれない
                corrections.append(GuardrailCorrection(
                    original_value=current_profile,
                    corrected_value="SEARCH_REQUEST",
                    correction_type="file_scope_consistency",
                    reason="ファイルが検出されていないため、まず検索が必要",
                    confidence_impact=-0.2
                ))
                result["profile_type"] = "SEARCH_REQUEST"
        
        return corrections
    
    def _check_negative_keyword_override(
        self, 
        user_request: str, 
        result: Dict[str, Any]
    ) -> List[GuardrailCorrection]:
        """否定的キーワードによる修正"""
        corrections = []
        request_lower = user_request.lower()
        current_profile = result.get("profile_type", "")
        
        # 「見るだけ」「表示だけ」「確認だけ」の場合
        read_only_patterns = [
            "見るだけ", "表示だけ", "確認だけ", "内容だけ", "読むだけ",
            "チェックだけ", "参照だけ", "眺めるだけ"
        ]
        
        if any(pattern in request_lower for pattern in read_only_patterns):
            if current_profile != "INFORMATION_REQUEST":
                corrections.append(GuardrailCorrection(
                    original_value=current_profile,
                    corrected_value="INFORMATION_REQUEST",
                    correction_type="negative_keyword_override",
                    reason=f"読み取り専用パターンを検出: {[p for p in read_only_patterns if p in request_lower]}",
                    confidence_impact=0.1  # この場合は信頼度を上げる
                ))
                result["profile_type"] = "INFORMATION_REQUEST"
        
        # 「説明だけ」「理解だけ」の場合
        explanation_only_patterns = ["説明だけ", "理解だけ", "教えるだけ", "知りたいだけ"]
        
        if any(pattern in request_lower for pattern in explanation_only_patterns):
            if current_profile in ["CREATION_REQUEST", "MODIFICATION_REQUEST"]:
                corrections.append(GuardrailCorrection(
                    original_value=current_profile,
                    corrected_value="INFORMATION_REQUEST",
                    correction_type="negative_keyword_override",
                    reason=f"説明専用パターンを検出: {[p for p in explanation_only_patterns if p in request_lower]}",
                    confidence_impact=0.1
                ))
                result["profile_type"] = "INFORMATION_REQUEST"
        
        return corrections
    
    def _check_compound_patterns(
        self, 
        user_request: str, 
        result: Dict[str, Any]
    ) -> List[GuardrailCorrection]:
        """複合パターンの検証"""
        corrections = []
        request_lower = user_request.lower()
        current_profile = result.get("profile_type", "")
        
        # パターン1: "レビューして改善"
        review_improve_pattern = re.search(r'(レビュー|評価).*?(改善|修正|直)', request_lower)
        if review_improve_pattern:
            if current_profile != "ANALYSIS_REQUEST":
                corrections.append(GuardrailCorrection(
                    original_value=current_profile,
                    corrected_value="ANALYSIS_REQUEST",
                    correction_type="compound_pattern",
                    reason="レビュー+改善パターン: レビューを優先して分析作業とする",
                    confidence_impact=-0.05
                ))
                result["profile_type"] = "ANALYSIS_REQUEST"
        
        # パターン2: "探して修正"
        find_fix_pattern = re.search(r'(探し|検索|見つけ).*?(修正|直し|変更)', request_lower)
        if find_fix_pattern:
            if current_profile not in ["SEARCH_REQUEST", "MODIFICATION_REQUEST"]:
                # 探すことが先にある場合は検索を優先
                corrections.append(GuardrailCorrection(
                    original_value=current_profile,
                    corrected_value="SEARCH_REQUEST",
                    correction_type="compound_pattern",
                    reason="検索+修正パターン: まず検索が必要",
                    confidence_impact=-0.1
                ))
                result["profile_type"] = "SEARCH_REQUEST"
        
        # パターン3: "分析して作成"  
        analyze_create_pattern = re.search(r'(分析|調査).*?(作成|実装|構築)', request_lower)
        if analyze_create_pattern:
            if current_profile == "CREATION_REQUEST":
                corrections.append(GuardrailCorrection(
                    original_value=current_profile,
                    corrected_value="ANALYSIS_REQUEST",
                    correction_type="compound_pattern",
                    reason="分析+作成パターン: まず分析が必要",
                    confidence_impact=-0.1
                ))
                result["profile_type"] = "ANALYSIS_REQUEST"
        
        return corrections
    
    def _check_profile_consistency(self, result: Dict[str, Any]) -> List[GuardrailCorrection]:
        """TaskProfile間の一貫性チェック"""
        corrections = []
        profile_type = result.get("profile_type", "")
        detected_intent = result.get("detected_intent", "")
        suggested_approach = result.get("suggested_approach", "")
        
        # detected_intentとprofile_typeの一貫性をチェック
        intent_profile_mapping = {
            "新規作成": "CREATION_REQUEST",
            "機能実装": "CREATION_REQUEST", 
            "ファイル作成": "CREATION_REQUEST",
            "既存修正": "MODIFICATION_REQUEST",
            "ファイル修正": "MODIFICATION_REQUEST",
            "バグ修正": "MODIFICATION_REQUEST",
            "情報参照": "INFORMATION_REQUEST",
            "内容確認": "INFORMATION_REQUEST",
            "品質分析": "ANALYSIS_REQUEST",
            "比較分析": "ANALYSIS_REQUEST",
            "問題分析": "ANALYSIS_REQUEST"
        }
        
        expected_profile = intent_profile_mapping.get(detected_intent)
        if expected_profile and expected_profile != profile_type:
            corrections.append(GuardrailCorrection(
                original_value=profile_type,
                corrected_value=expected_profile,
                correction_type="profile_consistency",
                reason=f"detected_intent '{detected_intent}' とprofile_type '{profile_type}' の不一致を修正",
                confidence_impact=-0.1
            ))
            result["profile_type"] = expected_profile
        
        return corrections
    
    def _calculate_confidence_adjustment(self, corrections: List[GuardrailCorrection]) -> float:
        """修正に基づく信頼度調整係数を計算"""
        if not corrections:
            return 1.0
        
        # 修正の重要度に基づく調整
        total_impact = sum(corr.confidence_impact for corr in corrections)
        adjustment = 1.0 + total_impact
        
        # 修正数が多い場合は追加ペナルティ
        if len(corrections) >= 3:
            adjustment *= 0.8
        elif len(corrections) >= 2:
            adjustment *= 0.9
        
        return max(0.3, min(1.2, adjustment))
    
    def _load_guardrail_config(self):
        """ガードレール設定を読み込み"""
        try:
            import yaml
            from pathlib import Path
            
            config_path = Path(__file__).parent.parent.parent / "config" / "task_classification_prompts.yaml"
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    
                guardrails_config = config.get("guardrails", {})
                verb_patterns = guardrails_config.get("explicit_verb_patterns", {})
                
                self.creation_verbs = verb_patterns.get("creation_verbs", ["作成", "実装", "構築"])
                self.modification_verbs = verb_patterns.get("modification_verbs", ["修正", "変更", "改善"])
                self.analysis_verbs = verb_patterns.get("analysis_verbs", ["分析", "レビュー", "評価"])
                self.search_verbs = verb_patterns.get("search_verbs", ["探して", "検索", "見つけて"])
                self.info_verbs = verb_patterns.get("info_verbs", ["教えて", "見て", "確認"])
                self.guidance_verbs = verb_patterns.get("guidance_verbs", ["実行", "使い方", "方法"])
                
            else:
                self._set_default_verb_patterns()
                
        except Exception as e:
            from ..ui.rich_ui import rich_ui
            rich_ui.print_warning(f"ガードレール設定読み込みエラー: {e}")
            self._set_default_verb_patterns()
    
    def _set_default_verb_patterns(self):
        """デフォルトの動詞パターンを設定"""
        self.creation_verbs = ["作成", "作って", "実装", "開発", "構築", "書いて", "生成", "追加"]
        self.modification_verbs = ["修正", "変更", "直して", "改修", "更新", "編集", "改善"]
        self.analysis_verbs = ["分析", "レビュー", "評価", "調査", "比較", "診断"]
        self.search_verbs = ["探して", "検索", "見つけて", "特定", "発見"]
        self.info_verbs = ["教えて", "見て", "表示", "確認", "内容", "読み"]
        self.guidance_verbs = ["実行", "使い方", "方法", "手順", "やり方"]
    
    def get_correction_statistics(self) -> Dict[str, Any]:
        """修正統計情報を取得"""
        if not self.correction_history:
            return {"total_corrections": 0}
        
        corrections_by_type = {}
        for correction in self.correction_history:
            correction_type = correction.correction_type
            if correction_type not in corrections_by_type:
                corrections_by_type[correction_type] = 0
            corrections_by_type[correction_type] += 1
        
        return {
            "total_corrections": len(self.correction_history),
            "corrections_by_type": corrections_by_type,
            "most_common_correction": max(corrections_by_type.items(), key=lambda x: x[1])[0] if corrections_by_type else None
        }


class ConfidenceAdjustment:
    """信頼度の動的調整システム"""
    
    def adjust_confidence(
        self, 
        base_confidence: float, 
        user_request: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """様々な要因を考慮して信頼度を調整"""
        adjusted = base_confidence
        
        # 要因1: 要求の明確度
        clarity_score = self._assess_request_clarity(user_request)
        adjusted *= clarity_score
        
        # 要因2: コンテキスト情報の豊富さ
        if context:
            context_score = self._assess_context_richness(context)
            adjusted *= context_score
        
        # 要因3: Few-Shot例との類似度
        similarity_score = self._assess_similarity_to_examples(user_request)
        adjusted *= similarity_score
        
        return max(0.1, min(1.0, adjusted))  # 0.1-1.0の範囲に制限

    def _assess_request_clarity(self, user_request: str) -> float:
        """要求の明確度評価"""
        # 長さによる評価
        if len(user_request) < 10:
            return 0.7  # 短すぎる要求は不明確
        elif len(user_request) > 200:
            return 0.9  # 詳細な要求は明確
        
        # 具体的な動詞の存在
        specific_verbs = ["作成", "修正", "分析", "比較", "実装", "説明", "確認", "教えて"]
        if any(verb in user_request for verb in specific_verbs):
            return 1.0
        
        # 疑問符や具体的な対象の存在
        if "？" in user_request or "?" in user_request:
            return 0.9
        
        # ファイル名や具体的な対象の言及
        if re.search(r'\w+\.(py|js|ts|md|json|yaml)', user_request):
            return 0.95
        
        return 0.8  # 標準的な明確度

    def _assess_context_richness(self, context: Dict[str, Any]) -> float:
        """コンテキスト情報の豊富さ評価"""
        score = 0.5  # ベーススコア
        
        if context.get("detected_files"):
            score += 0.2
        if context.get("recent_messages"):
            score += 0.2
        if context.get("workspace_manifest"):
            score += 0.1
        
        return min(1.0, score)
    
    def _assess_similarity_to_examples(self, user_request: str) -> float:
        """Few-Shot例との類似度評価（簡易版）"""
        # 共通的なパターンとの類似度をチェック
        common_patterns = [
            r"(.+)の内容を教えて",
            r"(.+)をレビューして",
            r"(.+)を作成して",
            r"(.+)を修正して",
            r"(.+)を探して",
            r"(.+)の実行方法"
        ]
        
        for pattern in common_patterns:
            if re.search(pattern, user_request):
                return 1.0
        
        return 0.8  # 標準的な類似度


# グローバルインスタンス
task_profile_guardrail = TaskProfileGuardrail()
confidence_adjuster = ConfidenceAdjustment()