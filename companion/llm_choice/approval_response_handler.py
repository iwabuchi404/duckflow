"""
LLMApprovalResponseHandler - 一般的な承認システムのLLM処理
ファイル操作、コマンド実行などの承認回答を自然言語で理解
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from .choice_models import ChoiceContext, ChoiceResult
from companion.intent_understanding.enhanced_option_resolver import EnhancedOptionResolver


class ApprovalDecision(Enum):
    """承認判定の種類"""
    APPROVED = "approved"                    # 承認
    DENIED = "denied"                        # 拒否
    ALTERNATIVE_REQUESTED = "alternative"   # 代替案要求
    MORE_INFO_REQUESTED = "more_info"       # 詳細情報要求
    CONDITIONAL_APPROVAL = "conditional"    # 条件付き承認


@dataclass
class OperationInfo:
    """操作情報"""
    operation_type: str                     # 操作タイプ ("file_write", "command_exec", etc.)
    description: str                        # 操作の説明
    target: str                            # 対象 (ファイルパス、コマンドなど)
    risk_level: str = "medium"             # リスクレベル
    details: str = ""                      # 詳細情報
    alternatives: List[str] = None         # 代替案
    
    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []


@dataclass
class ApprovalInterpretation:
    """承認解釈結果"""
    decision: ApprovalDecision
    confidence: float
    reasoning: str
    conditions: List[str] = None           # 条件付き承認の場合の条件
    clarification_needed: bool = False
    user_message: str = ""
    
    def __post_init__(self):
        if self.conditions is None:
            self.conditions = []
    
    @property
    def approved(self) -> bool:
        """承認されたかどうか"""
        return self.decision in [ApprovalDecision.APPROVED, ApprovalDecision.CONDITIONAL_APPROVAL]


class LLMApprovalResponseHandler:
    """一般的な承認システムのLLM処理"""
    
    def __init__(self):
        """初期化"""
        self.enhanced_resolver = EnhancedOptionResolver()
        self.logger = logging.getLogger(__name__)
    
    async def interpret_approval_response(self, response: str, operation_info: OperationInfo) -> ApprovalInterpretation:
        """承認回答の解釈
        
        Args:
            response: ユーザーの回答
            operation_info: 操作情報
            
        Returns:
            ApprovalInterpretation: 解釈結果
        """
        try:
            # 選択コンテキストを構築
            choice_context = self._build_approval_choice_context(operation_info)
            
            # 拡張選択解析を実行
            choice_result = await self.enhanced_resolver.parse_selection_enhanced(
                response, choice_context
            )
            
            # 選択結果を承認解釈に変換
            interpretation = self._convert_to_approval_interpretation(
                choice_result, operation_info, response
            )
            
            self.logger.info(f"承認解釈結果: {interpretation.decision.value} (確信度: {interpretation.confidence:.2f})")
            return interpretation
            
        except Exception as e:
            self.logger.error(f"承認解釈エラー: {e}")
            # エラー時のフォールバック
            return ApprovalInterpretation(
                decision=ApprovalDecision.MORE_INFO_REQUESTED,
                confidence=0.0,
                reasoning=f"解釈エラー: {str(e)}",
                clarification_needed=True,
                user_message=response
            )
    
    def _build_approval_choice_context(self, operation_info: OperationInfo) -> ChoiceContext:
        """承認用選択コンテキストを構築
        
        Args:
            operation_info: 操作情報
            
        Returns:
            ChoiceContext: 選択コンテキスト
        """
        # リスクレベルと操作タイプに応じた選択肢を構成
        if operation_info.risk_level == "high":
            available_options = [
                "実行する",
                "拒否する", 
                "代替案を選択",
                "詳細確認",
                "条件付きで実行"
            ]
            option_descriptions = [
                "そのまま実行する",
                "実行を取り消す",
                "代替手段を選択する",
                "より詳しい情報を確認する",
                "一定の条件付きで実行する"
            ]
        elif operation_info.alternatives:
            # 代替案がある場合
            available_options = [
                "実行する",
                "拒否する",
                "代替案を選択"
            ]
            option_descriptions = [
                "提案された操作を実行する",
                "実行を取り消す",
                f"代替案から選択 ({len(operation_info.alternatives)}個利用可能)"
            ]
        else:
            # 基本的な選択肢
            available_options = [
                "実行する",
                "拒否する",
                "詳細確認"
            ]
            option_descriptions = [
                "提案された操作を実行する",
                "実行を取り消す",
                "より詳しい情報を確認する"
            ]
        
        return ChoiceContext(
            available_options=available_options,
            option_descriptions=option_descriptions,
            current_plan=f"{operation_info.operation_type}: {operation_info.target}",
            risk_level=operation_info.risk_level,
            conversation_context=f"{operation_info.description}\n{operation_info.details}"
        )
    
    def _convert_to_approval_interpretation(self, choice_result: ChoiceResult, 
                                          operation_info: OperationInfo, 
                                          user_response: str) -> ApprovalInterpretation:
        """選択結果を承認解釈に変換
        
        Args:
            choice_result: 選択結果
            operation_info: 操作情報
            user_response: ユーザー回答
            
        Returns:
            ApprovalInterpretation: 承認解釈結果
        """
        # 選択肢がない場合は詳細確認
        if not choice_result.selected_options:
            return ApprovalInterpretation(
                decision=ApprovalDecision.MORE_INFO_REQUESTED,
                confidence=choice_result.confidence,
                reasoning=choice_result.reasoning,
                clarification_needed=True,
                user_message=user_response
            )
        
        # 最初の選択肢で決定を判定
        primary_choice = choice_result.selected_options[0]
        
        # リスクレベルと代替案の有無に応じたマッピング
        if operation_info.risk_level == "high":
            decision_mapping = {
                1: ApprovalDecision.APPROVED,
                2: ApprovalDecision.DENIED,
                3: ApprovalDecision.ALTERNATIVE_REQUESTED,
                4: ApprovalDecision.MORE_INFO_REQUESTED,
                5: ApprovalDecision.CONDITIONAL_APPROVAL
            }
        elif operation_info.alternatives:
            decision_mapping = {
                1: ApprovalDecision.APPROVED,
                2: ApprovalDecision.DENIED,
                3: ApprovalDecision.ALTERNATIVE_REQUESTED
            }
        else:
            decision_mapping = {
                1: ApprovalDecision.APPROVED,
                2: ApprovalDecision.DENIED,
                3: ApprovalDecision.MORE_INFO_REQUESTED
            }
        
        decision = decision_mapping.get(primary_choice, ApprovalDecision.MORE_INFO_REQUESTED)
        
        # 条件や修正要求の処理
        conditions = []
        if choice_result.modifications:
            if decision == ApprovalDecision.APPROVED:
                # 修正要求がある場合は条件付き承認に変更
                decision = ApprovalDecision.CONDITIONAL_APPROVAL
            conditions = choice_result.modifications
        
        return ApprovalInterpretation(
            decision=decision,
            confidence=choice_result.confidence,
            reasoning=choice_result.reasoning,
            conditions=conditions,
            clarification_needed=choice_result.clarification_needed,
            user_message=user_response
        )
    
    async def get_alternative_selection_enhanced(self, alternatives: List[str], 
                                               operation_info: OperationInfo) -> Optional[str]:
        """代替案のLLM強化選択
        
        Args:
            alternatives: 代替案リスト
            operation_info: 操作情報
            
        Returns:
            Optional[str]: 選択された代替案
        """
        from codecrafter.ui.rich_ui import rich_ui
        
        if not alternatives:
            return None
        
        # 代替案選択用コンテキストを構築
        choice_context = ChoiceContext(
            available_options=alternatives,
            option_descriptions=[f"代替案{i+1}: {alt}" for i, alt in enumerate(alternatives)],
            current_plan=f"{operation_info.operation_type}: {operation_info.target}",
            risk_level=operation_info.risk_level,
            conversation_context="代替案から選択してください"
        )
        
        # ユーザー入力を取得
        alternative_prompt = self._format_alternative_selection_prompt(alternatives, operation_info)
        rich_ui.print_message(alternative_prompt, "question")
        
        user_input = rich_ui.get_user_input("代替案を選択してください (自然な表現で):")
        
        try:
            # LLM強化選択解析
            choice_result = await self.enhanced_resolver.parse_selection_enhanced(
                user_input, choice_context
            )
            
            if choice_result.confidence >= 0.7 and choice_result.selected_options:
                selected_idx = choice_result.selected_options[0] - 1
                if 0 <= selected_idx < len(alternatives):
                    selected_alternative = alternatives[selected_idx]
                    
                    # 選択確認
                    if choice_result.confidence < 0.9:
                        confirmation_msg = f"以下の代替案を選択しますか？\n{selected_alternative}"
                        if not rich_ui.get_confirmation(confirmation_msg):
                            return None
                    
                    return selected_alternative
            
            # 低確信度または無効な選択の場合
            rich_ui.print_message("適切な代替案を特定できませんでした。", "warning")
            return None
            
        except Exception as e:
            self.logger.error(f"代替案選択エラー: {e}")
            return None
    
    def _format_alternative_selection_prompt(self, alternatives: List[str], 
                                           operation_info: OperationInfo) -> str:
        """代替案選択プロンプトをフォーマット
        
        Args:
            alternatives: 代替案リスト
            operation_info: 操作情報
            
        Returns:
            str: フォーマットされたプロンプト
        """
        lines = [
            f"元の操作: {operation_info.description}",
            f"対象: {operation_info.target}",
            "",
            "利用可能な代替案:"
        ]
        
        for i, alt in enumerate(alternatives, 1):
            lines.append(f"{i}. {alt}")
        
        return "\n".join(lines)
    
    def format_approval_confirmation(self, interpretation: ApprovalInterpretation, 
                                   operation_info: OperationInfo) -> str:
        """承認解釈結果の確認メッセージをフォーマット
        
        Args:
            interpretation: 承認解釈結果
            operation_info: 操作情報
            
        Returns:
            str: 確認メッセージ
        """
        decision_descriptions = {
            ApprovalDecision.APPROVED: "実行を承認",
            ApprovalDecision.DENIED: "実行を拒否",
            ApprovalDecision.ALTERNATIVE_REQUESTED: "代替案を要求",
            ApprovalDecision.MORE_INFO_REQUESTED: "詳細情報を要求",
            ApprovalDecision.CONDITIONAL_APPROVAL: "条件付きで承認"
        }
        
        message_parts = [
            f"以下の解釈で正しいですか？",
            f"",
            f"操作: {operation_info.description}",
            f"判定: {decision_descriptions.get(interpretation.decision, '不明')}",
            f"理由: {interpretation.reasoning}",
            f"確信度: {interpretation.confidence:.1%}"
        ]
        
        if interpretation.conditions:
            message_parts.extend([
                f"",
                f"条件:",
                *[f"- {cond}" for cond in interpretation.conditions]
            ])
        
        message_parts.extend([
            f"",
            f"正しい場合は「はい」、修正が必要な場合は「いいえ」を入力してください。"
        ])
        
        return "\n".join(message_parts)