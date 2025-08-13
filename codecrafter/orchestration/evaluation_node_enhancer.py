"""
Evaluation Node Enhancer - 評価ノード強化

品質ゲート & 司令塔機能を提供
全アクション結果を評価し、Duck Vitals Systemと連携して次の行動を決定
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from ..state.agent_state import AgentState
from ..prompts.four_node_context import (
    UnderstandingResult, GatheredInfo, ExecutionResult, EvaluationResult, NextAction
)
from ..services.task_classifier import TaskProfileType
from ..ui.rich_ui import rich_ui
from ..base.llm_client import llm_manager


class EvaluationCriteria(Enum):
    """評価基準"""
    COMPLETENESS = "completeness"        # 完全性
    ACCURACY = "accuracy"               # 正確性
    RELEVANCE = "relevance"             # 関連性
    SAFETY = "safety"                   # 安全性
    EFFICIENCY = "efficiency"           # 効率性


class QualityGate:
    """品質ゲート - 処理品質の最終判定"""
    
    def __init__(self):
        """品質ゲートを初期化"""
        self.minimum_scores = {
            EvaluationCriteria.COMPLETENESS: 0.6,
            EvaluationCriteria.ACCURACY: 0.7,
            EvaluationCriteria.RELEVANCE: 0.5,
            EvaluationCriteria.SAFETY: 0.9,
            EvaluationCriteria.EFFICIENCY: 0.4
        }
        
    def evaluate_quality(
        self, 
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo], 
        execution_result: Optional[ExecutionResult],
        task_profile_type: Optional[TaskProfileType]
    ) -> Dict[EvaluationCriteria, float]:
        """総合品質評価
        
        Args:
            understanding_result: 理解結果
            gathered_info: 収集情報
            execution_result: 実行結果
            task_profile_type: TaskProfile分類
            
        Returns:
            評価基準別スコア辞書
        """
        scores = {}
        
        # 完全性評価
        scores[EvaluationCriteria.COMPLETENESS] = self._evaluate_completeness(
            understanding_result, gathered_info, execution_result
        )
        
        # 正確性評価
        scores[EvaluationCriteria.ACCURACY] = self._evaluate_accuracy(
            understanding_result, gathered_info, execution_result
        )
        
        # 関連性評価
        scores[EvaluationCriteria.RELEVANCE] = self._evaluate_relevance(
            understanding_result, gathered_info, task_profile_type
        )
        
        # 安全性評価
        scores[EvaluationCriteria.SAFETY] = self._evaluate_safety(
            understanding_result, execution_result
        )
        
        # 効率性評価
        scores[EvaluationCriteria.EFFICIENCY] = self._evaluate_efficiency(
            understanding_result, gathered_info, execution_result
        )
        
        return scores
    
    def passes_quality_gate(self, quality_scores: Dict[EvaluationCriteria, float]) -> bool:
        """品質ゲート通過判定
        
        Args:
            quality_scores: 評価基準別スコア
            
        Returns:
            品質ゲート通過可否
        """
        for criteria, score in quality_scores.items():
            minimum_required = self.minimum_scores[criteria]
            if score < minimum_required:
                rich_ui.print_warning(f"品質ゲート未通過: {criteria.value} = {score:.2f} < {minimum_required}")
                return False
        
        rich_ui.print_success("🎉 品質ゲート通過")
        return True
    
    def _evaluate_completeness(
        self, 
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo], 
        execution_result: Optional[ExecutionResult]
    ) -> float:
        """完全性評価"""
        completeness_score = 0.0
        total_components = 3
        
        # 理解結果の完全性
        if understanding_result and understanding_result.execution_plan:
            if understanding_result.execution_plan.steps and understanding_result.execution_plan.required_tools:
                completeness_score += 0.4
        
        # 情報収集の完全性
        if gathered_info:
            if gathered_info.collected_files:
                completeness_score += 0.3
            if gathered_info.project_context:
                completeness_score += 0.1
        
        # 実行結果の完全性
        if execution_result and execution_result.success:
            completeness_score += 0.2
        
        return min(completeness_score, 1.0)
    
    def _evaluate_accuracy(
        self, 
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo], 
        execution_result: Optional[ExecutionResult]
    ) -> float:
        """正確性評価"""
        accuracy_indicators = []
        
        # 理解結果の正確性
        if understanding_result:
            accuracy_indicators.append(understanding_result.confidence)
        
        # 収集データの正確性
        if gathered_info and gathered_info.collected_files:
            # ファイル読み取り成功率
            successful_reads = sum(
                1 for file_content in gathered_info.collected_files.values()
                if hasattr(file_content, 'content') and 
                not file_content.content.startswith('[読み取りエラー')
            )
            total_files = len(gathered_info.collected_files)
            if total_files > 0:
                read_success_rate = successful_reads / total_files
                accuracy_indicators.append(read_success_rate)
        
        # 実行結果の正確性
        if execution_result:
            execution_accuracy = 1.0 if execution_result.success else 0.3
            accuracy_indicators.append(execution_accuracy)
        
        return sum(accuracy_indicators) / len(accuracy_indicators) if accuracy_indicators else 0.5
    
    def _evaluate_relevance(
        self, 
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo], 
        task_profile_type: Optional[TaskProfileType]
    ) -> float:
        """関連性評価"""
        if not task_profile_type:
            return 0.5
        
        relevance_score = 0.0
        
        # TaskProfileと理解結果の関連性
        if understanding_result:
            relevance_score += 0.4
        
        # TaskProfileと収集データの関連性
        if gathered_info and gathered_info.collected_files:
            # TaskProfileに応じた関連ファイルの存在チェック
            if task_profile_type in [TaskProfileType.FILE_ANALYSIS, TaskProfileType.CODE_EXPLANATION]:
                if any('.py' in str(path) or 'test' in str(path) 
                      for path in gathered_info.collected_files.keys()):
                    relevance_score += 0.6
            else:
                relevance_score += 0.4
        
        return min(relevance_score, 1.0)
    
    def _evaluate_safety(
        self, 
        understanding_result: Optional[UnderstandingResult],
        execution_result: Optional[ExecutionResult]
    ) -> float:
        """安全性評価"""
        safety_score = 1.0  # デフォルトで高安全性
        
        # 実行リスクによる安全性減点
        if execution_result and execution_result.risk_assessment:
            if execution_result.risk_assessment.overall_risk.value == "high":
                safety_score -= 0.3
            elif execution_result.risk_assessment.overall_risk.value == "medium":
                safety_score -= 0.1
        
        # エラー発生による安全性減点
        if execution_result and execution_result.errors:
            error_penalty = min(len(execution_result.errors) * 0.1, 0.3)
            safety_score -= error_penalty
        
        return max(safety_score, 0.0)
    
    def _evaluate_efficiency(
        self, 
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo], 
        execution_result: Optional[ExecutionResult]
    ) -> float:
        """効率性評価"""
        efficiency_indicators = []
        
        # 理解段階の効率性
        if understanding_result:
            # 複雑度予測と実際の一致度
            predicted_complexity = understanding_result.execution_plan.estimated_complexity
            complexity_score = {"low": 0.9, "medium": 0.7, "high": 0.5}.get(predicted_complexity, 0.6)
            efficiency_indicators.append(complexity_score)
        
        # 情報収集の効率性
        if gathered_info and gathered_info.collected_files:
            # ファイル数とコンテンツ量のバランス
            file_count = len(gathered_info.collected_files)
            if 1 <= file_count <= 10:  # 適切な範囲
                efficiency_indicators.append(0.8)
            else:
                efficiency_indicators.append(0.5)
        
        # 実行の効率性
        if execution_result:
            execution_time = execution_result.execution_time
            if execution_time < 1.0:  # 1秒以下
                efficiency_indicators.append(0.9)
            elif execution_time < 5.0:  # 5秒以下
                efficiency_indicators.append(0.7)
            else:
                efficiency_indicators.append(0.4)
        
        return sum(efficiency_indicators) / len(efficiency_indicators) if efficiency_indicators else 0.5


class EvaluationNodeEnhancer:
    """評価ノード強化機能
    
    品質ゲート & 司令塔として、全アクション結果を評価し、
    Duck Vitals Systemと連携して次の行動を決定
    """
    
    def __init__(self):
        """評価ノード強化機能を初期化"""
        self.quality_gate = QualityGate()
    
    async def enhance_evaluation(
        self, 
        state_obj: AgentState,
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo],
        execution_result: Optional[ExecutionResult],
        task_profile_type: Optional[TaskProfileType]
    ) -> EvaluationResult:
        """強化された評価実行
        
        Args:
            state_obj: エージェント状態
            understanding_result: 理解結果
            gathered_info: 収集情報
            execution_result: 実行結果
            task_profile_type: TaskProfile分類
            
        Returns:
            強化された評価結果
        """
        try:
            rich_ui.print_step("🎯 [品質ゲート & 司令塔] 強化評価実行")
            
            # 1. 品質評価実行
            quality_scores = self.quality_gate.evaluate_quality(
                understanding_result, gathered_info, execution_result, task_profile_type
            )
            
            # 2. 品質ゲート判定
            quality_gate_passed = self.quality_gate.passes_quality_gate(quality_scores)
            overall_quality_score = sum(quality_scores.values()) / len(quality_scores)
            
            # 3. Duck Vitals System 統合評価
            vitals_assessment = self._assess_duck_vitals(state_obj, quality_scores)
            
            # 4. LLM推理による詳細評価
            llm_evaluation = await self._perform_llm_reasoning(
                state_obj, understanding_result, gathered_info, execution_result, 
                task_profile_type, quality_scores
            )
            
            # 5. 次アクション決定 (司令塔機能)
            next_action = self._determine_next_action(
                state_obj, quality_gate_passed, quality_scores, 
                understanding_result, gathered_info, execution_result, vitals_assessment
            )
            
            # 6. 応答生成準備度チェック
            response_readiness, template_completeness = self._assess_response_generation_readiness(
                understanding_result, gathered_info, execution_result, task_profile_type
            )
            
            # 7. 統合評価結果作成
            evaluation_result = EvaluationResult(
                overall_quality_score=overall_quality_score,
                task_completion_status=self._determine_completion_status(
                    understanding_result, gathered_info, execution_result
                ),
                identified_issues=self._identify_issues(quality_scores, state_obj),
                recommended_next_action=next_action,
                confidence_in_recommendation=self._calculate_recommendation_confidence(quality_scores),
                reasoning=llm_evaluation.get("reasoning", "品質ゲート評価に基づく判定"),
                duck_vitals_assessment=vitals_assessment,
                response_generation_readiness=response_readiness,
                template_data_completeness=template_completeness,
                quality_gate_passed=quality_gate_passed
            )
            
            rich_ui.print_success(f"🎯 評価完了: 次アクション = {next_action.value}")
            
            return evaluation_result
            
        except Exception as e:
            rich_ui.print_error(f"強化評価エラー: {e}")
            # フォールバック評価結果
            return EvaluationResult(
                overall_quality_score=0.3,
                task_completion_status="error",
                identified_issues=[f"評価エラー: {str(e)}"],
                recommended_next_action=NextAction.RESPONSE_GENERATION,
                confidence_in_recommendation=0.5,
                reasoning=f"評価エラーのためフォールバック: {str(e)}",
                duck_vitals_assessment={"mood": 0.5, "focus": 0.5, "stamina": 0.5}
            )
    
    def _assess_duck_vitals(self, state_obj: AgentState, quality_scores: Dict[EvaluationCriteria, float]) -> Dict[str, float]:
        """Duck Vitals System 評価"""
        return {
            "mood": state_obj.vitals.mood,
            "focus": state_obj.vitals.focus,
            "stamina": state_obj.vitals.stamina,
            "health_status": state_obj.vitals.get_health_status(),
            "quality_alignment": sum(quality_scores.values()) / len(quality_scores)
        }
    
    async def _perform_llm_reasoning(
        self, 
        state_obj: AgentState,
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo],
        execution_result: Optional[ExecutionResult],
        task_profile_type: Optional[TaskProfileType],
        quality_scores: Dict[EvaluationCriteria, float]
    ) -> Dict[str, Any]:
        """LLM推理による詳細評価"""
        try:
            # 評価プロンプト構築
            prompt = self._build_llm_evaluation_prompt(
                understanding_result, gathered_info, execution_result, 
                task_profile_type, quality_scores
            )
            
            # LLM推理実行
            response = llm_manager.chat(prompt)
            
            return {
                "reasoning": response[:300],  # 最初の300文字
                "full_response": response
            }
            
        except Exception as e:
            rich_ui.print_warning(f"LLM推理エラー: {e}")
            return {
                "reasoning": "LLM推理エラーのため品質スコアベース評価",
                "full_response": ""
            }
    
    def _build_llm_evaluation_prompt(
        self, 
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo],
        execution_result: Optional[ExecutionResult],
        task_profile_type: Optional[TaskProfileType],
        quality_scores: Dict[EvaluationCriteria, float]
    ) -> str:
        """LLM評価プロンプト構築"""
        prompt_parts = [
            "以下の処理結果を評価し、品質ゲート通過可否と次のアクションを判定してください。",
            "",
            f"TaskProfile: {task_profile_type.value if task_profile_type else 'Unknown'}",
            "",
            "品質スコア:"
        ]
        
        for criteria, score in quality_scores.items():
            prompt_parts.append(f"• {criteria.value}: {score:.2f}")
        
        prompt_parts.extend([
            "",
            "処理状況:",
            f"• 理解・計画: {'完了' if understanding_result else '未完了'}",
            f"• 情報収集: {'完了' if gathered_info else '未完了'}",
            f"• 実行: {'完了' if execution_result else '未完了'}",
            "",
            "次のアクション候補:",
            "1. RESPONSE_GENERATION - 応答生成へ進む",
            "2. REPLAN - 再計画が必要", 
            "3. COLLECT_MORE_INFO - 追加情報収集",
            "4. EXECUTE_ADDITIONAL - 追加実行",
            "5. END - 処理完了",
            "",
            "推奨アクションと理由を簡潔に回答してください。"
        ])
        
        return "\n".join(prompt_parts)
    
    def _determine_next_action(
        self, 
        state_obj: AgentState,
        quality_gate_passed: bool,
        quality_scores: Dict[EvaluationCriteria, float],
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo],
        execution_result: Optional[ExecutionResult],
        vitals_assessment: Dict[str, float]
    ) -> NextAction:
        """次アクション決定 (司令塔機能)"""
        
        # Duck Pacemaker 介入チェック (最優先)
        intervention = state_obj.needs_duck_intervention()
        if intervention["required"]:
            if intervention["priority"] == "CRITICAL":
                return NextAction.DUCK_CALL
            elif intervention["priority"] == "HIGH" and intervention["action"] == "REPLAN":
                return NextAction.REPLAN
        
        # 品質ゲート未通過の場合
        if not quality_gate_passed:
            # 完全性が低い場合
            if quality_scores.get(EvaluationCriteria.COMPLETENESS, 0) < 0.5:
                if not gathered_info or not gathered_info.collected_files:
                    return NextAction.COLLECT_MORE_INFO
                else:
                    return NextAction.REPLAN
            
            # 正確性が低い場合
            if quality_scores.get(EvaluationCriteria.ACCURACY, 0) < 0.6:
                return NextAction.REPLAN
        
        # 段階的完了チェック
        if not understanding_result:
            return NextAction.REPLAN
        elif not gathered_info:
            return NextAction.COLLECT_MORE_INFO
        elif not execution_result:
            return NextAction.EXECUTE_ADDITIONAL
        else:
            # 全て完了している場合は応答生成へ
            return NextAction.RESPONSE_GENERATION
    
    def _assess_response_generation_readiness(
        self, 
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo],
        execution_result: Optional[ExecutionResult],
        task_profile_type: Optional[TaskProfileType]
    ) -> Tuple[bool, float]:
        """応答生成準備度評価"""
        readiness_indicators = []
        
        # 基本データの有無
        if understanding_result:
            readiness_indicators.append(0.3)
        if gathered_info and gathered_info.collected_files:
            readiness_indicators.append(0.4)
        if execution_result and execution_result.success:
            readiness_indicators.append(0.2)
        if task_profile_type:
            readiness_indicators.append(0.1)
        
        template_completeness = sum(readiness_indicators)
        response_readiness = template_completeness >= 0.6
        
        return response_readiness, template_completeness
    
    def _determine_completion_status(
        self, 
        understanding_result: Optional[UnderstandingResult],
        gathered_info: Optional[GatheredInfo],
        execution_result: Optional[ExecutionResult]
    ) -> str:
        """完了状況判定"""
        completed_phases = 0
        total_phases = 3
        
        if understanding_result:
            completed_phases += 1
        if gathered_info:
            completed_phases += 1
        if execution_result and execution_result.success:
            completed_phases += 1
        
        completion_percentage = completed_phases / total_phases
        
        if completion_percentage >= 1.0:
            return "completed"
        elif completion_percentage >= 0.6:
            return "mostly_completed"
        elif completion_percentage >= 0.3:
            return "in_progress"
        else:
            return "just_started"
    
    def _identify_issues(self, quality_scores: Dict[EvaluationCriteria, float], state_obj: AgentState) -> List[str]:
        """問題特定"""
        issues = []
        
        # 品質スコアベース問題特定
        for criteria, score in quality_scores.items():
            if score < 0.5:
                issues.append(f"{criteria.value}スコア低下 ({score:.2f})")
        
        # バイタルベース問題特定
        if state_obj.vitals.stamina < 0.2:
            issues.append("体力不足による処理品質低下")
        if state_obj.vitals.focus < 0.4:
            issues.append("集中力低下による思考停滞")
        if state_obj.vitals.mood < 0.6:
            issues.append("自信不足による判断困難")
        
        return issues
    
    def _calculate_recommendation_confidence(self, quality_scores: Dict[EvaluationCriteria, float]) -> float:
        """推奨信頼度計算"""
        average_quality = sum(quality_scores.values()) / len(quality_scores)
        
        # 品質スコアが高いほど推奨の信頼度も高い
        base_confidence = average_quality
        
        # 品質スコアの分散による調整（一貫性チェック）
        quality_values = list(quality_scores.values())
        quality_variance = sum((score - average_quality) ** 2 for score in quality_values) / len(quality_values)
        
        # 分散が低い（一貫している）ほど信頼度向上
        consistency_bonus = max(0, 0.2 - quality_variance)
        
        final_confidence = min(base_confidence + consistency_bonus, 1.0)
        return final_confidence


# グローバルインスタンス
evaluation_node_enhancer = EvaluationNodeEnhancer()