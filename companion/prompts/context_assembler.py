"""
ContextAssembler - Phase 2: AgentStateからの文脈構築
DuckFlowの文脈構築システムを実装する
"""

from typing import Dict, Any, Optional, List
from datetime import datetime


class ContextAssembler:
    """AgentStateから文脈を構築する"""
    
    def __init__(self):
        self.max_context_length = 1000
        self.max_file_refs = 5
        self.max_decision_logs = 3
    
    def assemble_context(self, agent_state: Dict[str, Any], 
                        conversation_history: Optional[List[Dict[str, Any]]] = None) -> str:
        """AgentStateから文脈を構築"""
        try:
            context_parts = []
            
            # 1. 基本状態情報
            basic_state = self._extract_basic_state(agent_state)
            if basic_state:
                context_parts.append(basic_state)
            
            # 2. 固定5項目
            fixed_items = self._extract_fixed_five_items(agent_state)
            if fixed_items:
                context_parts.append(fixed_items)
            
            # 3. 関連ファイル参照
            file_refs = self._extract_file_references(agent_state)
            if file_refs:
                context_parts.append(file_refs)
            
            # 4. 決定ログ
            decision_logs = self._extract_decision_logs(agent_state)
            if decision_logs:
                context_parts.append(decision_logs)
            
            # 5. 会話履歴
            if conversation_history:
                conv_context = self._extract_conversation_context(conversation_history)
                if conv_context:
                    context_parts.append(conv_context)
            
            # 文脈を結合
            assembled_context = "\n\n".join(context_parts)
            
            # 長さ制限の適用
            if len(assembled_context) > self.max_context_length:
                assembled_context = self._truncate_context(assembled_context)
            
            return assembled_context
            
        except Exception as e:
            return f"文脈構築エラー: {str(e)}"
    
    def _extract_basic_state(self, agent_state: Dict[str, Any]) -> Optional[str]:
        """基本状態情報を抽出"""
        basic_info = []
        
        # ステップとステータス
        if 'step' in agent_state:
            basic_info.append(f"現在のステップ: {agent_state['step']}")
        if 'status' in agent_state:
            basic_info.append(f"現在のステータス: {agent_state['status']}")
        
        # 最後の変更
        if 'last_delta' in agent_state and agent_state['last_delta']:
            basic_info.append(f"最後の変更: {agent_state['last_delta']}")
        
        # 承認待ち状態
        if 'pending_gate' in agent_state and agent_state['pending_gate']:
            basic_info.append("承認待ち: はい")
        
        if basic_info:
            return "## 基本状態\n" + "\n".join(basic_info)
        
        return None
    
    def _extract_fixed_five_items(self, agent_state: Dict[str, Any]) -> Optional[str]:
        """固定5項目を抽出"""
        fixed_items = []
        
        # 固定5項目のキー
        fixed_keys = ['goal', 'why_now', 'constraints', 'plan_brief', 'open_questions']
        
        for key in fixed_keys:
            if key in agent_state and agent_state[key]:
                value = agent_state[key]
                if isinstance(value, list):
                    # リストの場合は最初の2つまで
                    display_value = ', '.join(str(item)[:50] for item in value[:2])
                    if len(value) > 2:
                        display_value += f" (+{len(value)-2}件)"
                else:
                    display_value = str(value)[:100]
                
                fixed_items.append(f"- {key}: {display_value}")
        
        if fixed_items:
            return "## 固定5項目\n" + "\n".join(fixed_items)
        
        return None
    
    def _extract_file_references(self, agent_state: Dict[str, Any]) -> Optional[str]:
        """関連ファイル参照を抽出"""
        if 'context_refs' not in agent_state or not agent_state['context_refs']:
            return None
        
        file_refs = agent_state['context_refs'][:self.max_file_refs]
        formatted_refs = []
        
        for ref in file_refs:
            if ref.startswith('file:'):
                file_path = ref[5:]  # 'file:'を除去
                formatted_refs.append(f"- ファイル: {file_path}")
            elif ref.startswith('conversation:'):
                conv_id = ref[13:]  # 'conversation:'を除去
                formatted_refs.append(f"- 会話: {conv_id}")
            elif ref.startswith('plan:'):
                plan_id = ref[5:]  # 'plan:'を除去
                formatted_refs.append(f"- プラン: {plan_id}")
            else:
                formatted_refs.append(f"- 参照: {ref}")
        
        if formatted_refs:
            return "## 関連参照\n" + "\n".join(formatted_refs)
        
        return None
    
    def _extract_decision_logs(self, agent_state: Dict[str, Any]) -> Optional[str]:
        """決定ログを抽出"""
        if 'decision_log' not in agent_state or not agent_state['decision_log']:
            return None
        
        decision_logs = agent_state['decision_log'][-self.max_decision_logs:]  # 最新のもの
        formatted_logs = []
        
        for i, decision in enumerate(decision_logs, 1):
            formatted_logs.append(f"{i}. {decision[:100]}")
        
        if formatted_logs:
            return "## 決定ログ\n" + "\n".join(formatted_logs)
        
        return None
    
    def _extract_conversation_context(self, conversation_history: List[Dict[str, Any]]) -> Optional[str]:
        """会話履歴から文脈を抽出"""
        if not conversation_history:
            return None
        
        # 最新の3件を取得
        recent_conversations = conversation_history[-3:]
        formatted_conv = []
        
        for i, conv in enumerate(recent_conversations, 1):
            user_msg = conv.get('user', '')[:80]
            assistant_msg = conv.get('assistant', '')[:80]
            
            formatted_conv.append(f"{i}. ユーザー: {user_msg}")
            formatted_conv.append(f"   アシスタント: {assistant_msg}")
        
        if formatted_conv:
            return "## 直近の会話\n" + "\n".join(formatted_conv)
        
        return None
    
    def _truncate_context(self, context: str) -> str:
        """文脈を適切に切り詰める"""
        # 優先順位に基づいて切り詰め
        # 1. 会話履歴
        # 2. 決定ログ
        # 3. ファイル参照
        # 4. 固定5項目（保持）
        # 5. 基本状態（保持）
        
        lines = context.split('\n')
        essential_lines = []
        other_lines = []
        
        current_section = None
        
        for line in lines:
            if line.startswith('##'):
                current_section = line
                if '基本状態' in line or '固定5項目' in line:
                    essential_lines.append(line)
                else:
                    other_lines.append(line)
            elif current_section:
                if '基本状態' in current_section or '固定5項目' in current_section:
                    essential_lines.append(line)
                else:
                    other_lines.append(line)
            else:
                essential_lines.append(line)
        
        # 必須部分を保持
        essential_context = '\n'.join(essential_lines)
        
        # 残りの部分を追加（長さ制限内で）
        remaining_length = self.max_context_length - len(essential_context) - 50  # 余裕を持たせる
        
        if remaining_length > 0 and other_lines:
            other_context = '\n'.join(other_lines[:remaining_length // 20])  # 概算
            return essential_context + '\n\n' + other_context + '\n\n... (文脈が長いため省略)'
        
        return essential_context
    
    def get_context_length(self, agent_state: Dict[str, Any], 
                          conversation_history: Optional[List[Dict[str, Any]]] = None) -> int:
        """文脈の長さを取得"""
        context = self.assemble_context(agent_state, conversation_history)
        return len(context)
    
    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式で取得"""
        return {
            'max_context_length': self.max_context_length,
            'max_file_refs': self.max_file_refs,
            'max_decision_logs': self.max_decision_logs
        }
