"""
IntegratedPromptSystem - Phase 2: Base + Main プロンプトの統合
DuckFlowの3層プロンプトシステムの統合版を実装する
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_prompt_generator import BasePromptGenerator
from .main_prompt_generator import MainPromptGenerator
from .context_assembler import ContextAssembler
from .llm_call_manager import LLMCallManager


class IntegratedPromptSystem:
    """Base + Main プロンプトの統合システム"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 各コンポーネントの初期化
        self.base_generator = BasePromptGenerator()
        self.main_generator = MainPromptGenerator()
        self.context_assembler = ContextAssembler()
        self.llm_manager = LLMCallManager()
        
        # 設定
        self.max_total_length = 3000
        self.enable_context_assembly = True
        self.enable_llm_calls = True
    
    def generate_base_main_prompt(self, 
                                 agent_state: Optional[Dict[str, Any]] = None,
                                 conversation_history: Optional[List[Dict[str, Any]]] = None,
                                 session_data: Optional[Dict[str, Any]] = None) -> str:
        """Base + Main プロンプトを生成"""
        try:
            self.logger.info("Base + Main プロンプト生成開始")
            
            # 1. Base Prompt生成
            base_prompt = self.base_generator.generate(session_data)
            self.logger.debug(f"Base Prompt生成完了: {len(base_prompt)}文字")
            
            # 2. Main Prompt生成
            main_prompt = self.main_generator.generate(agent_state)
            self.logger.debug(f"Main Prompt生成完了: {len(main_prompt)}文字")
            
            # 3. プロンプトの結合
            combined_prompt = self._combine_prompts(base_prompt, main_prompt)
            self.logger.debug(f"プロンプト結合完了: {len(combined_prompt)}文字")
            
            # 4. 長さ制限の適用
            if len(combined_prompt) > self.max_total_length:
                combined_prompt = self._truncate_prompt(combined_prompt)
                self.logger.warning(f"プロンプトが長すぎるため切り詰め: {len(combined_prompt)}文字")
            
            self.logger.info(f"Base + Main プロンプト生成完了: {len(combined_prompt)}文字")
            return combined_prompt
            
        except Exception as e:
            self.logger.error(f"プロンプト生成エラー: {e}")
            return f"プロンプト生成エラー: {str(e)}"
    
    def _combine_prompts(self, base_prompt: str, main_prompt: str) -> str:
        """プロンプトを結合"""
        separator = "\n\n" + "="*50 + "\n\n"
        return base_prompt + separator + main_prompt
    
    def _truncate_prompt(self, prompt: str) -> str:
        """プロンプトを適切に切り詰める"""
        # 優先順位に基づいて切り詰め
        # 1. Base Prompt（人格・憲法）は保持
        # 2. Main Prompt（固定5項目）は保持
        # 3. 会話履歴を削減
        
        lines = prompt.split('\n')
        base_section = []
        main_section = []
        other_sections = []
        
        current_section = None
        
        for line in lines:
            if line.startswith('あなたはDuckflowのAIアシスタントです'):
                current_section = 'base'
                base_section.append(line)
            elif line.startswith('# 現在の対話状況'):
                current_section = 'main'
                main_section.append(line)
            elif line.startswith('##'):
                if current_section == 'base':
                    base_section.append(line)
                elif current_section == 'main':
                    main_section.append(line)
                else:
                    other_sections.append(line)
            elif current_section == 'base':
                base_section.append(line)
            elif current_section == 'main':
                main_section.append(line)
            else:
                other_sections.append(line)
        
        # 必須部分を保持
        essential_prompt = '\n'.join(base_section + main_section)
        
        # 残りの部分を追加（長さ制限内で）
        remaining_length = self.max_total_length - len(essential_prompt) - 100  # 余裕を持たせる
        
        if remaining_length > 0 and other_sections:
            other_prompt = '\n'.join(other_sections[:remaining_length // 20])  # 概算
            return essential_prompt + '\n\n' + other_prompt + '\n\n... (プロンプトが長いため省略)'
        
        return essential_prompt
    
    def call_llm_with_prompt(self, 
                            agent_state: Optional[Dict[str, Any]] = None,
                            conversation_history: Optional[List[Dict[str, Any]]] = None,
                            session_data: Optional[Dict[str, Any]] = None,
                            expected_format: str = "json") -> Dict[str, Any]:
        """プロンプトを生成してLLMを呼び出し"""
        try:
            if not self.enable_llm_calls:
                return {
                    'success': False,
                    'error': 'LLM呼び出しが無効化されています'
                }
            
            # プロンプト生成
            prompt = self.generate_base_main_prompt(agent_state, conversation_history, session_data)
            
            # LLM呼び出し
            response = self.llm_manager.call_llm(prompt, expected_format)
            
            # 会話履歴の更新
            if agent_state and conversation_history:
                self._update_conversation_history(agent_state, conversation_history, prompt, response)
            
            return response
            
        except Exception as e:
            self.logger.error(f"LLM呼び出しエラー: {e}")
            return {
                'success': False,
                'error': str(e),
                'content': None
            }
    
    def _update_conversation_history(self, 
                                   agent_state: Dict[str, Any],
                                   conversation_history: List[Dict[str, Any]],
                                   prompt: str,
                                   response: Dict[str, Any]):
        """会話履歴を更新"""
        try:
            # 最新の会話を取得
            latest_user = self._extract_latest_user_message(agent_state)
            latest_assistant = self._extract_latest_assistant_message(response)
            
            if latest_user and latest_assistant:
                # 会話履歴に追加
                conversation_record = {
                    'user': latest_user,
                    'assistant': latest_assistant,
                    'timestamp': datetime.now().isoformat()
                }
                conversation_history.append(conversation_record)
                
                # Base Promptの会話履歴も更新
                self.base_generator.add_conversation(f"{latest_user} → {latest_assistant}")
                
                # Main Promptの会話履歴も更新
                self.main_generator.add_conversation(latest_user, latest_assistant)
                
                self.logger.debug("会話履歴を更新しました")
                
        except Exception as e:
            self.logger.warning(f"会話履歴更新エラー: {e}")
    
    def _extract_latest_user_message(self, agent_state: Dict[str, Any]) -> Optional[str]:
        """最新のユーザーメッセージを抽出"""
        # AgentStateから最新のユーザーメッセージを取得
        # 実際の実装では、AgentStateの構造に応じて調整が必要
        if 'last_user_message' in agent_state:
            return agent_state['last_user_message']
        elif 'messages' in agent_state and agent_state['messages']:
            # 最新のユーザーメッセージを探す
            for msg in reversed(agent_state['messages']):
                if msg.get('role') == 'user':
                    return msg.get('content', '')
        return None
    
    def _extract_latest_assistant_message(self, response: Dict[str, Any]) -> Optional[str]:
        """最新のアシスタントメッセージを抽出"""
        if response.get('success') and response.get('content'):
            content = response['content']
            # JSON形式の場合は内容を抽出
            if isinstance(content, str) and content.strip().startswith('{'):
                try:
                    import json
                    parsed = json.loads(content)
                    if 'rationale' in parsed:
                        return parsed['rationale']
                except:
                    pass
            return str(content)[:200]  # 200文字制限
        return None
    
    def get_prompt_statistics(self) -> Dict[str, Any]:
        """プロンプト統計を取得"""
        base_length = self.base_generator.get_prompt_length()
        main_length = self.main_generator.get_prompt_length()
        
        return {
            'base_prompt_length': base_length,
            'main_prompt_length': main_length,
            'total_length': base_length + main_length,
            'max_total_length': self.max_total_length,
            'llm_statistics': self.llm_manager.get_call_statistics()
        }
    
    def update_settings(self, **kwargs):
        """設定を更新"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                self.logger.info(f"設定を更新: {key} = {value}")
    
    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式で取得"""
        return {
            'max_total_length': self.max_total_length,
            'enable_context_assembly': self.enable_context_assembly,
            'enable_llm_calls': self.enable_llm_calls,
            'base_generator': self.base_generator.to_dict(),
            'main_generator': self.main_generator.to_dict(),
            'context_assembler': self.context_assembler.to_dict(),
            'llm_manager': self.llm_manager.to_dict(),
            'statistics': self.get_prompt_statistics()
        }
