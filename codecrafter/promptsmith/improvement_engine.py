"""
改善提案エンジン

分析結果から具体的なプロンプト改善案を生成し、
複数のバリエーションを作成して安全性を検証します。
"""

import json
import yaml
import re
import statistics
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib
from pathlib import Path


@dataclass
class PromptImprovement:
    """プロンプト改善案"""
    improvement_id: str
    target_section: str      # 改善対象セクション
    improvement_type: str    # addition, modification, deletion, restructure
    current_content: str     # 現在の内容
    proposed_content: str    # 提案内容
    rationale: str          # 改善理由
    expected_impact: Dict[str, float]  # 予想される効果
    risk_level: str         # low, medium, high
    validation_status: str  # pending, approved, rejected
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class ImprovementPlan:
    """改善計画"""
    plan_id: str
    improvements: List[PromptImprovement]
    priority_order: List[str]  # improvement_idの順序
    total_expected_impact: Dict[str, float]
    implementation_strategy: str  # incremental, batch, a_b_test
    validation_requirements: List[str]


class ImprovementEngine:
    """分析結果から具体的なプロンプト改善案を生成"""
    
    def __init__(self):
        """ImprovementEngineの初期化"""
        self.improvement_templates = self._load_improvement_templates()
        self.safety_patterns = self._load_safety_patterns()
        self.impact_weights = {
            "intent_understanding_rate": 0.25,
            "code_quality_score": 0.20,
            "completeness_score": 0.20,
            "communication_clarity": 0.15,
            "error_reduction_rate": 0.10,
            "efficiency_score": 0.10
        }
    
    def generate_targeted_improvements(self, analysis: Dict) -> List[PromptImprovement]:
        """
        分析結果に基づく改善提案
        
        Args:
            analysis: 分析結果（OptimizerAIとConversationAnalyzerの結果）
            
        Returns:
            改善提案のリスト
        """
        improvements = []
        
        # 弱点パターンから改善提案を生成
        weakness_patterns = analysis.get("weakness_patterns", [])
        for weakness in weakness_patterns:
            improvement = self._generate_improvement_from_weakness(weakness)
            if improvement:
                improvements.append(improvement)
        
        # 対話分析結果から改善提案を生成（Phase 2: 拡張分析対応）
        conversation_analysis = analysis.get("conversation_analysis", {})
        improvements.extend(self._generate_improvements_from_conversation(conversation_analysis))
        
        # Phase 2: 拡張分析結果からの改善提案
        improvements.extend(self._generate_improvements_from_advanced_analysis(conversation_analysis))
        
        # 評価結果から改善提案を生成
        evaluation_results = analysis.get("evaluation_results", {})
        improvements.extend(self._generate_improvements_from_evaluation(evaluation_results))
        
        # 重複削除と優先度付け
        improvements = self._deduplicate_improvements(improvements)
        improvements = self._prioritize_improvements(improvements)
        
        return improvements
    
    def create_prompt_variations(self, base_prompt: Dict[str, str], 
                               improvements: List[PromptImprovement]) -> List[Dict[str, str]]:
        """
        複数の改善バリエーション生成
        
        Args:
            base_prompt: ベースプロンプト
            improvements: 改善案のリスト
            
        Returns:
            プロンプトバリエーションのリスト
        """
        variations = []
        
        # 単一改善版
        for improvement in improvements[:3]:  # 上位3つ
            variation = self._apply_single_improvement(base_prompt, improvement)
            variations.append({
                "variant_id": f"single_{improvement.improvement_id}",
                "prompt": variation,
                "applied_improvements": [improvement.improvement_id],
                "description": f"単一改善: {improvement.target_section}"
            })
        
        # 組み合わせ改善版
        high_priority_improvements = [imp for imp in improvements if imp.risk_level == "low"][:2]
        if len(high_priority_improvements) >= 2:
            variation = self._apply_multiple_improvements(base_prompt, high_priority_improvements)
            variations.append({
                "variant_id": f"combined_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "prompt": variation,
                "applied_improvements": [imp.improvement_id for imp in high_priority_improvements],
                "description": "組み合わせ改善: 低リスク改善の組み合わせ"
            })
        
        # 段階的改善版
        if len(improvements) >= 3:
            incremental_improvement = improvements[0]  # 最高優先度
            variation = self._apply_single_improvement(base_prompt, incremental_improvement)
            variations.append({
                "variant_id": f"incremental_{incremental_improvement.improvement_id}",
                "prompt": variation,
                "applied_improvements": [incremental_improvement.improvement_id],
                "description": "段階的改善: 最高優先度の改善のみ適用"
            })
        
        return variations
    
    def validate_improvement_safety(self, new_prompt: Dict[str, str], 
                                  base_prompt: Dict[str, str]) -> Dict[str, Any]:
        """
        改善案の安全性検証
        
        Args:
            new_prompt: 新しいプロンプト
            base_prompt: ベースプロンプト
            
        Returns:
            検証結果
        """
        validation_result = {
            "is_safe": True,
            "risk_level": "low",
            "issues": [],
            "recommendations": [],
            "safety_score": 1.0
        }
        
        # 長さチェック
        length_issues = self._validate_prompt_length(new_prompt, base_prompt)
        validation_result["issues"].extend(length_issues)
        
        # 必須要素チェック
        missing_elements = self._validate_required_elements(new_prompt)
        validation_result["issues"].extend(missing_elements)
        
        # 危険なパターンチェック
        dangerous_patterns = self._check_dangerous_patterns(new_prompt)
        validation_result["issues"].extend(dangerous_patterns)
        
        # 一貫性チェック
        consistency_issues = self._check_consistency(new_prompt)
        validation_result["issues"].extend(consistency_issues)
        
        # 総合リスクレベルの決定
        if any(issue["severity"] == "high" for issue in validation_result["issues"]):
            validation_result["risk_level"] = "high"
            validation_result["is_safe"] = False
        elif any(issue["severity"] == "medium" for issue in validation_result["issues"]):
            validation_result["risk_level"] = "medium"
        
        # 安全性スコア計算
        safety_score = self._calculate_safety_score(validation_result["issues"])
        validation_result["safety_score"] = safety_score
        validation_result["is_safe"] = safety_score >= 0.7
        
        # 推奨事項生成
        validation_result["recommendations"] = self._generate_safety_recommendations(validation_result["issues"])
        
        return validation_result
    
    def create_improvement_plan(self, improvements: List[PromptImprovement],
                              strategy: str = "incremental") -> ImprovementPlan:
        """
        改善計画の作成
        
        Args:
            improvements: 改善案のリスト
            strategy: 実装戦略 (incremental, batch, a_b_test)
            
        Returns:
            改善計画
        """
        # 優先度順でソート
        sorted_improvements = sorted(improvements, 
                                   key=lambda x: self._calculate_improvement_priority(x), 
                                   reverse=True)
        
        # 実装順序の決定
        priority_order = []
        if strategy == "incremental":
            # 段階的実装：リスクレベル順
            low_risk = [imp for imp in sorted_improvements if imp.risk_level == "low"]
            medium_risk = [imp for imp in sorted_improvements if imp.risk_level == "medium"]
            high_risk = [imp for imp in sorted_improvements if imp.risk_level == "high"]
            priority_order = ([imp.improvement_id for imp in low_risk] +
                            [imp.improvement_id for imp in medium_risk] +
                            [imp.improvement_id for imp in high_risk])
        elif strategy == "batch":
            # バッチ実装：影響度順
            priority_order = [imp.improvement_id for imp in sorted_improvements]
        elif strategy == "a_b_test":
            # A/Bテスト：最も効果が期待される上位3つ
            priority_order = [imp.improvement_id for imp in sorted_improvements[:3]]
        
        # 総合期待効果の計算
        total_impact = self._calculate_total_impact(improvements)
        
        # 検証要件の定義
        validation_requirements = self._define_validation_requirements(improvements, strategy)
        
        plan_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return ImprovementPlan(
            plan_id=plan_id,
            improvements=improvements,
            priority_order=priority_order,
            total_expected_impact=total_impact,
            implementation_strategy=strategy,
            validation_requirements=validation_requirements
        )
    
    def _generate_improvement_from_weakness(self, weakness) -> Optional[PromptImprovement]:
        """弱点から改善提案を生成"""
        improvement_templates = {
            "understanding": {
                "target_section": "task_understanding",
                "template": "ユーザーの要求を受け取ったら、{specific_action}してから実装に取りかかってください。",
                "specific_actions": [
                    "まず要求の核心を理解し、不明な点がないか確認",
                    "要件の範囲と制約条件を明確化",
                    "成功基準を定義"
                ]
            },
            "communication": {
                "target_section": "communication",
                "template": "{communication_guideline}を心がけてください。",
                "communication_guidelines": [
                    "作業内容を分かりやすく説明し、進捗を定期的に報告すること",
                    "専門用語を使う際は、必要に応じて説明を添えること",
                    "ユーザーの理解レベルに合わせた説明をすること"
                ]
            },
            "implementation": {
                "target_section": "code_quality",
                "template": "{quality_guideline}を遵守してください。",
                "quality_guidelines": [
                    "コードを書く前に設計を検討し、テスト可能で保守性の高いコードを心がける",
                    "構文エラーやセキュリティ問題がないか、コード生成後に必ず確認する",
                    "適切なコメントとドキュメントを含める"
                ]
            }
        }
        
        if not hasattr(weakness, 'category') or weakness.category not in improvement_templates:
            return None
        
        template_info = improvement_templates[weakness.category]
        template = template_info["template"]
        
        # テンプレートの具体的な内容を選択
        if weakness.category == "understanding":
            specific_content = template.format(specific_action=template_info["specific_actions"][0])
        elif weakness.category == "communication":
            specific_content = template.format(communication_guideline=template_info["communication_guidelines"][0])
        elif weakness.category == "implementation":
            specific_content = template.format(quality_guideline=template_info["quality_guidelines"][0])
        else:
            specific_content = template
        
        return PromptImprovement(
            improvement_id=f"weakness_{weakness.pattern_id}_{datetime.now().strftime('%H%M%S')}",
            target_section=template_info["target_section"],
            improvement_type="addition",
            current_content="",  # 新規追加の場合
            proposed_content=specific_content,
            rationale=f"{weakness.description}への対応として追加",
            expected_impact={
                "intent_understanding_rate": 15.0 if weakness.category == "understanding" else 0.0,
                "communication_clarity": 20.0 if weakness.category == "communication" else 0.0,
                "code_quality_score": 25.0 if weakness.category == "implementation" else 0.0
            },
            risk_level="low",
            validation_status="pending"
        )
    
    def _generate_improvements_from_conversation(self, conversation_analysis: Dict) -> List[PromptImprovement]:
        """対話分析結果から改善提案を生成"""
        improvements = []
        
        # 意図理解率が低い場合
        intent_rate = conversation_analysis.get("intent_understanding_rate", 1.0)
        if intent_rate < 0.7:
            improvements.append(PromptImprovement(
                improvement_id=f"intent_{datetime.now().strftime('%H%M%S')}",
                target_section="task_understanding",
                improvement_type="modification",
                current_content="",
                proposed_content="要求を受けた際は、まず内容を正確に理解し、曖昧な点や不明な点があれば具体的な質問をして明確化してください。推測で進めることは避けてください。",
                rationale=f"意図理解率が{intent_rate:.2f}と低いため、要求理解プロセスの改善が必要",
                expected_impact={"intent_understanding_rate": 20.0},
                risk_level="low",
                validation_status="pending"
            ))
        
        # 混乱ポイントが多い場合
        confusion_points = conversation_analysis.get("confusion_points", [])
        if len(confusion_points) > 2:
            improvements.append(PromptImprovement(
                improvement_id=f"confusion_{datetime.now().strftime('%H%M%S')}",
                target_section="communication",
                improvement_type="addition",
                current_content="",
                proposed_content="説明する際は、段階的に分かりやすく説明し、ユーザーが理解できているか適宜確認を取ってください。複雑な内容は例を用いて説明してください。",
                rationale=f"{len(confusion_points)}箇所で混乱が発生しているため、コミュニケーション改善が必要",
                expected_impact={"communication_clarity": 25.0},
                risk_level="low",
                validation_status="pending"
            ))
        
        # 質問品質が低い場合
        question_quality = conversation_analysis.get("question_quality", {})
        if question_quality.get("effectiveness_score", 1.0) < 0.6:
            improvements.append(PromptImprovement(
                improvement_id=f"question_{datetime.now().strftime('%H%M%S')}",
                target_section="task_understanding",
                improvement_type="addition",
                current_content="",
                proposed_content="不明な要求に対しては、以下の観点から具体的に質問してください：1）機能要件（何ができる必要があるか）、2）技術要件（使用技術・環境）、3）制約条件（期限・リソース）、4）成功基準（どうなれば完成か）",
                rationale=f"質問効果性スコアが{question_quality.get('effectiveness_score', 0):.2f}と低いため、質問品質の向上が必要",
                expected_impact={"intent_understanding_rate": 18.0, "communication_clarity": 15.0},
                risk_level="low",
                validation_status="pending"
            ))
        
        return improvements
    
    def _generate_improvements_from_evaluation(self, evaluation_results: Dict) -> List[PromptImprovement]:
        """評価結果から改善提案を生成"""
        improvements = []
        
        # 品質スコアが低い場合
        quality_score = evaluation_results.get("quality_score", 100)
        if quality_score < 70:
            improvements.append(PromptImprovement(
                improvement_id=f"quality_{datetime.now().strftime('%H%M%S')}",
                target_section="code_quality",
                improvement_type="modification",
                current_content="",
                proposed_content="コード生成時は以下を必ず遵守してください：1）構文エラーがないことを確認、2）セキュリティベストプラクティスの適用、3）適切なエラーハンドリングの実装、4）コードの可読性とメンテナンス性の確保",
                rationale=f"品質スコアが{quality_score}と低いため、コード品質基準の明確化が必要",
                expected_impact={"code_quality_score": 20.0},
                risk_level="low",
                validation_status="pending"
            ))
        
        # 完成度が低い場合
        completeness_score = evaluation_results.get("completeness_score", 100)
        if completeness_score < 60:
            improvements.append(PromptImprovement(
                improvement_id=f"completeness_{datetime.now().strftime('%H%M%S')}",
                target_section="task_understanding",
                improvement_type="addition",
                current_content="",
                proposed_content="実装前にタスクの全体像を把握し、必要な成果物（ファイル、機能、ドキュメント等）を明確にしてください。実装後は要求された全ての項目が含まれているかチェックしてください。",
                rationale=f"完成度スコアが{completeness_score}と低いため、要求仕様の完全実装を強化する必要",
                expected_impact={"completeness_score": 25.0},
                risk_level="low",
                validation_status="pending"
            ))
        
        # 効率性が低い場合
        efficiency_score = evaluation_results.get("efficiency_score", 100)
        if efficiency_score < 70:
            improvements.append(PromptImprovement(
                improvement_id=f"efficiency_{datetime.now().strftime('%H%M%S')}",
                target_section="task_understanding",
                improvement_type="addition",
                current_content="",
                proposed_content="複雑なタスクの場合は、実装前に作業計画を立て、効率的なアプローチを検討してください。段階的に実装を進め、各段階での成果を確認しながら進めてください。",
                rationale=f"効率性スコアが{efficiency_score}と低いため、計画性の向上が必要",
                expected_impact={"efficiency_score": 15.0},
                risk_level="low",
                validation_status="pending"
            ))
        
        return improvements
    
    def _generate_improvements_from_advanced_analysis(self, conversation_analysis: Dict) -> List[PromptImprovement]:
        """
        拡張分析結果から改善提案を生成（Phase 2）
        
        Args:
            conversation_analysis: 拡張対話分析結果
            
        Returns:
            改善提案のリスト
        """
        improvements = []
        
        # センチメント分析に基づく改善
        sentiment_analysis = conversation_analysis.get("sentiment_analysis", {})
        if sentiment_analysis.get("sentiment_trend") == "declining":
            improvements.append(PromptImprovement(
                improvement_id=f"sentiment_{datetime.now().strftime('%H%M%S')}",
                target_section="communication",
                improvement_type="addition",
                current_content="",
                proposed_content="ユーザーのフラストレーションを検出した場合は、共感的な対応をし、具体的な解決策を段階的に提示してください。「申し訳ありません。お困りのことと思います。一緒に解決していきましょう」のような表現を使用してください。",
                rationale=f"センチメント分析で満足度低下（{sentiment_analysis.get('satisfaction_score', 0):.2f}）が検出されたため",
                expected_impact={"user_satisfaction": 25.0, "communication_clarity": 20.0},
                risk_level="low",
                validation_status="pending"
            ))
        
        # 複雑さ処理に基づく改善
        complexity_analysis = conversation_analysis.get("complexity_analysis", {})
        if complexity_analysis.get("complexity_level") == "high" and complexity_analysis.get("handling_quality", 1.0) < 0.6:
            improvements.append(PromptImprovement(
                improvement_id=f"complexity_{datetime.now().strftime('%H%M%S')}",
                target_section="task_understanding",
                improvement_type="addition",
                current_content="",
                proposed_content="複雑なタスクに対しては以下の手順を実施してください：1）タスクを小さなステップに分解、2）各ステップの目標を明確化、3）段階的な実装計画の提示、4）各段階での確認とフィードバック要求。ドメイン固有の知識が必要な場合は、前提知識を確認してください。",
                rationale=f"高複雑度タスク（{complexity_analysis.get('complexity_level')}）の処理品質が低い（{complexity_analysis.get('handling_quality', 0):.2f}）ため",
                expected_impact={"completeness_score": 30.0, "planning_quality": 25.0},
                risk_level="low",
                validation_status="pending"
            ))
        
        # コミュニケーション効率に基づく改善
        efficiency_analysis = conversation_analysis.get("efficiency_analysis", {})
        if efficiency_analysis.get("efficiency_score", 1.0) < 0.5:
            waste_indicators = efficiency_analysis.get("waste_indicators", [])
            efficiency_suggestions = efficiency_analysis.get("optimization_suggestions", [])
            
            # 安全な文字列結合のための処理
            safe_suggestions = []
            for suggestion in efficiency_suggestions[:3]:
                if isinstance(suggestion, str):
                    safe_suggestions.append(suggestion)
                elif isinstance(suggestion, dict):
                    # 辞書の場合は適切な文字列表現に変換
                    safe_suggestions.append(str(suggestion.get('description', str(suggestion))))
                else:
                    safe_suggestions.append(str(suggestion))
            
            improvements.append(PromptImprovement(
                improvement_id=f"efficiency_{datetime.now().strftime('%H%M%S')}",
                target_section="communication",
                improvement_type="modification",
                current_content="",
                proposed_content=f"コミュニケーション効率を向上させるため、以下を心がけてください：{'; '.join(safe_suggestions)}。冗長な表現を避け、情報密度の高い応答を提供してください。",
                rationale=f"コミュニケーション効率が低い（{efficiency_analysis.get('efficiency_score', 0):.2f}）ため",
                expected_impact={"communication_efficiency": 20.0, "response_quality": 15.0},
                risk_level="low",
                validation_status="pending"
            ))
        
        # ミスアライメントに基づく改善
        misalignment_analysis = conversation_analysis.get("misalignment_analysis", {})
        if misalignment_analysis.get("severity") in ["high", "medium"]:
            improvements.append(PromptImprovement(
                improvement_id=f"alignment_{datetime.now().strftime('%H%M%S')}",
                target_section="task_understanding",
                improvement_type="addition",
                current_content="",
                proposed_content="ユーザーの要求に対応する前に、必ず要求の理解を確認してください。「理解したことを整理しますと、○○ということでよろしいでしょうか？」のような確認を行い、推測や仮定で進めることを避けてください。実装開始前に成果物のイメージを共有し、期待と実際のギャップを防いでください。",
                rationale=f"ユーザー期待とのミスアライメントが検出された（重要度: {misalignment_analysis.get('severity')}）",
                expected_impact={"intent_understanding_rate": 35.0, "user_satisfaction": 30.0},
                risk_level="low",
                validation_status="pending"
            ))
        
        # 統合指標に基づく改善
        advanced_metrics = conversation_analysis.get("advanced_metrics", {})
        if advanced_metrics:
            overall_quality = statistics.mean([
                advanced_metrics.get("overall_satisfaction", 0.5),
                advanced_metrics.get("complexity_handling_quality", 0.5),
                advanced_metrics.get("communication_efficiency", 0.5),
                advanced_metrics.get("alignment_quality", 0.5)
            ])
            
            if overall_quality < 0.6:
                improvements.append(PromptImprovement(
                    improvement_id=f"holistic_{datetime.now().strftime('%H%M%S')}",
                    target_section="system_role",
                    improvement_type="addition",
                    current_content="",
                    proposed_content="ユーザーとの対話において、1）ユーザーの満足度を常に意識し、2）複雑なタスクを適切に分解し、3）効率的なコミュニケーションを心がけ、4）ユーザーの期待と実際の成果物のギャップを防ぐことを最優先として行動してください。",
                    rationale=f"統合品質指標が低い（{overall_quality:.2f}）ため、全体的な対話品質向上が必要",
                    expected_impact={
                        "overall_satisfaction": 20.0,
                        "complexity_handling_quality": 15.0,
                        "communication_efficiency": 15.0,
                        "alignment_quality": 20.0
                    },
                    risk_level="medium",
                    validation_status="pending"
                ))
        
        return improvements
    
    def _deduplicate_improvements(self, improvements: List[PromptImprovement]) -> List[PromptImprovement]:
        """改善提案の重複削除"""
        unique_improvements = []
        seen_contents = set()
        
        for improvement in improvements:
            # 提案内容のハッシュ値で重複チェック
            content_hash = hashlib.md5(improvement.proposed_content.encode()).hexdigest()
            if content_hash not in seen_contents:
                unique_improvements.append(improvement)
                seen_contents.add(content_hash)
        
        return unique_improvements
    
    def _prioritize_improvements(self, improvements: List[PromptImprovement]) -> List[PromptImprovement]:
        """改善提案の優先度付け"""
        def calculate_priority_score(improvement):
            # 期待効果の重み付き合計
            impact_score = sum(
                improvement.expected_impact.get(metric, 0) * weight
                for metric, weight in self.impact_weights.items()
            )
            
            # リスクレベルによるペナルティ
            risk_penalty = {"low": 0, "medium": -10, "high": -25}[improvement.risk_level]
            
            return impact_score + risk_penalty
        
        return sorted(improvements, key=calculate_priority_score, reverse=True)
    
    def _apply_single_improvement(self, base_prompt: Dict[str, str], 
                                improvement: PromptImprovement) -> Dict[str, str]:
        """単一改善をプロンプトに適用"""
        new_prompt = base_prompt.copy()
        
        if improvement.improvement_type == "addition":
            # セクションが存在する場合は追記、存在しない場合は新規作成
            if improvement.target_section in new_prompt:
                new_prompt[improvement.target_section] += f" {improvement.proposed_content}"
            else:
                new_prompt[improvement.target_section] = improvement.proposed_content
        
        elif improvement.improvement_type == "modification":
            new_prompt[improvement.target_section] = improvement.proposed_content
        
        elif improvement.improvement_type == "deletion":
            if improvement.target_section in new_prompt:
                # 特定の内容を削除（完全削除ではなく部分削除）
                current_content = new_prompt[improvement.target_section]
                new_content = current_content.replace(improvement.current_content, "")
                new_prompt[improvement.target_section] = new_content.strip()
        
        return new_prompt
    
    def _apply_multiple_improvements(self, base_prompt: Dict[str, str], 
                                   improvements: List[PromptImprovement]) -> Dict[str, str]:
        """複数改善をプロンプトに適用"""
        new_prompt = base_prompt.copy()
        
        # 改善を順番に適用
        for improvement in improvements:
            new_prompt = self._apply_single_improvement(new_prompt, improvement)
        
        return new_prompt
    
    def _validate_prompt_length(self, new_prompt: Dict[str, str], 
                              base_prompt: Dict[str, str]) -> List[Dict[str, Any]]:
        """プロンプト長の検証"""
        issues = []
        
        # 全体の長さチェック
        new_total_length = sum(len(content) for content in new_prompt.values())
        base_total_length = sum(len(content) for content in base_prompt.values())
        
        if new_total_length > base_total_length * 2:  # 2倍を超える場合
            issues.append({
                "type": "length_excessive",
                "severity": "medium", 
                "description": f"プロンプト全体の長さが{new_total_length}文字となり、元の{base_total_length}文字から大幅に増加しています",
                "recommendation": "プロンプトの簡潔性を保つため、内容を整理することを推奨します"
            })
        
        # 個別セクションの長さチェック
        for section, content in new_prompt.items():
            if len(content) > 1000:  # 1000文字を超える場合
                issues.append({
                    "type": "section_length_excessive",
                    "severity": "low",
                    "section": section,
                    "description": f"{section}セクションが{len(content)}文字と長くなっています",
                    "recommendation": f"{section}セクションの内容を簡潔に整理することを推奨します"
                })
        
        return issues
    
    def _validate_required_elements(self, new_prompt: Dict[str, str]) -> List[Dict[str, Any]]:
        """必須要素の検証"""
        issues = []
        required_sections = ["system_role", "task_understanding"]
        
        for section in required_sections:
            if section not in new_prompt or not new_prompt[section].strip():
                issues.append({
                    "type": "missing_required_section",
                    "severity": "high",
                    "section": section,
                    "description": f"必須セクション'{section}'が不足または空です",
                    "recommendation": f"{section}セクションを追加または内容を記入してください"
                })
        
        return issues
    
    def _check_dangerous_patterns(self, new_prompt: Dict[str, str]) -> List[Dict[str, Any]]:
        """危険なパターンのチェック"""
        issues = []
        dangerous_patterns = [
            (r"無視して", "指示無視", "高"),
            (r"すべて許可", "過度な許可", "中"),
            (r"制限なし", "制約解除", "中"),
            (r"何でも実行", "無制限実行", "高")
        ]
        
        # 安全な文字列結合
        all_content = " ".join([
            str(value) if not isinstance(value, dict) else str(value)
            for value in new_prompt.values()
        ])
        
        for pattern, description, severity_jp in dangerous_patterns:
            if re.search(pattern, all_content, re.IGNORECASE):
                severity = {"高": "high", "中": "medium", "低": "low"}[severity_jp]
                issues.append({
                    "type": "dangerous_pattern",
                    "severity": severity,
                    "pattern": pattern,
                    "description": f"危険なパターン'{description}'が検出されました",
                    "recommendation": f"'{pattern}'に関する記述を見直してください"
                })
        
        return issues
    
    def _check_consistency(self, new_prompt: Dict[str, str]) -> List[Dict[str, Any]]:
        """一貫性のチェック"""
        issues = []
        
        # 矛盾する指示の検出
        contradictions = [
            (["簡潔に", "詳細に"], "簡潔性と詳細性の矛盾"),
            (["自動で", "確認を取って"], "自動実行と手動確認の矛盾"),
            (["速く", "慎重に"], "速度と慎重性の矛盾")
        ]
        
        # 安全な文字列結合
        all_content = " ".join([
            str(value) if not isinstance(value, dict) else str(value)
            for value in new_prompt.values()
        ]).lower()
        
        for contradiction_words, description in contradictions:
            if all(word in all_content for word in contradiction_words):
                issues.append({
                    "type": "logical_contradiction",
                    "severity": "medium",
                    "description": f"{description}が検出されました",
                    "contradictory_terms": contradiction_words,
                    "recommendation": f"'{contradiction_words[0]}'と'{contradiction_words[1]}'の関係を明確にしてください"
                })
        
        return issues
    
    def _calculate_safety_score(self, issues: List[Dict[str, Any]]) -> float:
        """安全性スコアの計算"""
        if not issues:
            return 1.0
        
        severity_weights = {"high": -0.3, "medium": -0.15, "low": -0.05}
        total_penalty = sum(severity_weights.get(issue["severity"], 0) for issue in issues)
        
        return max(0.0, 1.0 + total_penalty)
    
    def _generate_safety_recommendations(self, issues: List[Dict[str, Any]]) -> List[str]:
        """安全性改善の推奨事項生成"""
        recommendations = []
        
        for issue in issues:
            if "recommendation" in issue:
                recommendations.append(issue["recommendation"])
        
        if not recommendations:
            recommendations.append("安全性に問題は検出されませんでした")
        
        return recommendations
    
    def _calculate_improvement_priority(self, improvement: PromptImprovement) -> float:
        """改善提案の優先度計算"""
        # 期待効果の合計
        impact_sum = sum(improvement.expected_impact.values())
        
        # リスクレベルによる重み
        risk_weights = {"low": 1.0, "medium": 0.8, "high": 0.5}
        risk_weight = risk_weights.get(improvement.risk_level, 0.5)
        
        return impact_sum * risk_weight
    
    def _calculate_total_impact(self, improvements: List[PromptImprovement]) -> Dict[str, float]:
        """総合期待効果の計算"""
        total_impact = {}
        
        for improvement in improvements:
            for metric, value in improvement.expected_impact.items():
                if metric not in total_impact:
                    total_impact[metric] = 0
                total_impact[metric] += value
        
        # 重複効果を考慮した調整（完全加算ではなく収穫逓減）
        for metric in total_impact:
            original_value = total_impact[metric]
            # 収穫逓減効果を適用
            total_impact[metric] = original_value * (1 - 0.1 * (original_value / 100))
        
        return total_impact
    
    def _define_validation_requirements(self, improvements: List[PromptImprovement], 
                                      strategy: str) -> List[str]:
        """検証要件の定義"""
        requirements = []
        
        # 基本的な検証要件
        requirements.extend([
            "改善前後での基本シナリオテストの実行",
            "品質指標の測定と比較",
            "安全性チェックの実行"
        ])
        
        # 戦略別の追加要件
        if strategy == "a_b_test":
            requirements.extend([
                "A/Bテストの実行（最低100回の試行）",
                "統計的有意性の確認",
                "ユーザーフィードバックの収集"
            ])
        
        # 高リスク改善が含まれる場合
        if any(imp.risk_level == "high" for imp in improvements):
            requirements.extend([
                "段階的ロールアウトの実施",
                "ロールバック計画の準備",
                "詳細監視の設定"
            ])
        
        return requirements
    
    def _load_improvement_templates(self) -> Dict[str, Any]:
        """改善テンプレートのロード"""
        return {
            "understanding_templates": [
                "要求内容を正確に理解し、不明点は質問で明確化する",
                "成功基準を定義してから実装に着手する",
                "前提条件と制約を確認する"
            ],
            "communication_templates": [
                "専門用語には説明を付ける", 
                "作業内容を段階的に説明する",
                "進捗を定期的に報告する"
            ],
            "quality_templates": [
                "コード品質基準を明確に定義する",
                "テストとレビューを必須化する",
                "セキュリティを考慮する"
            ]
        }
    
    def _load_safety_patterns(self) -> Dict[str, List[str]]:
        """安全パターンのロード"""
        return {
            "required_sections": ["system_role", "task_understanding"],
            "dangerous_phrases": ["無視して", "制限なし", "何でも実行"],
            "contradictory_pairs": [["簡潔", "詳細"], ["自動", "確認"], ["速い", "慎重"]]
        }


# デモ実行用関数
def demo_improvement_engine():
    """ImprovementEngineのデモ実行"""
    print("=== ImprovementEngine デモ実行 ===")
    
    engine = ImprovementEngine()
    
    # サンプル分析結果
    sample_analysis = {
        "weakness_patterns": [
            type("WeaknessPattern", (), {
                "pattern_id": "low_understanding",
                "category": "understanding",
                "description": "要求理解が不十分",
                "severity": "high"
            })()
        ],
        "conversation_analysis": {
            "intent_understanding_rate": 0.6,
            "confusion_points": ["混乱1", "混乱2", "混乱3"],
            "question_quality": {"effectiveness_score": 0.5}
        },
        "evaluation_results": {
            "quality_score": 65,
            "completeness_score": 55,
            "efficiency_score": 60
        }
    }
    
    # 改善提案生成
    print("\n1. 改善提案生成:")
    improvements = engine.generate_targeted_improvements(sample_analysis)
    for i, improvement in enumerate(improvements[:3], 1):
        print(f"\n提案{i}: {improvement.improvement_id}")
        print(f"対象: {improvement.target_section}")
        print(f"タイプ: {improvement.improvement_type}")
        print(f"内容: {improvement.proposed_content[:100]}...")
        print(f"期待効果: {improvement.expected_impact}")
        print(f"リスク: {improvement.risk_level}")
    
    # サンプルベースプロンプト
    base_prompt = {
        "system_role": "あなたは優秀なAIアシスタントです。",
        "task_understanding": "ユーザーの要求を理解して適切に対応してください。"
    }
    
    # プロンプトバリエーション生成
    print(f"\n2. プロンプトバリエーション生成:")
    variations = engine.create_prompt_variations(base_prompt, improvements[:2])
    for variation in variations:
        print(f"\nバリエーション: {variation['variant_id']}")
        print(f"説明: {variation['description']}")
        print(f"適用改善: {variation['applied_improvements']}")
    
    # 安全性検証
    if variations:
        print(f"\n3. 安全性検証:")
        validation = engine.validate_improvement_safety(variations[0]["prompt"], base_prompt)
        print(f"安全性: {'安全' if validation['is_safe'] else '要注意'}")
        print(f"リスクレベル: {validation['risk_level']}")
        print(f"安全性スコア: {validation['safety_score']:.2f}")
        if validation['issues']:
            print("検出された問題:")
            for issue in validation['issues']:
                print(f"  - {issue['description']}")
    
    # 改善計画作成
    print(f"\n4. 改善計画作成:")
    plan = engine.create_improvement_plan(improvements[:3], strategy="incremental")
    print(f"計画ID: {plan.plan_id}")
    print(f"実装戦略: {plan.implementation_strategy}")
    print(f"優先順序: {plan.priority_order}")
    print(f"総合期待効果: {plan.total_expected_impact}")
    print(f"検証要件: {len(plan.validation_requirements)}項目")
    
    print("\n=== デモ完了 ===")


if __name__ == "__main__":
    demo_improvement_engine()