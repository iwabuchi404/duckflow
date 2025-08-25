"""
PromptContextService - 3パターンのプロンプト合成サービス
Base/Main/Specializedの3層プロンプトシステムを統合管理

PromptCompilerとの統合により、記憶注入機能を強化
"""

import logging
from typing import Optional, Dict, Any, List
from enum import Enum

from ..state.agent_state import AgentState
from ..state.enums import Step, Status
from .context_builder import PromptContextBuilder
from .base_prompt_generator import BasePromptGenerator
from .specialized_prompt_generator import SpecializedPromptGenerator
from .prompt_compiler import PromptCompiler


class PromptPattern(Enum):
    """プロンプトパターンの定義"""
    BASE_SPECIALIZED = "base_specialized"      # 軽量版: Base + Specializedのみ
    BASE_MAIN = "base_main"                    # 標準版: Base + Main
    BASE_MAIN_SPECIALIZED = "base_main_specialized"  # 完全版: Base + Main + Specialized


class PromptContextService:
    """3パターンのプロンプトを合成するサービス - PromptCompiler統合版"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.context_builder = PromptContextBuilder()
        self.base_generator = BasePromptGenerator()
        self.specialized_generator = SpecializedPromptGenerator()
        
        # PromptCompilerとの統合
        self.prompt_compiler = PromptCompiler()
        
        # トークン制限設定
        self.token_limits = {
            PromptPattern.BASE_SPECIALIZED: 2000,      # 軽量版: 2K
            PromptPattern.BASE_MAIN: 4000,             # 標準版: 4K
            PromptPattern.BASE_MAIN_SPECIALIZED: 6000  # 完全版: 6K
        }
        
        self.logger.info("PromptContextService初期化完了（PromptCompiler統合版）")
    
    def compose(self, pattern: PromptPattern, agent_state: AgentState) -> str:
        """3パターンのプロンプトを合成（従来方式）"""
        try:
            self.logger.debug(f"プロンプト合成開始: pattern={pattern.value}")
            
            # Baseコンテキストを構築
            base = self._build_base_context()
            
            if pattern == PromptPattern.BASE_SPECIALIZED:
                # 軽量版: Base + Specializedのみ
                specialized = self._build_specialized_context(agent_state)
                result = f"{base}\n\n{specialized}"
                
            elif pattern == PromptPattern.BASE_MAIN:
                # 標準版: Base + Main
                main = self._build_main_context(agent_state)
                result = f"{base}\n\n{main}"
                
            elif pattern == PromptPattern.BASE_MAIN_SPECIALIZED:
                # 完全版: Base + Main + Specialized
                main = self._build_main_context(agent_state)
                specialized = self._build_specialized_context(agent_state)
                result = f"{base}\n\n{main}\n\n{specialized}"
                
            else:
                # デフォルト: Base + Main
                self.logger.warning(f"未知のパターン: {pattern}, デフォルト使用")
                main = self._build_main_context(agent_state)
                result = f"{base}\n\n{main}"
            
            # トークン制限チェック
            result = self._apply_token_limit(result, pattern)
            
            self.logger.debug(f"プロンプト合成完了: pattern={pattern.value}, 長さ={len(result)}")
            return result
            
        except Exception as e:
            self.logger.error(f"プロンプト合成エラー: {e}")
            # エラー時は最小限のBaseコンテキストを返す
            return self._build_base_context()
    
    def compose_with_memory(self, pattern: PromptPattern, agent_state: AgentState,
                           target_file: Optional[str] = None) -> str:
        """記憶データを統合した3層プロンプトを合成（PromptCompiler統合版）
        
        Args:
            pattern: プロンプトパターン
            agent_state: エージェント状態
            target_file: 対象ファイル（オプション）
            
        Returns:
            記憶データが統合されたプロンプト
        """
        try:
            # デバッグ情報の出力
            self.logger.info(f"記憶統合プロンプト合成開始: pattern={pattern.value}")
            self.logger.info(f"会話履歴数: {len(agent_state.conversation_history) if agent_state.conversation_history else 0}")
            self.logger.info(f"短期記憶キー数: {len(agent_state.short_term_memory) if agent_state.short_term_memory else 0}")
            
            # 各層のコンテキストを構築
            base_context = self._build_base_context()
            main_context = self._build_main_context(agent_state)
            specialized_context = self._build_specialized_context(agent_state)
            
            # 各層の内容をログ出力（デバッグ用）
            self.logger.debug(f"Base層長さ: {len(base_context)}文字")
            self.logger.debug(f"Main層長さ: {len(main_context)}文字")
            self.logger.debug(f"Specialized層長さ: {len(specialized_context)}文字")
            
            # PromptCompilerを使用して記憶データを統合
            result = self.prompt_compiler.compile_with_memory(
                pattern=pattern.value,
                base_context=base_context,
                main_context=main_context,
                specialized_context=specialized_context,
                agent_state=agent_state,
                target_file=target_file
            )
            
            # 生成されたプロンプトの内容をログ出力（最初の500文字）
            self.logger.info(f"記憶統合プロンプト合成完了: pattern={pattern.value}, 長さ={len(result)}")
            self.logger.info(f"生成されたプロンプト（最初の500文字）: {result[:500]}...")
            
            return result
            
        except Exception as e:
            self.logger.error(f"記憶統合プロンプト合成エラー: {e}")
            # エラー時は従来方式でフォールバック
            return self.compose(pattern, agent_state)
    
    def compose_enhanced(self, pattern: PromptPattern, agent_state: AgentState,
                         target_file: Optional[str] = None, 
                         use_memory_injection: bool = True) -> str:
        """拡張版プロンプト合成（記憶注入の有効/無効を選択可能）
        
        Args:
            pattern: プロンプトパターン
            agent_state: エージェント状態
            target_file: 対象ファイル（オプション）
            use_memory_injection: 記憶注入を使用するかどうか
            
        Returns:
            合成されたプロンプト
        """
        try:
            if use_memory_injection:
                # 記憶注入版
                return self.compose_with_memory(pattern, agent_state, target_file)
            else:
                # 従来版
                return self.compose(pattern, agent_state)
                
        except Exception as e:
            self.logger.error(f"拡張版プロンプト合成エラー: {e}")
            # エラー時は従来方式でフォールバック
            return self.compose(pattern, agent_state)
    
    def get_memory_statistics(self, agent_state: AgentState) -> Dict[str, Any]:
        """記憶データの統計情報を取得（PromptCompiler経由）"""
        try:
            return self.prompt_compiler.get_memory_statistics(agent_state)
        except Exception as e:
            self.logger.error(f"記憶統計情報取得エラー: {e}")
            return {"error": f"記憶統計情報取得エラー: {str(e)}"}
    
    def validate_and_enhance_pattern(self, pattern: str, agent_state: AgentState) -> str:
        """パターンを検証し、必要に応じて最適化
        
        Args:
            pattern: パターン文字列
            agent_state: エージェント状態
            
        Returns:
            最適化されたパターン
        """
        try:
            # パターンの検証
            validated_pattern = self.validate_pattern(pattern)
            
            # エージェント状態に基づくパターン最適化
            optimized_pattern = self._optimize_pattern_for_state(validated_pattern, agent_state)
            
            self.logger.info(f"パターン最適化: {pattern} -> {optimized_pattern.value}")
            return optimized_pattern.value
            
        except Exception as e:
            self.logger.error(f"パターン最適化エラー: {e}")
            return "base_main"  # デフォルト
    
    def _optimize_pattern_for_state(self, pattern: PromptPattern, agent_state: AgentState) -> PromptPattern:
        """エージェント状態に基づいてパターンを最適化"""
        try:
            # 現在のステップに基づく最適化
            current_step = self._get_current_step(agent_state)
            
            if current_step == Step.EXECUTION:
                # 実行中は完全版を使用
                if pattern != PromptPattern.BASE_MAIN_SPECIALIZED:
                    return PromptPattern.BASE_MAIN_SPECIALIZED
            
            elif current_step == Step.PLANNING:
                # 計画中は完全版または標準版を使用
                if pattern == PromptPattern.BASE_SPECIALIZED:
                    return PromptPattern.BASE_MAIN
            
            elif current_step == Step.REVIEW:
                # レビュー中は完全版を使用
                if pattern != PromptPattern.BASE_MAIN_SPECIALIZED:
                    return PromptPattern.BASE_MAIN_SPECIALIZED
            
            # 会話履歴の長さに基づく最適化
            conversation_length = len(agent_state.conversation_history) if agent_state.conversation_history else 0
            
            if conversation_length > 20:
                # 会話が長い場合は完全版を使用
                if pattern != PromptPattern.BASE_MAIN_SPECIALIZED:
                    return PromptPattern.BASE_MAIN_SPECIALIZED
            elif conversation_length < 5:
                # 会話が短い場合は軽量版を使用
                if pattern == PromptPattern.BASE_MAIN_SPECIALIZED:
                    return PromptPattern.BASE_SPECIALIZED
            
            return pattern
            
        except Exception as e:
            self.logger.warning(f"パターン最適化エラー: {e}")
            return pattern
    
    def _build_base_context(self) -> str:
        """Baseコンテキスト（システム設定・制約・安全ルール）を構築"""
        try:
            return self.base_generator.generate_base_context()
        except Exception as e:
            self.logger.error(f"Baseコンテキスト構築エラー: {e}")
            return self._get_fallback_base_context()
    
    def _build_main_context(self, agent_state: AgentState) -> str:
        """Mainコンテキスト（会話履歴・固定5項目・短期記憶）を構築"""
        try:
            self.logger.debug(f"Mainコンテキスト構築開始: 会話履歴数={len(agent_state.conversation_history) if agent_state.conversation_history else 0}")
            
            # 直接的な会話履歴の構築
            main_context = "現在のコンテキスト:\n\n"
            
            # 固定5項目
            if hasattr(agent_state, 'goal') and agent_state.goal:
                main_context += f"目標: {agent_state.goal}\n"
            if hasattr(agent_state, 'why_now') and agent_state.why_now:
                main_context += f"なぜ今やるのか: {agent_state.why_now}\n"
            if hasattr(agent_state, 'constraints') and agent_state.constraints:
                main_context += f"制約: {', '.join(agent_state.constraints)}\n"
            if hasattr(agent_state, 'plan_brief') and agent_state.plan_brief:
                main_context += f"直近の計画: {', '.join(agent_state.plan_brief)}\n"
            if hasattr(agent_state, 'open_questions') and agent_state.open_questions:
                main_context += f"未解決の問い: {', '.join(agent_state.open_questions)}\n"
            
            # 会話履歴（最新5件）
            if agent_state.conversation_history:
                main_context += "\n直近の会話履歴:\n"
                recent_messages = agent_state.conversation_history[-5:]
                for i, msg in enumerate(recent_messages):
                    role = msg.role if hasattr(msg, 'role') else 'unknown'
                    content = msg.content if hasattr(msg, 'content') else ''
                    if content:
                        label = 'ユーザー' if role == 'user' else 'アシスタント'
                        # 最新のメッセージを強調
                        if i == len(recent_messages) - 1:
                            main_context += f"→ {label}: {content[:300]}...\n"
                        else:
                            main_context += f"  {label}: {content[:200]}...\n"
            
            # 短期記憶の情報
            if hasattr(agent_state, 'short_term_memory') and agent_state.short_term_memory:
                short_term = agent_state.short_term_memory
                if short_term:
                    main_context += "\n短期記憶:\n"
                    for key, value in list(short_term.items())[:3]:  # 最新3件
                        if value:
                            main_context += f"- {key}: {str(value)[:100]}...\n"
            
            self.logger.debug(f"Mainコンテキスト構築完了: 長さ={len(main_context)}文字")
            return main_context
            
        except Exception as e:
            self.logger.error(f"Mainコンテキスト構築エラー: {e}")
            return self._get_fallback_main_context()
    
    def _build_specialized_context(self, agent_state: AgentState) -> str:
        """Specializedコンテキスト（専門知識・手順書）を構築"""
        try:
            # 現在のStep/Statusに応じた専門知識・手順書を取得
            step = self._get_current_step(agent_state)
            status = self._get_current_status(agent_state)
            
            if step == Step.EXECUTION:
                return self.specialized_generator.generate_execution_guidelines(agent_state)
            elif step == Step.REVIEW:
                return self.specialized_generator.generate_review_guidelines(agent_state)
            elif step == Step.PLANNING:
                return self.specialized_generator.generate_planning_guidelines(agent_state)
            else:
                return self.specialized_generator.generate_general_guidelines(agent_state)
                
        except Exception as e:
            self.logger.error(f"Specializedコンテキスト構築エラー: {e}")
            return self._get_fallback_specialized_context()
    
    def _get_current_step(self, agent_state: AgentState) -> Step:
        """現在のStepを安全に取得"""
        try:
            if hasattr(agent_state, 'current_step'):
                step = agent_state.current_step
                if isinstance(step, Step):
                    return step
                elif isinstance(step, str):
                    # 文字列からStepを推測
                    for s in Step:
                        if s.value.lower() == step.lower():
                            return s
            return Step.IDLE
        except Exception:
            return Step.IDLE
    
    def _get_current_status(self, agent_state: AgentState) -> Status:
        """現在のStatusを安全に取得"""
        try:
            if hasattr(agent_state, 'current_status'):
                status = agent_state.current_status
                if isinstance(status, Status):
                    return status
                elif isinstance(status, str):
                    # 文字列からStatusを推測
                    for s in Status:
                        if s.value.lower() == status.lower():
                            return s
            return Status.PENDING
        except Exception:
            return Status.PENDING
    
    def _apply_token_limit(self, prompt: str, pattern: PromptPattern) -> str:
        """トークン制限を適用（簡易実装）"""
        try:
            limit = self.token_limits.get(pattern, 4000)
            if len(prompt) > limit:
                # 制限を超えた場合、後半部分を切り詰め
                truncated = prompt[:limit-100] + "\n\n[内容が長すぎるため切り詰めました]"
                self.logger.warning(f"プロンプトが長すぎます: {len(prompt)} > {limit}, 切り詰め実行")
                return truncated
            return prompt
        except Exception as e:
            self.logger.error(f"トークン制限適用エラー: {e}")
            return prompt
    
    def _get_fallback_base_context(self) -> str:
        """フォールバック用のBaseコンテキスト"""
        return """あなたはDuckFlowのアシスタントです。
基本的なルール:
- 安全性を最優先に行動する
- ファイル操作前には必ず確認する
- エラーが発生した場合は適切に報告する"""
    
    def _get_fallback_main_context(self) -> str:
        """フォールバック用のMainコンテキスト"""
        return "現在のコンテキスト情報を取得できませんでした。基本的な情報のみで対応します。"
    
    def _get_fallback_specialized_context(self) -> str:
        """フォールバック用のSpecializedコンテキスト"""
        return "専門知識の取得に失敗しました。基本的なガイドラインで対応します。"
    
    def get_pattern_info(self, pattern: PromptPattern) -> Dict[str, Any]:
        """パターン情報を取得"""
        return {
            "pattern": pattern.value,
            "description": self._get_pattern_description(pattern),
            "token_limit": self.token_limits.get(pattern, 4000),
            "components": self._get_pattern_components(pattern)
        }
    
    def _get_pattern_description(self, pattern: PromptPattern) -> str:
        """パターンの説明を取得"""
        descriptions = {
            PromptPattern.BASE_SPECIALIZED: "軽量版: 高速処理用、Base + Specializedのみ",
            PromptPattern.BASE_MAIN: "標準版: 通常処理用、Base + Main",
            PromptPattern.BASE_MAIN_SPECIALIZED: "完全版: 複雑処理用、Base + Main + Specialized"
        }
        return descriptions.get(pattern, "不明なパターン")
    
    def _get_pattern_components(self, pattern: PromptPattern) -> list:
        """パターンの構成要素を取得"""
        components = {
            PromptPattern.BASE_SPECIALIZED: ["Base", "Specialized"],
            PromptPattern.BASE_MAIN: ["Base", "Main"],
            PromptPattern.BASE_MAIN_SPECIALIZED: ["Base", "Main", "Specialized"]
        }
        return components.get(pattern, ["Base"])
    
    def validate_pattern(self, pattern: str) -> PromptPattern:
        """パターン文字列を検証してPromptPatternに変換"""
        try:
            if isinstance(pattern, str):
                for p in PromptPattern:
                    if p.value == pattern:
                        return p
            elif isinstance(pattern, PromptPattern):
                return pattern
            
            # デフォルト値を返す
            self.logger.warning(f"無効なパターン: {pattern}, デフォルト使用")
            return PromptPattern.BASE_MAIN
            
        except Exception as e:
            self.logger.error(f"パターン検証エラー: {e}")
            return PromptPattern.BASE_MAIN
    
    def get_available_patterns(self) -> List[Dict[str, Any]]:
        """利用可能なパターン一覧を取得（PromptCompiler統合版）"""
        try:
            patterns = []
            for pattern in PromptPattern:
                pattern_info = self.get_pattern_info(pattern)
                pattern_info['memory_injection_supported'] = True
                patterns.append(pattern_info)
            
            return patterns
            
        except Exception as e:
            self.logger.error(f"パターン一覧取得エラー: {e}")
            return []
    
    def compare_patterns(self, pattern1: str, pattern2: str) -> Dict[str, Any]:
        """2つのパターンを比較"""
        try:
            p1 = self.validate_pattern(pattern1)
            p2 = self.validate_pattern(pattern2)
            
            info1 = self.get_pattern_info(p1)
            info2 = self.get_pattern_info(p2)
            
            return {
                "pattern1": info1,
                "pattern2": info2,
                "comparison": {
                    "token_difference": info1['token_limit'] - info2['token_limit'],
                    "component_difference": len(info1['components']) - len(info2['components']),
                    "recommendation": self._get_pattern_recommendation(p1, p2)
                }
            }
            
        except Exception as e:
            self.logger.error(f"パターン比較エラー: {e}")
            return {"error": f"パターン比較エラー: {str(e)}"}
    
    def _get_pattern_recommendation(self, pattern1: PromptPattern, pattern2: PromptPattern) -> str:
        """パターン選択の推奨事項を生成"""
        try:
            if pattern1 == pattern2:
                return "同じパターンです"
            
            # トークン制限の比較
            limit1 = self.token_limits.get(pattern1, 4000)
            limit2 = self.token_limits.get(pattern2, 4000)
            
            if limit1 > limit2:
                return f"{pattern1.value}の方が詳細な情報を含みますが、より多くのトークンを使用します"
            else:
                return f"{pattern2.value}の方が詳細な情報を含みますが、より多くのトークンを使用します"
                
        except Exception as e:
            self.logger.warning(f"推奨事項生成エラー: {e}")
            return "推奨事項を生成できませんでした"
