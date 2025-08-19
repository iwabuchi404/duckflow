"""
MainPromptGenerator - Phase 2: 固定5項目と会話状況の生成
DuckFlowのMain Prompt（司令塔）を生成する
"""

from typing import Dict, Any, List, Optional
from datetime import datetime


class MainPromptGenerator:
    """固定5項目と会話状況の生成器"""
    
    def __init__(self):
        self.fixed_five_items = {
            "goal": "",
            "why_now": "",
            "constraints": [],
            "plan_brief": [],
            "open_questions": []
        }
        
        self.current_situation = {
            "step": "PLANNING",
            "status": "IN_PROGRESS",
            "ongoing_task": ""
        }
        
        self.recent_conversations = []
        self.max_conversations = 3
        self.max_conversation_length = 100
    
    def generate(self, agent_state: Optional[Dict[str, Any]] = None) -> str:
        """Main Promptを生成"""
        # AgentStateから固定5項目を更新
        if agent_state:
            self._update_from_agent_state(agent_state)
        
        # プロンプトを構築
        prompt = self._build_main_prompt()
        
        return prompt
    
    def _update_from_agent_state(self, agent_state: Dict[str, Any]):
        """AgentStateから固定5項目を更新"""
        # 固定5項目の更新
        for key in self.fixed_five_items.keys():
            if key in agent_state:
                if isinstance(agent_state[key], list):
                    # リストの場合は文字数制限を適用
                    self.fixed_five_items[key] = [
                        str(item)[:100] for item in agent_state[key][:3]  # 最大3個
                    ]
                else:
                    # 文字列の場合は文字数制限を適用
                    self.fixed_five_items[key] = str(agent_state[key])[:200]
        
        # 現在の状況の更新
        if 'step' in agent_state:
            self.current_situation['step'] = agent_state['step']
        if 'status' in agent_state:
            self.current_situation['status'] = agent_state['status']
        if 'ongoing_task' in agent_state:
            self.current_situation['ongoing_task'] = str(agent_state['ongoing_task'])[:200]
    
    def _build_main_prompt(self) -> str:
        """Main Promptを構築"""
        prompt = f"""# 現在の対話状況（ワーキングメモリ）

現在のステップ: {self.current_situation['step']}
現在のステータス: {self.current_situation['status']}
進行中のタスク: {self.current_situation['ongoing_task']}

# 固定5項目（文脈の核）
目標: {self.fixed_five_items['goal']}
なぜ今やるのか: {self.fixed_five_items['why_now']}
制約: {', '.join(self.fixed_five_items['constraints']) if self.fixed_five_items['constraints'] else 'なし'}
直近の計画: {', '.join(self.fixed_five_items['plan_brief']) if self.fixed_five_items['plan_brief'] else 'なし'}
未解決の問い: {', '.join(self.fixed_five_items['open_questions']) if self.fixed_five_items['open_questions'] else 'なし'}

# 直近の会話の流れ（短期記憶）
{self._format_recent_conversations()}

# 次のステップの指示
必ず以下のJSON形式で出力してください:
{{
  "rationale": "操作の理由（1行）",
  "goal_consistency": "目標との整合性（yes/no + 理由）",
  "constraint_check": "制約チェック（yes/no + 理由）",
  "next_step": "次のステップ（done/pending_user/defer/continue）",
  "step": "ステップ（PLANNING/EXECUTION/REVIEW/AWAITING_APPROVAL）",
  "state_delta": "状態変化（あれば）"
}}"""
        
        return prompt
    
    def _format_recent_conversations(self) -> str:
        """直近の会話をフォーマット"""
        if not self.recent_conversations:
            return "- 直近の会話はありません"
        
        formatted = []
        for i, conv in enumerate(self.recent_conversations, 1):
            user_msg = conv.get('user', '')[:self.max_conversation_length]
            assistant_msg = conv.get('assistant', '')[:self.max_conversation_length]
            
            formatted.append(f"{i}. ユーザー: {user_msg}")
            formatted.append(f"   アシスタント: {assistant_msg}")
        
        return "\n".join(formatted)
    
    def add_conversation(self, user_message: str, assistant_message: str):
        """会話を追加"""
        self.recent_conversations.append({
            'user': user_message,
            'assistant': assistant_message,
            'timestamp': datetime.now().isoformat()
        })
        
        # 最大件数を制限
        if len(self.recent_conversations) > self.max_conversations:
            self.recent_conversations = self.recent_conversations[-self.max_conversations:]
    
    def update_current_situation(self, step: str = None, status: str = None, ongoing_task: str = None):
        """現在の状況を更新"""
        if step:
            self.current_situation['step'] = step
        if status:
            self.current_situation['status'] = status
        if ongoing_task:
            self.current_situation['ongoing_task'] = ongoing_task
    
    def update_fixed_five_items(self, **kwargs):
        """固定5項目を更新"""
        for key, value in kwargs.items():
            if key in self.fixed_five_items:
                if isinstance(value, list):
                    # リストの場合は文字数制限を適用
                    self.fixed_five_items[key] = [
                        str(item)[:100] for item in value[:3]  # 最大3個
                    ]
                else:
                    # 文字列の場合は文字数制限を適用
                    self.fixed_five_items[key] = str(value)[:200]
    
    def get_prompt_length(self) -> int:
        """プロンプトの長さを取得"""
        return len(self.generate())
    
    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式で取得"""
        return {
            'fixed_five_items': self.fixed_five_items,
            'current_situation': self.current_situation,
            'recent_conversations': self.recent_conversations
        }
