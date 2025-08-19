"""
EnhancedPromptSystem - Phase 3: 3パターンのプロンプトとToolRouter統合
DuckFlowのPhase 3統合システムを実装する
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_prompt_generator import BasePromptGenerator
from .main_prompt_generator import MainPromptGenerator
from .specialized_prompt_generator import SpecializedPromptGenerator
from .prompt_router import PromptRouter
from .llm_call_manager import LLMCallManager
from .conversation_gate import ConversationGate
from ..tools.tool_router import ToolRouter


class EnhancedPromptSystem:
    """Phase 3: 3パターンのプロンプトとToolRouter統合システム"""
    
    def __init__(self, work_dir: str = "./work"):
        self.logger = logging.getLogger(__name__)
        
        # 各コンポーネントの初期化
        self.base_generator = BasePromptGenerator()
        self.main_generator = MainPromptGenerator()
        self.specialized_generator = SpecializedPromptGenerator()
        self.prompt_router = PromptRouter()
        self.llm_manager = LLMCallManager()
        self.conversation_gate = ConversationGate(work_dir)
        self.tool_router = ToolRouter(work_dir)
        
        # 設定
        self.max_total_length = 5000  # Phase 3では長めに設定
        self.enable_specialized_prompts = True
        self.enable_tool_routing = True
        self.enable_llm_calls = True
        self.enable_conversation_gate = True
        
        # 使用統計
        self.prompt_usage = {
            'base_main': 0,
            'base_main_specialized': 0,
            'base_specialized': 0
        }
        
        # 承認システム統計
        self.approval_stats = {
            'total_requests': 0,
            'auto_approved': 0,
            'manual_approved': 0,
            'rejected': 0
        }
    
    def process_request(self, 
                       user_input: str,
                       agent_state: Optional[Dict[str, Any]] = None,
                       conversation_history: Optional[List[Dict[str, Any]]] = None,
                       session_data: Optional[Dict[str, Any]] = None,
                       force_pattern: Optional[str] = None) -> Dict[str, Any]:
        """ユーザー要求を処理"""
        try:
            self.logger.info(f"要求処理開始: {user_input[:50]}...")
            
            # 1. プロンプトパターンの選択
            if force_pattern:
                selected_pattern = force_pattern
                self.logger.info(f"強制パターン使用: {selected_pattern}")
            else:
                selected_pattern = self.prompt_router.select_prompt_pattern(
                    agent_state, user_input, 
                    agent_state.get('step') if agent_state else None,
                    self._build_conversation_context(conversation_history)
                )
            
            # 2. プロンプトの生成
            prompt = self.prompt_router.generate_prompt(
                selected_pattern, agent_state, conversation_history, session_data
            )
            
            # 3. LLM呼び出し
            llm_response = self.llm_manager.call_llm(prompt, expected_format="json")
            
            # 4. ツール操作の実行（必要に応じて）
            tool_results = self._execute_tool_operations(llm_response, user_input, agent_state)
            
            # 5. 統計更新
            self.prompt_usage[selected_pattern] += 1
            
            # 6. 結果の構築
            result = {
                'success': True,
                'selected_pattern': selected_pattern,
                'prompt_length': len(prompt),
                'llm_response': llm_response,
                'tool_results': tool_results,
                'processing_timestamp': datetime.now().isoformat()
            }
            
            self.logger.info(f"要求処理完了: パターン={selected_pattern}, 成功={result['success']}")
            return result
            
        except Exception as e:
            self.logger.error(f"要求処理エラー: {e}")
            return {
                'success': False,
                'error': str(e),
                'processing_timestamp': datetime.now().isoformat()
            }
    
    def _build_conversation_context(self, conversation_history: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """会話コンテキストを構築"""
        if not conversation_history:
            return {'length': 0, 'recent_operations': []}
        
        context = {
            'length': len(conversation_history),
            'recent_operations': []
        }
        
        # 最近の操作を抽出
        for conv in conversation_history[-5:]:  # 最新5件
            if 'operation' in conv:
                context['recent_operations'].append(conv['operation'])
        
        return context
    
    def _execute_tool_operations(self, llm_response: Dict[str, Any], 
                                user_input: str, 
                                agent_state: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """LLM応答に基づいてツール操作を実行"""
        tool_results = []
        
        try:
            if not self.enable_tool_routing:
                return tool_results
            
            # LLM応答からツール操作を抽出
            tool_operations = self._extract_tool_operations(llm_response, user_input, agent_state)
            
            for operation in tool_operations:
                try:
                    # ツール操作を実行
                    result = self.tool_router.route_operation(**operation)
                    tool_results.append({
                        'operation': operation,
                        'result': result,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    # 成功した場合はAgentStateを更新
                    if result.get('success') and agent_state:
                        self._update_agent_state(agent_state, operation, result)
                        
                except Exception as e:
                    tool_results.append({
                        'operation': operation,
                        'result': {
                            'success': False,
                            'error': str(e)
                        },
                        'timestamp': datetime.now().isoformat()
                    })
        
        except Exception as e:
            self.logger.warning(f"ツール操作実行エラー: {e}")
        
        return tool_results
    
    def _extract_tool_operations(self, llm_response: Dict[str, Any], 
                                user_input: str, 
                                agent_state: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """LLM応答からツール操作を抽出"""
        operations = []
        
        try:
            content = llm_response.get('content', '')
            if not content:
                return operations
            
            # JSON応答の場合は内容を解析
            if isinstance(content, str) and content.strip().startswith('{'):
                import json
                try:
                    parsed = json.loads(content)
                    
                    # ステップに基づいて操作を決定
                    step = parsed.get('step', 'PLANNING')
                    
                    if step == "EXECUTION":
                        # 実行ステップではファイル作成や書き込み
                        if "実装" in user_input or "作成" in user_input:
                            operations.append({
                                'operation': 'create',
                                'file_path': self._determine_file_path(user_input, agent_state),
                                'content': self._generate_file_content(user_input, parsed, agent_state)
                            })
                    
                    elif step == "REVIEW":
                        # レビューステップではファイル読み取り
                        if agent_state and 'context_refs' in agent_state:
                            for ref in agent_state['context_refs']:
                                if ref.startswith('file:'):
                                    operations.append({
                                        'operation': 'read',
                                        'file_path': ref[5:]  # 'file:'を除去
                                    })
                
                except json.JSONDecodeError:
                    pass
            
            # テキスト応答の場合も基本的な操作を抽出
            if not operations and "ファイル" in user_input:
                if "作成" in user_input or "実装" in user_input:
                    operations.append({
                        'operation': 'create',
                        'file_path': self._determine_file_path(user_input, agent_state),
                        'content': f"# {user_input}\n\n{content}"
                    })
        
        except Exception as e:
            self.logger.warning(f"ツール操作抽出エラー: {e}")
        
        return operations
    
    def _determine_file_path(self, user_input: str, agent_state: Optional[Dict[str, Any]]) -> str:
        """ファイルパスを決定"""
        # 入力内容に基づいてファイルパスを決定
        if "計画" in user_input or "プラン" in user_input:
            return "plan.md"
        elif "実装" in user_input:
            return "implementation.md"
        elif "設計" in user_input or "アーキテクチャ" in user_input:
            return "design.md"
        elif "レビュー" in user_input:
            return "review.md"
        else:
            return "task.md"
    
    def _generate_file_content(self, user_input: str, llm_parsed: Dict[str, Any], 
                              agent_state: Optional[Dict[str, Any]]) -> str:
        """ファイル内容を生成"""
        content_parts = []
        
        # タイトル
        content_parts.append(f"# {user_input}")
        content_parts.append("")
        
        # LLM応答の内容
        if 'rationale' in llm_parsed:
            content_parts.append(f"## 理由")
            content_parts.append(llm_parsed['rationale'])
            content_parts.append("")
        
        if 'goal_consistency' in llm_parsed:
            content_parts.append(f"## 目標との整合性")
            content_parts.append(llm_parsed['goal_consistency'])
            content_parts.append("")
        
        if 'constraint_check' in llm_parsed:
            content_parts.append(f"## 制約チェック")
            content_parts.append(llm_parsed['constraint_check'])
            content_parts.append("")
        
        # AgentStateの情報
        if agent_state:
            if 'goal' in agent_state:
                content_parts.append(f"## 目標")
                content_parts.append(agent_state['goal'])
                content_parts.append("")
            
            if 'constraints' in agent_state:
                content_parts.append(f"## 制約")
                for constraint in agent_state['constraints']:
                    content_parts.append(f"- {constraint}")
                content_parts.append("")
        
        # タイムスタンプ
        content_parts.append(f"---")
        content_parts.append(f"生成日時: {datetime.now().isoformat()}")
        
        return "\n".join(content_parts)
    
    def _update_agent_state(self, agent_state: Dict[str, Any], operation: Dict[str, Any], result: Dict[str, Any]):
        """AgentStateを更新"""
        try:
            # ファイル作成/書き込みが成功した場合
            if operation.get('operation') in ['create', 'write'] and result.get('success'):
                file_path = operation.get('file_path', '')
                if file_path:
                    # コンテキスト参照に追加
                    if 'context_refs' not in agent_state:
                        agent_state['context_refs'] = []
                    
                    ref = f"file:{file_path}"
                    if ref not in agent_state['context_refs']:
                        agent_state['context_refs'].append(ref)
                    
                    # 決定ログに追加
                    if 'decision_log' not in agent_state:
                        agent_state['decision_log'] = []
                    
                    decision = f"ファイル作成完了: {file_path}"
                    agent_state['decision_log'].append(decision)
                    
                    # 最後の変更を更新
                    agent_state['last_delta'] = f"ファイル {file_path} を作成"
            
            # ステップの更新
            if 'step' in agent_state:
                if agent_state['step'] == 'PLANNING':
                    agent_state['step'] = 'EXECUTION'
                    agent_state['last_delta'] = "ステップをPLANNINGからEXECUTIONに変更"
                elif agent_state['step'] == 'EXECUTION':
                    agent_state['step'] = 'REVIEW'
                    agent_state['last_delta'] = "ステップをEXECUTIONからREVIEWに変更"
        
        except Exception as e:
            self.logger.warning(f"AgentState更新エラー: {e}")
    
    def request_approval(self, 
                        user_input: str, 
                        operation_type: str,
                        target_path: Optional[str] = None,
                        user_id: str = "default",
                        session_id: str = "default") -> Dict[str, Any]:
        """承認リクエストを作成"""
        try:
            if not self.enable_conversation_gate:
                return {
                    'approved': True,
                    'reason': '承認システムが無効',
                    'auto_approved': True
                }
            
            # ConversationGateで承認リクエストを作成
            request = self.conversation_gate.request_approval(
                user_input, operation_type, target_path, user_id, session_id
            )
            
            # 統計を更新
            self.approval_stats['total_requests'] += 1
            if request.approval_status.value == 'approved':
                self.approval_stats['auto_approved'] += 1
            else:
                self.approval_stats['manual_approved'] += 1
            
            # 承認プロンプトを生成
            approval_prompt = self.conversation_gate.generate_approval_prompt(request)
            
            return {
                'request_id': request.request_id,
                'approved': request.approval_status.value == 'approved',
                'auto_approved': request.approval_status.value == 'approved',
                'approval_prompt': approval_prompt,
                'risk_level': request.risk_level.value,
                'expires_at': request.expires_at.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"承認リクエスト作成に失敗: {e}")
            return {
                'approved': False,
                'reason': f'承認システムエラー: {e}',
                'auto_approved': False
            }
    
    def process_approval_response(self, request_id: str, user_response: str) -> Dict[str, Any]:
        """承認レスポンスを処理"""
        try:
            if not self.enable_conversation_gate:
                return {
                    'approved': True,
                    'reason': '承認システムが無効'
                }
            
            # ConversationGateで承認レスポンスを処理
            response = self.conversation_gate.process_approval_response(request_id, user_response)
            
            # 統計を更新
            if response.approved:
                self.approval_stats['manual_approved'] += 1
            else:
                self.approval_stats['rejected'] += 1
            
            return {
                'approved': response.approved,
                'reason': response.reasoning,
                'timestamp': response.timestamp.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"承認レスポンス処理に失敗: {e}")
            return {
                'approved': False,
                'reason': f'承認処理エラー: {e}'
            }
    
    def get_approval_statistics(self) -> Dict[str, Any]:
        """承認統計を取得"""
        try:
            if not self.enable_conversation_gate:
                return {
                    'enabled': False,
                    'message': '承認システムが無効'
                }
            
            # ConversationGateの統計を取得
            gate_stats = self.conversation_gate.get_approval_statistics()
            
            # 統合統計
            return {
                'enabled': True,
                'conversation_gate': gate_stats,
                'enhanced_system': self.approval_stats,
                'pending_requests': len(self.conversation_gate.get_pending_requests())
            }
            
        except Exception as e:
            self.logger.error(f"承認統計取得に失敗: {e}")
            return {
                'enabled': False,
                'error': str(e)
            }
    
    def get_system_status(self) -> Dict[str, Any]:
        """システムの状態を取得"""
        return {
            'enhanced_prompt_system': {
                'enabled': True,
                'max_total_length': self.max_total_length,
                'enable_specialized_prompts': self.enable_specialized_prompts,
                'enable_tool_routing': self.enable_tool_routing,
                'enable_llm_calls': self.enable_llm_calls,
                'enable_conversation_gate': self.enable_conversation_gate
            },
            'prompt_usage': self.prompt_usage.copy(),
            'tool_router': self.tool_router.to_dict(),
            'llm_manager': self.llm_manager.to_dict(),
            'conversation_gate': self.get_approval_statistics(),
            'supported_patterns': self.prompt_router.get_supported_steps()
        }
    
    def update_settings(self, **kwargs):
        """設定を更新"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                self.logger.info(f"設定を更新: {key} = {value}")
    
    def reset_statistics(self):
        """統計をリセット"""
        for key in self.prompt_usage:
            self.prompt_usage[key] = 0
        
        # 承認システム統計のリセット
        for key in self.approval_stats:
            self.approval_stats[key] = 0
        
        self.prompt_router.reset_statistics()
        self.tool_router.clear_history()
        self.llm_manager.clear_history()
        self.logger.info("統計をリセットしました")
    
    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式で取得"""
        return {
            'max_total_length': self.max_total_length,
            'enable_specialized_prompts': self.enable_specialized_prompts,
            'enable_tool_routing': self.enable_tool_routing,
            'enable_llm_calls': self.enable_llm_calls,
            'prompt_usage': self.prompt_usage,
            'system_status': self.get_system_status()
        }
