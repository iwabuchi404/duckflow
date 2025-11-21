#!/usr/bin/env python3
"""
UserResponseTool - LLMが直接呼び出せるユーザー応答生成Tool

既存の三層プロンプトシステムを活用し、アクション実行結果からユーザーへの応答を生成
"""

import logging
from typing import Dict, Any, List, Optional

from ..prompts.prompt_compiler import PromptCompiler
from ..llm.llm_client import LLMClient


class UserResponseTool:
    """LLMが直接呼び出せるユーザー応答生成Tool"""
    
    def __init__(self, prompt_compiler: PromptCompiler, llm_client: LLMClient):
        self.prompt_compiler = prompt_compiler
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)
    
    async def generate_response(self, 
                              user_input: str,
                              action_results: List[Dict[str, Any]] = [], 
                              agent_state: Optional[Any] = None, 
                              prompt_override: Optional[str] = None) -> Dict[str, Any]:
        """
        アクション実行結果やプロンプトオーバーライドからユーザーへの応答を生成する
        
        Args:
            user_input: ユーザーの元の要求
            action_results: 実行されたアクションの結果リスト
            agent_state: エージェントの現在の状態
            prompt_override: この引数が指定された場合、他の情報より優先してLLMへの指示として使用
            
        Returns:
            生成された応答の辞書
        """
        try:
            self.logger.info(f"応答生成開始: {len(action_results)}個のアクション結果, prompt_override: {prompt_override is not None}")
            
            if prompt_override:
                # prompt_overrideが指定されている場合は、それを最優先で使用
                prompt = prompt_override
            else:
                # agent_stateが辞書の場合は適切な形式に変換
                if isinstance(agent_state, dict):
                    self.logger.warning("agent_stateが辞書として渡されました。適切な形式に変換します。")
                    agent_state = None
                
                # 応答生成用のプロンプトをコンパイル
                prompt = self.prompt_compiler.compile_response_prompt(
                    pattern="base_main_specialized",
                    action_results=action_results,
                    user_input=user_input,
                    agent_state=agent_state
                )
            
            # LLMに応答生成を依頼
            response = await self._call_llm_for_response(prompt)
            
            result = {
                "success": True,
                "response": response,
                "generation_method": "llm_based_override" if prompt_override else "llm_based_summary",
                "prompt_length": len(prompt),
                "response_length": len(response),
                "action_count": len(action_results)
            }
            
            self.logger.info(f"応答生成完了: {len(response)}文字の応答を生成")
            return result
            
        except Exception as e:
            self.logger.error(f"応答生成エラー: {e}", exc_info=True)
            fallback_response = self._generate_fallback_response(action_results, user_input)
            
            result = {
                "success": False,
                "error": str(e),
                "fallback_response": fallback_response,
                "generation_method": "fallback",
                "action_count": len(action_results)
            }
            
            return result
    
    async def _call_llm_for_response(self, prompt: str) -> str:
        """LLMに応答生成を依頼"""
        try:
            # LLM呼び出し（ツール使用を明示的に無効化）
            response = await self.llm_client.chat(
                prompt=prompt,
                tools=False,  # ツール使用を無効化
                tool_choice="none"  # ツール選択を無効化
            )
            
            # レスポンスの検証
            if not response or not response.content:
                raise ValueError("LLMからの応答が空です")
            
            return response.content
            
        except Exception as e:
            self.logger.error(f"LLM呼び出しエラー: {e}")
            raise
    
    def _generate_fallback_response(self, action_results: List[Dict[str, Any]], user_input: str) -> str:
        """フォールバック用の応答を生成"""
        self.logger.info("フォールバック応答を生成")
        
        try:
            # 基本的な応答構造を構築
            response_lines = []
            response_lines.append(f"ユーザーの要求「{user_input}」の処理が完了しました。")
            
            if action_results:
                response_lines.append("\n実行されたアクション:")
                for i, result in enumerate(action_results, 1):
                    operation = result.get('operation', '不明な操作')
                    success = result.get('success', False)
                    status = "成功" if success else "失敗"
                    response_lines.append(f"{i}. {operation}: {status}")
                    
                    if result.get('data'):
                        data_summary = str(result['data'])[:100]
                        if len(str(result['data'])) > 100:
                            data_summary += "..."
                        response_lines.append(f"   結果: {data_summary}")
                    
                    if result.get('error_message'):
                        response_lines.append(f"   エラー: {result['error_message']}")
                    response_lines.append("")
                
                # 次のステップの提案
                response_lines.append("次のステップについて何かご質問がございましたら、お気軽にお聞かせください。")
            else:
                response_lines.append("実行されたアクションはありません。")
                response_lines.append("何かお手伝いできることがございましたら、お聞かせください。")
            
            return "\n".join(response_lines)
            
        except Exception as e:
            self.logger.error(f"フォールバック応答生成エラー: {e}")
            return f"申し訳ありません。処理中にエラーが発生しました: {str(e)}"
    
    def _format_action_summary(self, action_results: List[Dict[str, Any]]) -> str:
        """アクション結果の要約をフォーマット"""
        if not action_results:
            return "実行されたアクションはありません"
        
        summary_lines = []
        success_count = sum(1 for result in action_results if result.get('success', False))
        total_count = len(action_results)
        
        summary_lines.append(f"実行されたアクション: {total_count}件")
        summary_lines.append(f"成功: {success_count}件")
        summary_lines.append(f"失敗: {total_count - success_count}件")
        
        return "\n".join(summary_lines)
    
    def _extract_error_summary(self, action_results: List[Dict[str, Any]]) -> str:
        """エラー情報の要約を抽出"""
        errors = []
        for result in action_results:
            if not result.get('success', False):
                error_msg = result.get('error_message', '不明なエラー')
                operation = result.get('operation', '不明な操作')
                errors.append(f"{operation}: {error_msg}")
        
        if not errors:
            return "エラーは発生していません"
        
        return "\n".join(errors)
