"""
User Consultation - ユーザー相談システム
Duck Pacemakerが介入時にユーザーに状況説明と選択肢を提示
"""

import logging
from typing import Dict, Any, List, Optional
from enum import Enum

from ..state.agent_state import AgentState
from ..ui.rich_ui import rich_ui

logger = logging.getLogger(__name__)


class InterventionPattern(Enum):
    """介入パターンの種類"""
    PROGRESS_STAGNATION = "progress_stagnation"  # 進捗停滞
    CONFIDENCE_LOSS = "confidence_loss"          # 自信不足
    THINKING_CONFUSION = "thinking_confusion"    # 思考混乱
    EXCESSIVE_TRIALS = "excessive_trials"        # 過度な試行


class UserConsultation:
    """ユーザー相談システム
    
    設計原則:
    - 数値ではなく状況説明による透明性
    - 4つの明確な選択肢提示
    - 協調的なAI-人間関係の構築
    """
    
    def __init__(self):
        """ユーザー相談システムを初期化"""
        self.consultation_patterns = self._initialize_patterns()
        logger.info("UserConsultation初期化完了")
    
    def _initialize_patterns(self) -> Dict[InterventionPattern, Dict[str, Any]]:
        """介入パターンを初期化
        
        Returns:
            介入パターン辞書
        """
        return {
            InterventionPattern.PROGRESS_STAGNATION: {
                "title": "進捗停滞の相談",
                "situation": "AIがタスクの進捗がなく作業を繰り返しています（{loop_count}回目）。\n同じような分析や情報収集を何度も行っており、新しい発見がない状況です。",
                "options": [
                    "作業を中止する",
                    "追加の指示や情報を提供する", 
                    "このまま作業を継続する",
                    "別のアプローチで再開する"
                ],
                "actions": ["halt", "provide_guidance", "continue", "restart_different"]
            },
            
            InterventionPattern.CONFIDENCE_LOSS: {
                "title": "自信不足の相談",
                "situation": "AIが現在の作業プランに自信を失っています。\n複雑な問題に対して適切な解決策を見つけられずにいる状況です。",
                "options": [
                    "より詳細な要件や制約を教える",
                    "問題を分割して段階的に進める",
                    "別の専門家や資料を参照する",
                    "現在のアプローチを続ける"
                ],
                "actions": ["clarify_requirements", "divide_problem", "seek_reference", "continue_current"]
            },
            
            InterventionPattern.THINKING_CONFUSION: {
                "title": "思考混乱の相談", 
                "situation": "AIの思考が一貫性を失い、混乱している状況です。\n複数の解決策を同時に検討して判断がつかない状態になっています。",
                "options": [
                    "最も重要な要件を1つ教える",
                    "作業を一旦リセットして再開する",
                    "現在までの成果を整理する",
                    "別の角度からアプローチする"
                ],
                "actions": ["focus_priority", "reset_work", "organize_results", "different_angle"]
            },
            
            InterventionPattern.EXCESSIVE_TRIALS: {
                "title": "過度な試行の相談",
                "situation": "AIが同じタスクで多くの試行を重ねており、効率が低下しています。\nこれ以上続けても良い結果が得られない可能性があります。",
                "options": [
                    "現在までの結果で満足する",
                    "問題の原因を一緒に分析する",
                    "要求を簡素化して再挑戦する",
                    "完全に別のアプローチを試す"
                ],
                "actions": ["accept_current", "analyze_together", "simplify_request", "completely_different"]
            }
        }
    
    def determine_intervention_pattern(
        self,
        state: AgentState,
        intervention_details: Dict[str, Any]
    ) -> InterventionPattern:
        """介入パターンを決定
        
        Args:
            state: AgentState インスタンス
            intervention_details: 介入詳細情報
            
        Returns:
            適切な介入パターン
        """
        try:
            reason = intervention_details.get("reason", "")
            action = intervention_details.get("action", "")
            
            # バイタル状態に基づく判定
            if state.vitals.focus < 0.3:
                return InterventionPattern.THINKING_CONFUSION
            elif state.vitals.mood < 0.5:
                return InterventionPattern.CONFIDENCE_LOSS
            elif state.vitals.stamina < 0.3:
                return InterventionPattern.EXCESSIVE_TRIALS
            else:
                # デフォルトは進捗停滞
                return InterventionPattern.PROGRESS_STAGNATION
                
        except Exception as e:
            logger.warning(f"介入パターン決定エラー: {e}")
            return InterventionPattern.PROGRESS_STAGNATION
    
    def present_consultation(
        self,
        state: AgentState,
        intervention_details: Dict[str, Any],
        current_loop: int
    ) -> Dict[str, Any]:
        """ユーザーに相談を提示
        
        Args:
            state: AgentState インスタンス
            intervention_details: 介入詳細情報
            current_loop: 現在のループ数
            
        Returns:
            ユーザー選択結果
        """
        try:
            # 介入パターンを決定
            pattern = self.determine_intervention_pattern(state, intervention_details)
            pattern_info = self.consultation_patterns[pattern]
            
            # 状況説明を生成
            situation = pattern_info["situation"].format(
                loop_count=current_loop,
                max_loops=state.graph_state.max_loops
            )
            
            # ユーザーに提示
            rich_ui.print_message("🦆 Duck Pacemaker からの相談", "warning")
            rich_ui.print_panel(situation, pattern_info["title"], "yellow")
            
            # 選択肢を表示
            rich_ui.print_message("\nどのように進めますか？", "info")
            for i, option in enumerate(pattern_info["options"], 1):
                rich_ui.print_message(f"{i}. {option}", "info")
            
            # ユーザー選択を取得
            while True:
                try:
                    choice = rich_ui.get_user_input("選択してください (1-4)").strip()
                    choice_num = int(choice)
                    
                    if 1 <= choice_num <= 4:
                        selected_option = pattern_info["options"][choice_num - 1]
                        selected_action = pattern_info["actions"][choice_num - 1]
                        
                        # 追加情報の取得（必要に応じて）
                        additional_info = self._get_additional_info(selected_action)
                        
                        result = {
                            "pattern": pattern.value,
                            "choice_number": choice_num,
                            "selected_option": selected_option,
                            "selected_action": selected_action,
                            "additional_info": additional_info,
                            "timestamp": state.last_activity.isoformat()
                        }
                        
                        logger.info(f"ユーザー選択: {pattern.value} -> {selected_option}")
                        return result
                    else:
                        rich_ui.print_message("1-4の数字を入力してください。", "warning")
                        
                except ValueError:
                    rich_ui.print_message("数字を入力してください。", "warning")
                except KeyboardInterrupt:
                    logger.info("ユーザーが相談をキャンセル")
                    return {
                        "pattern": pattern.value,
                        "cancelled": True,
                        "selected_action": "cancel"
                    }
                    
        except Exception as e:
            logger.error(f"相談提示エラー: {e}")
            return {
                "error": str(e),
                "selected_action": "continue"  # エラー時は継続
            }
    
    def _get_additional_info(self, action: str) -> Optional[str]:
        """追加情報を取得（必要に応じて）
        
        Args:
            action: 選択されたアクション
            
        Returns:
            追加情報（あれば）
        """
        try:
            if action in ["provide_guidance", "clarify_requirements"]:
                rich_ui.print_message("\n追加の指示や情報があれば入力してください（空白で省略）:", "info")
                additional = rich_ui.get_user_input("追加情報").strip()
                return additional if additional else None
            
            return None
            
        except Exception as e:
            logger.warning(f"追加情報取得エラー: {e}")
            return None
    
    def process_user_choice(
        self,
        choice_result: Dict[str, Any],
        state: AgentState
    ) -> Dict[str, Any]:
        """ユーザー選択を処理
        
        Args:
            choice_result: ユーザー選択結果
            state: AgentState インスタンス
            
        Returns:
            処理結果
        """
        try:
            action = choice_result.get("selected_action", "continue")
            
            # アクションに基づく処理
            if action == "halt":
                return {
                    "next_action": "complete",
                    "reason": "ユーザーが作業中止を選択",
                    "message": "作業を中止します。"
                }
                
            elif action == "provide_guidance":
                additional_info = choice_result.get("additional_info", "")
                if additional_info:
                    # 追加情報をメッセージとして追加
                    state.add_message("user", f"追加指示: {additional_info}")
                
                return {
                    "next_action": "continue_with_guidance",
                    "reason": "ユーザーが追加指示を提供",
                    "additional_context": additional_info,
                    "message": "追加指示を受けて作業を継続します。"
                }
                
            elif action == "continue":
                return {
                    "next_action": "continue",
                    "reason": "ユーザーが継続を選択",
                    "message": "作業を継続します。"
                }
                
            elif action in ["restart_different", "different_angle", "completely_different"]:
                return {
                    "next_action": "restart",
                    "reason": "ユーザーが別アプローチを選択",
                    "message": "別のアプローチで再開します。"
                }
                
            elif action == "reset_work":
                return {
                    "next_action": "reset",
                    "reason": "ユーザーがリセットを選択", 
                    "message": "作業をリセットして再開します。"
                }
                
            else:
                # その他のアクションは継続として処理
                return {
                    "next_action": "continue",
                    "reason": f"ユーザー選択: {choice_result.get('selected_option', 'unknown')}",
                    "message": "ユーザーの指示に従って作業を継続します。"
                }
                
        except Exception as e:
            logger.error(f"ユーザー選択処理エラー: {e}")
            return {
                "next_action": "continue",
                "reason": "処理エラーのため継続",
                "error": str(e)
            }
    
    def get_consultation_history(self) -> List[Dict[str, Any]]:
        """相談履歴を取得（将来拡張用）
        
        Returns:
            相談履歴のリスト
        """
        # 現在はシンプル版のため空リストを返す
        return []
    
    def get_pattern_info(self, pattern: InterventionPattern) -> Dict[str, Any]:
        """特定パターンの情報を取得
        
        Args:
            pattern: 介入パターン
            
        Returns:
            パターン情報辞書
        """
        return self.consultation_patterns.get(pattern, {})
    
    def get_all_patterns(self) -> Dict[str, Dict[str, Any]]:
        """全パターン情報を取得
        
        Returns:
            全パターン情報辞書
        """
        return {pattern.value: info for pattern, info in self.consultation_patterns.items()}