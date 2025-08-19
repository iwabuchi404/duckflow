"""
BasePromptGenerator - Phase 2: 基本人格と制約の生成
DuckFlowのBase Prompt（人格・憲法）を生成する
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional


class BasePromptGenerator:
    """基本人格と制約の生成器"""
    
    def __init__(self):
        self.base_personality = {
            "name": "DuckFlow AI Assistant",
            "core_traits": [
                "安全第一、正確性重視、継続性を大切にする",
                "ユーザーの学習レベルに合わせた説明を行う",
                "エラーが発生した場合は適切に説明し、解決策を提案する"
            ],
            "safety_principles": [
                "システムファイルは変更しない",
                "危険なコマンドは実行しない",
                "作業フォルダ外の操作は承認を求める"
            ],
            "constraints": [
                "ファイル操作は安全な場所のみ",
                "実行前に必ず内容を確認",
                "エラー時は適切な復旧処理を実行"
            ]
        }
        
        self.session_info = {
            "session_id": None,
            "total_conversations": 0,
            "last_updated": None
        }
        
        self.conversation_memory = []
    
    def generate(self, session_data: Optional[Dict[str, Any]] = None) -> str:
        """Base Promptを生成"""
        # セッション情報の更新
        if session_data:
            self.session_info.update(session_data)
        
        # 現在時刻の更新
        self.session_info["last_updated"] = datetime.now().isoformat()
        
        # 基本人格プロンプトの構築
        prompt = self._build_base_prompt()
        
        return prompt
    
    def _build_base_prompt(self) -> str:
        """基本プロンプトを構築"""
        prompt = f"""あなたは{self.base_personality['name']}です。

基本人格:
{self._format_list(self.base_personality['core_traits'])}

安全原則:
{self._format_list(self.base_personality['safety_principles'])}

制約:
{self._format_list(self.base_personality['constraints'])}

現在のセッション:
- セッションID: {self.session_info.get('session_id', 'N/A')}
- 総会話数: {self.session_info.get('total_conversations', 0)}
- 最後の更新: {self.session_info.get('last_updated', 'N/A')}

会話履歴（最新5件）:
{self._format_conversation_history()}

あなたは常に上記の原則に従い、安全で有用な支援を提供します。"""
        
        return prompt
    
    def _format_list(self, items: list) -> str:
        """リストをフォーマット"""
        return "\n".join([f"- {item}" for item in items])
    
    def _format_conversation_history(self) -> str:
        """会話履歴をフォーマット"""
        if not self.conversation_memory:
            return "- 会話履歴はありません"
        
        # 最新5件を表示
        recent = self.conversation_memory[-5:]
        formatted = []
        
        for i, conv in enumerate(recent, 1):
            summary = conv.get('summary', '要約なし')[:100]  # 100文字制限
            formatted.append(f"{i}. {summary}")
        
        return "\n".join(formatted)
    
    def add_conversation(self, summary: str):
        """会話履歴を追加"""
        self.conversation_memory.append({
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        })
        
        # 最大10件まで保持
        if len(self.conversation_memory) > 10:
            self.conversation_memory = self.conversation_memory[-10:]
        
        # 総会話数を更新
        self.session_info['total_conversations'] += 1
    
    def update_session_id(self, session_id: str):
        """セッションIDを更新"""
        self.session_info['session_id'] = session_id
    
    def get_prompt_length(self) -> int:
        """プロンプトの長さを取得"""
        return len(self.generate())
    
    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式で取得"""
        return {
            'base_personality': self.base_personality,
            'session_info': self.session_info,
            'conversation_memory': self.conversation_memory
        }
