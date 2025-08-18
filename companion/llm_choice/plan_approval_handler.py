"""
LLMPlanApprovalHandler - プラン承認のLLM処理
プラン承認回答を自然言語で理解し、適切な処理を実行
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from .choice_models import ChoiceContext, ChoiceResult
from .choice_parser import LLMChoiceParser
from companion.intent_understanding.enhanced_option_resolver import EnhancedOptionResolver
from companion.plan_tool import Plan, PlanState, SpecSelection
from companion.collaborative_planner import ActionSpec


class ApprovalAction(Enum):
    """承認アクションの種類"""
    APPROVE_ALL = "approve_all"           # 全選択肢を承認
    APPROVE_PARTIAL = "approve_partial"   # 部分的に承認
    REJECT = "reject"                     # 拒否
    REQUEST_MODIFICATION = "request_modification"  # 修正要求
    REQUEST_DETAILS = "request_details"   # 詳細確認


@dataclass
class PlanApprovalContext:
    """プラン承認コンテキスト"""
    plan: Plan
    plan_state: PlanState
    available_actions: List[ActionSpec]
    risk_level: str = "medium"
    preview_summary: str = ""
    
    @property
    def plan_summary(self) -> str:
        """プランの簡潔な要約を取得"""
        return f"{self.plan.title}: {self.plan.content[:100]}{'...' if len(self.plan.content) > 100 else ''}"


@dataclass
class ApprovalResult:
    """承認結果"""
    action: ApprovalAction
    approved_spec_ids: List[str]
    reasoning: str
    confidence: float
    modifications_requested: List[str]
    clarification_needed: bool = False
    user_message: str = ""


class LLMPlanApprovalHandler:
    """プラン承認のLLM処理"""
    
    def __init__(self):
        """初期化"""
        self.enhanced_resolver = EnhancedOptionResolver()
        self.llm_parser = LLMChoiceParser()
        self.logger = logging.getLogger(__name__)
    
    async def process_plan_response(self, user_input: str, plan_context: PlanApprovalContext) -> ApprovalResult:
        """プラン承認回答の処理
        
        Args:
            user_input: ユーザーの入力
            plan_context: プランコンテキスト
            
        Returns:
            ApprovalResult: 承認結果
        """
        try:
            # 選択コンテキストを構築
            choice_context = self._build_choice_context(plan_context)
            
            # 拡張選択解析を実行
            choice_result = await self.enhanced_resolver.parse_selection_enhanced(
                user_input, choice_context
            )
            
            # 選択結果を承認結果に変換
            approval_result = self._convert_to_approval_result(
                choice_result, plan_context, user_input
            )
            
            self.logger.info(f"プラン承認処理完了: {approval_result.action.value} (確信度: {approval_result.confidence:.2f})")
            return approval_result
            
        except Exception as e:
            self.logger.error(f"プラン承認処理エラー: {e}")
            # エラー時のフォールバック
            return ApprovalResult(
                action=ApprovalAction.REQUEST_DETAILS,
                approved_spec_ids=[],
                reasoning=f"処理エラーが発生しました: {str(e)}",
                confidence=0.0,
                modifications_requested=[],
                clarification_needed=True,
                user_message=user_input
            )
    
    def _build_choice_context(self, plan_context: PlanApprovalContext) -> ChoiceContext:
        """選択コンテキストを構築
        
        Args:
            plan_context: プランコンテキスト
            
        Returns:
            ChoiceContext: 選択コンテキスト
        """
        # リスクレベルに応じた選択肢の構成
        if plan_context.risk_level == "high":
            available_options = [
                "全て実行",
                "部分的に実行", 
                "拒否",
                "修正要求",
                "詳細確認"
            ]
            option_descriptions = [
                "すべてのアクションを実行する",
                "一部のアクションのみ実行する",
                "プランを実行しない",
                "プランの一部修正を要求する",
                "プランの詳細を確認する"
            ]
        else:
            available_options = [
                "全て実行",
                "部分的に実行",
                "拒否",
                "修正要求"
            ]
            option_descriptions = [
                "すべてのアクションを実行する",
                "一部のアクションのみ実行する",
                "プランを実行しない",
                "プランの一部修正を要求する"
            ]
        
        return ChoiceContext(
            available_options=available_options,
            option_descriptions=option_descriptions,
            current_plan=plan_context.plan_summary,
            risk_level=plan_context.risk_level,
            conversation_context=plan_context.preview_summary
        )
    
    def _convert_to_approval_result(self, choice_result: ChoiceResult, 
                                  plan_context: PlanApprovalContext, 
                                  user_input: str) -> ApprovalResult:
        """選択結果を承認結果に変換
        
        Args:
            choice_result: 選択結果
            plan_context: プランコンテキスト
            user_input: ユーザー入力
            
        Returns:
            ApprovalResult: 承認結果
        """
        # 選択肢がない場合は詳細確認
        if not choice_result.selected_options:
            return ApprovalResult(
                action=ApprovalAction.REQUEST_DETAILS,
                approved_spec_ids=[],
                reasoning=choice_result.reasoning,
                confidence=choice_result.confidence,
                modifications_requested=[],
                clarification_needed=True,
                user_message=user_input
            )
        
        # 最初の選択肢でアクションを決定
        primary_choice = choice_result.selected_options[0]
        
        # リスクレベルに応じたマッピング
        if plan_context.risk_level == "high":
            action_mapping = {
                1: ApprovalAction.APPROVE_ALL,
                2: ApprovalAction.APPROVE_PARTIAL,
                3: ApprovalAction.REJECT,
                4: ApprovalAction.REQUEST_MODIFICATION,
                5: ApprovalAction.REQUEST_DETAILS
            }
        else:
            action_mapping = {
                1: ApprovalAction.APPROVE_ALL,
                2: ApprovalAction.APPROVE_PARTIAL,
                3: ApprovalAction.REJECT,
                4: ApprovalAction.REQUEST_MODIFICATION
            }
        
        action = action_mapping.get(primary_choice, ApprovalAction.REQUEST_DETAILS)
        
        # 承認対象のActionSpec IDを決定
        approved_spec_ids = []
        if action in [ApprovalAction.APPROVE_ALL, ApprovalAction.APPROVE_PARTIAL]:
            if action == ApprovalAction.APPROVE_ALL:
                # 全てのActionSpecを承認
                approved_spec_ids = [spec.id for spec in plan_context.plan_state.action_specs]
            else:
                # 部分的承認: modificationsから特定のアクションを抽出
                # またはデフォルトで最初のアクションのみ
                if choice_result.modifications:
                    # modificationからアクションIDを抽出する処理を実装
                    approved_spec_ids = self._extract_spec_ids_from_modifications(
                        choice_result.modifications, plan_context
                    )
                else:
                    # デフォルト: 最初のアクションのみ
                    if plan_context.plan_state.action_specs:
                        approved_spec_ids = [plan_context.plan_state.action_specs[0].id]
        
        return ApprovalResult(
            action=action,
            approved_spec_ids=approved_spec_ids,
            reasoning=choice_result.reasoning,
            confidence=choice_result.confidence,
            modifications_requested=choice_result.modifications,
            clarification_needed=choice_result.clarification_needed,
            user_message=user_input
        )
    
    def _extract_spec_ids_from_modifications(self, modifications: List[str], 
                                           plan_context: PlanApprovalContext) -> List[str]:
        """修正要求から特定のActionSpec IDを抽出
        
        Args:
            modifications: 修正要求リスト
            plan_context: プランコンテキスト
            
        Returns:
            List[str]: 抽出されたActionSpec IDリスト
        """
        # 簡単なキーワードマッチングで特定のアクションを特定
        extracted_ids = []
        
        for modification in modifications:
            modification_lower = modification.lower()
            
            # ファイル関連のキーワードでフィルタリング
            for spec_ext in plan_context.plan_state.action_specs:
                spec_content = f"{spec_ext.base.operation} {spec_ext.base.path}".lower()
                
                # キーワードマッチング
                if ("ファイル作成" in modification_lower and "create" in spec_content) or \
                   ("ファイル書き込み" in modification_lower and "write" in spec_content) or \
                   ("ファイル読み込み" in modification_lower and "read" in spec_content):
                    if spec_ext.id not in extracted_ids:
                        extracted_ids.append(spec_ext.id)
        
        # 何も特定できなかった場合は最初のアクションをデフォルトとする
        if not extracted_ids and plan_context.plan_state.action_specs:
            extracted_ids = [plan_context.plan_state.action_specs[0].id]
        
        return extracted_ids
    
    def format_approval_confirmation(self, approval_result: ApprovalResult, 
                                   plan_context: PlanApprovalContext) -> str:
        """承認結果の確認メッセージをフォーマット
        
        Args:
            approval_result: 承認結果
            plan_context: プランコンテキスト
            
        Returns:
            str: 確認メッセージ
        """
        action_descriptions = {
            ApprovalAction.APPROVE_ALL: "全てのアクションを実行",
            ApprovalAction.APPROVE_PARTIAL: "部分的なアクションを実行",
            ApprovalAction.REJECT: "プランを拒否",
            ApprovalAction.REQUEST_MODIFICATION: "プランの修正を要求",
            ApprovalAction.REQUEST_DETAILS: "詳細確認を要求"
        }
        
        message_parts = [
            f"以下の解釈で正しいですか？",
            f"",
            f"アクション: {action_descriptions.get(approval_result.action, '不明')}",
            f"理由: {approval_result.reasoning}",
            f"確信度: {approval_result.confidence:.1%}"
        ]
        
        if approval_result.approved_spec_ids:
            approved_actions = []
            for spec_ext in plan_context.plan_state.action_specs:
                if spec_ext.id in approval_result.approved_spec_ids:
                    approved_actions.append(f"- {spec_ext.base.operation}: {spec_ext.base.path}")
            
            if approved_actions:
                message_parts.extend([
                    f"",
                    f"承認されたアクション:",
                    *approved_actions
                ])
        
        if approval_result.modifications_requested:
            message_parts.extend([
                f"",
                f"修正要求:",
                *[f"- {mod}" for mod in approval_result.modifications_requested]
            ])
        
        message_parts.extend([
            f"",
            f"正しい場合は「はい」、修正が必要な場合は「いいえ」を入力してください。"
        ])
        
        return "\n".join(message_parts)