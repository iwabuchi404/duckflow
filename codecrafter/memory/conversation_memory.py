"""
対話記憶管理システム (ステップ2c)
短期・中期記憶と要約機能を実装
"""
import tiktoken
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from ..base.llm_client import llm_manager, LLMClientError
from ..base.config import config_manager
from ..state.agent_state import ConversationMessage


class ConversationMemory:
    """対話記憶管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.config = config_manager.load_config()
        self.memory_config = self.config.memory
        
        # トークンカウンター初期化（GPTベースのエンコーダーを使用）
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4のエンコーダー
        except Exception:
            # フォールバック: 簡易的な文字数ベース推定
            self.encoding = None
    
    def count_tokens(self, text: str) -> int:
        """テキストのトークン数を推定
        
        Args:
            text: カウントするテキスト
            
        Returns:
            推定トークン数
        """
        if self.encoding:
            return len(self.encoding.encode(text))
        else:
            # フォールバック: 文字数 / 4 (日本語・英語混合の粗い推定)
            return len(text) // 4
    
    def calculate_conversation_tokens(self, messages: List[ConversationMessage]) -> int:
        """対話履歴の総トークン数を計算
        
        Args:
            messages: 対話メッセージリスト
            
        Returns:
            総トークン数
        """
        total_tokens = 0
        for message in messages:
            # メッセージ内容 + ロール情報 + メタデータ
            content_tokens = self.count_tokens(message.content)
            role_tokens = self.count_tokens(f"role:{message.role}")
            total_tokens += content_tokens + role_tokens + 10  # メタデータ用余裕
        
        return total_tokens
    
    def should_summarize(self, messages: List[ConversationMessage]) -> bool:
        """要約が必要かどうかを判定
        
        Args:
            messages: 対話メッセージリスト
            
        Returns:
            要約が必要な場合True
        """
        total_tokens = self.calculate_conversation_tokens(messages)
        trigger_tokens = self.memory_config.medium_term.get("summary_trigger_tokens", 4000)
        
        return total_tokens > trigger_tokens
    
    def create_conversation_summary(
        self, 
        messages: List[ConversationMessage],
        existing_summary: Optional[str] = None
    ) -> str:
        """対話履歴の要約を作成
        
        Args:
            messages: 要約する対話メッセージリスト
            existing_summary: 既存の要約（あれば）
            
        Returns:
            要約テキスト
        """
        try:
            # 要約用プロンプトを構築
            summary_prompt = self._build_summary_prompt(messages, existing_summary)
            
            # 要約用LLMで要約実行
            summary = llm_manager.chat(
                message="以下の対話を要約してください：",
                system_prompt=summary_prompt,
                client_type="summary"
            )
            
            return summary.strip()
            
        except LLMClientError as e:
            # 要約に失敗した場合のフォールバック
            return self._create_fallback_summary(messages, existing_summary)
    
    def _build_summary_prompt(
        self, 
        messages: List[ConversationMessage],
        existing_summary: Optional[str] = None
    ) -> str:
        """要約用システムプロンプトを構築
        
        Args:
            messages: 対話メッセージリスト
            existing_summary: 既存の要約
            
        Returns:
            要約用システムプロンプト
        """
        base_prompt = """あなたは対話履歴の要約専門AIです。以下の指示に従って対話を要約してください：

**要約の目標:**
- 重要な指示、決定事項、進行中のタスクを保持
- ユーザーの目標や意図を明確に記録
- AI の応答や提案内容を簡潔にまとめる
- 文脈の継続性を保つ

**要約の形式:**
1. **セッション目標**: ユーザーが達成しようとしていること
2. **重要な決定**: 行われた重要な判断や設定
3. **進行状況**: 完了したタスクと未完了のタスク
4. **重要な情報**: 覚えておくべき技術的詳細や制約

**要約の制約:**
- 目標トークン数: {target_tokens}トークン以内
- 具体的な固有名詞（ファイル名、変数名など）は保持
- 感情的な表現は除去し、事実のみを記録"""

        # 既存の要約がある場合は統合指示を追加
        if existing_summary:
            base_prompt += f"""

**既存の要約:**
{existing_summary}

**指示**: 既存の要約と新しい対話を統合し、重複を排除して更新された要約を作成してください。"""

        # 対話履歴を追加
        conversation_text = self._format_messages_for_summary(messages)
        base_prompt += f"""

**要約対象の対話:**
{conversation_text}"""

        return base_prompt.format(
            target_tokens=self.memory_config.medium_term.get("summary_target_tokens", 500)
        )
    
    def _format_messages_for_summary(self, messages: List[ConversationMessage]) -> str:
        """メッセージを要約用に整形
        
        Args:
            messages: 対話メッセージリスト
            
        Returns:
            整形されたテキスト
        """
        formatted_parts = []
        
        for message in messages:
            timestamp = message.timestamp.strftime("%H:%M")
            role_label = {
                "user": "ユーザー",
                "assistant": "AI", 
                "system": "システム"
            }.get(message.role, message.role)
            
            content = message.content[:1000]  # 長すぎる場合は切り詰め
            formatted_parts.append(f"[{timestamp}] {role_label}: {content}")
        
        return "\n".join(formatted_parts)
    
    def _create_fallback_summary(
        self, 
        messages: List[ConversationMessage],
        existing_summary: Optional[str] = None
    ) -> str:
        """LLM要約に失敗した場合のフォールバック要約
        
        Args:
            messages: 対話メッセージリスト
            existing_summary: 既存の要約
            
        Returns:
            簡易要約テキスト
        """
        # 基本統計
        user_messages = [m for m in messages if m.role == "user"]
        ai_messages = [m for m in messages if m.role == "assistant"]
        
        # 最初と最後のメッセージから簡易要約を生成
        start_time = messages[0].timestamp.strftime("%H:%M")
        end_time = messages[-1].timestamp.strftime("%H:%M")
        
        fallback_summary = f"""**簡易要約 ({start_time}-{end_time})**
- 対話ターン数: {len(user_messages)}回
- 最初の要求: {user_messages[0].content[:100] if user_messages else "不明"}...
- 最後の応答: {ai_messages[-1].content[:100] if ai_messages else "不明"}..."""

        if existing_summary:
            fallback_summary = f"{existing_summary}\n\n{fallback_summary}"
        
        return fallback_summary
    
    def trim_conversation_history(
        self, 
        messages: List[ConversationMessage],
        summary: str
    ) -> Tuple[str, List[ConversationMessage]]:
        """対話履歴をトリム（要約 + 最新数ターンのみ保持）
        
        Args:
            messages: 全対話メッセージリスト
            summary: 作成された要約
            
        Returns:
            (更新された要約, 保持する最新メッセージリスト)
        """
        keep_turns = self.memory_config.medium_term.get("keep_recent_turns", 3)
        
        # 最新の指定ターン数のメッセージペアを保持
        if len(messages) <= keep_turns * 2:  # user + assistant のペア
            return summary, messages
        
        # ユーザー・AI のメッセージペアを特定
        recent_messages = []
        user_ai_pairs = []
        
        # 最新から遡ってペアを収集
        i = len(messages) - 1
        while i >= 0 and len(user_ai_pairs) < keep_turns:
            if messages[i].role == "assistant" and i > 0 and messages[i-1].role == "user":
                user_ai_pairs.insert(0, (messages[i-1], messages[i]))
                i -= 2
            else:
                i -= 1
        
        # ペアを展開してメッセージリストに変換
        for user_msg, ai_msg in user_ai_pairs:
            recent_messages.extend([user_msg, ai_msg])
        
        return summary, recent_messages
    
    def get_memory_status(
        self, 
        messages: List[ConversationMessage],
        summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """メモリ状態の統計情報を取得
        
        Args:
            messages: 対話メッセージリスト
            summary: 現在の要約
            
        Returns:
            メモリ状態情報
        """
        total_tokens = self.calculate_conversation_tokens(messages)
        summary_tokens = self.count_tokens(summary) if summary else 0
        
        return {
            "total_messages": len(messages),
            "total_tokens": total_tokens,
            "summary_tokens": summary_tokens,
            "needs_summary": self.should_summarize(messages),
            "trigger_threshold": self.memory_config.medium_term.get("summary_trigger_tokens", 4000),
            "target_summary_tokens": self.memory_config.medium_term.get("summary_target_tokens", 500),
            "keep_recent_turns": self.memory_config.medium_term.get("keep_recent_turns", 3)
        }


# グローバルインスタンス
conversation_memory = ConversationMemory()