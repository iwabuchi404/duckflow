from typing import List, Dict, Optional, Tuple
from pydantic import BaseModel, Field
import logging
from companion.base.llm_client import LLMClient, default_client

logger = logging.getLogger(__name__)


class ScoringConfig(BaseModel):
    """重要度スコアリングの設定"""
    recency_weight: float = 0.3
    role_weight: float = 0.3
    content_weight: float = 0.4
    
    important_keywords: List[str] = [
        "error", "success", "plan", "task", "duck_call",
        "approval", "denied", "completed", "failed", "warning"
    ]
    
    min_content_length: int = 20
    short_content_penalty: float = 0.7


class MemoryManager:
    """
    会話履歴のコンテキスト管理を担当
    
    主な機能:
    - トークン数の監視
    - 重要度に基づくメッセージの選択
    - 低優先度メッセージの削除
    - 削除されたメッセージの要約
    """
    
    def __init__(
        self,
        llm_client: LLMClient = default_client,
        max_tokens: int = 8000,
        config: Optional[ScoringConfig] = None
    ):
        self.llm = llm_client
        self.max_tokens = max_tokens
        self.config = config or ScoringConfig()
        self.prune_count = 0  # 整理実行回数（統計用）
        
    def should_prune(self, conversation_history: List[Dict]) -> bool:
        """整理が必要かチェック"""
        current_tokens = self._estimate_tokens(conversation_history)
        usage_ratio = current_tokens / self.max_tokens
        
        if usage_ratio > 0.8:
            logger.info(
                f"Memory pruning needed: {current_tokens}/{self.max_tokens} "
                f"tokens ({usage_ratio:.1%})"
            )
            return True
        
        return False
    
    async def prune_history(
        self,
        conversation_history: List[Dict]
    ) -> Tuple[List[Dict], Dict]:
        """
        会話履歴を整理
        
        Returns:
            (pruned_history, stats)
        """
        self.prune_count += 1
        
        original_count = len(conversation_history)
        original_tokens = self._estimate_tokens(conversation_history)
        
        # トークン使用率チェック
        if not self.should_prune(conversation_history):
            return conversation_history, {
                "pruned": False,
                "original_count": original_count,
                "original_tokens": original_tokens
            }
        
        # 緊急モード（100%超え）
        emergency_mode = original_tokens > self.max_tokens
        
        # スコアリング
        scored_messages = self._score_messages(conversation_history)
        
        # スコア順にソート
        scored_messages.sort(reverse=True, key=lambda x: x[0])
        
        # トークン予算内で選択
        target_tokens = self.max_tokens * 0.7  # 70%使用を目標
        selected_messages = self._select_within_budget(
            scored_messages, 
            target_tokens
        )
        
        # インデックス順に並び替え
        selected_messages.sort(key=lambda x: x[0])
        
        # ギャップ検出と要約挿入
        if emergency_mode:
            # 緊急モードでは要約をスキップ
            result_history = [msg for _, msg in selected_messages]
        else:
            result_history = await self._insert_summaries(
                conversation_history,
                selected_messages
            )
        
        final_count = len(result_history)
        final_tokens = self._estimate_tokens(result_history)
        
        stats = {
            "pruned": True,
            "original_count": original_count,
            "original_tokens": original_tokens,
            "final_count": final_count,
            "final_tokens": final_tokens,
            "removed_count": original_count - final_count,
            "removed_tokens": original_tokens - final_tokens,
            "emergency_mode": emergency_mode
        }
        
        logger.info(
            f"Memory pruned: {original_count} → {final_count} messages, "
            f"{original_tokens} → {final_tokens} tokens"
        )
        
        return result_history, stats
    
    def _score_messages(
        self,
        conversation_history: List[Dict]
    ) -> List[Tuple[float, int, Dict]]:
        """全メッセージのスコアリング"""
        scored = []
        total = len(conversation_history)
        
        for idx, msg in enumerate(conversation_history):
            score = self._calculate_importance(msg, idx, total)
            scored.append((score, idx, msg))
        
        return scored
    
    def _calculate_importance(
        self,
        message: Dict,
        index: int,
        total: int
    ) -> float:
        """メッセージの重要度を0-1でスコアリング"""
        content = message.get("content", "")
        role = message.get("role", "")
        
        # Recency score
        recency_score = index / max(total - 1, 1)
        
        # Role score
        role_scores = {
            "user": 1.0,
            "assistant": 0.5,
            "system": 0.3
        }
        role_score = role_scores.get(role, 0.5)
        
        # Content score
        content_score = 0.0
        content_lower = content.lower()
        
        # キーワードチェック
        if any(kw in content_lower for kw in self.config.important_keywords):
            content_score += 0.3
        
        # 特殊マーカー
        if "[Tool:" in content:
            content_score += 0.25
        if any(marker in content for marker in ["[SYSTEM:", "[User", "[TASK"]):
            content_score += 0.2
        if "duck_call" in content_lower or "approval" in content_lower:
            content_score += 0.3
        
        # 長さペナルティ
        if len(content) < self.config.min_content_length:
            content_score *= self.config.short_content_penalty
        
        content_score = min(content_score, 1.0)
        
        # 総合スコア
        total_score = (
            recency_score * self.config.recency_weight +
            role_score * self.config.role_weight +
            content_score * self.config.content_weight
        )
        
        return min(total_score, 1.0)
    
    def _select_within_budget(
        self,
        scored_messages: List[Tuple[float, int, Dict]],
        budget: int
    ) -> List[Tuple[int, Dict]]:
        """トークン予算内で高スコアメッセージを選択"""
        selected = []
        remaining_budget = budget
        
        for score, idx, msg in scored_messages:
            msg_tokens = self._estimate_tokens([msg])
            
            if remaining_budget - msg_tokens > 0:
                selected.append((idx, msg))
                remaining_budget -= msg_tokens
            
            if remaining_budget <= 0:
                break
        
        return selected
    
    async def _insert_summaries(
        self,
        original_history: List[Dict],
        selected_messages: List[Tuple[int, Dict]]
    ) -> List[Dict]:
        """ギャップを検出し、要約を挿入"""
        result = []
        last_idx = -1
        
        for idx, msg in selected_messages:
            # ギャップ検出
            if idx - last_idx > 1:
                gap_messages = original_history[last_idx + 1 : idx]
                
                if len(gap_messages) >= 5:
                    # 5件以上のギャップは要約
                    summary = await self._summarize_gap(gap_messages)
                    result.append(summary)
                elif len(gap_messages) > 0:
                    # 少数のギャップは削除通知のみ
                    result.append({
                        "role": "assistant",
                        "content": f"[{len(gap_messages)}件のメッセージが省略されました]"
                    })
            
            result.append(msg)
            last_idx = idx
        
        return result
    
    async def _summarize_gap(self, messages: List[Dict]) -> Dict:
        """メッセージ群を要約"""
        combined = "\n\n".join([
            f"{msg['role']}: {msg['content'][:200]}"
            for msg in messages
        ])
        
        prompt = f"""以下の会話の重要なポイントのみを簡潔に要約してください。
出力は必ず以下のJSON形式にしてください：
{{
    "summary": "要約テキスト（2-3文、100文字以内）"
}}

会話内容:
{combined}"""
        
        try:
            response = await self.llm.chat(
                [{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.3
            )
            
            summary_text = response.get("summary", "（要約失敗）")
            
            return {
                "role": "assistant",
                "content": f"[過去{len(messages)}件の会話の要約: {summary_text}]"
            }
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return {
                "role": "assistant",
                "content": f"[過去{len(messages)}件のメッセージが削除されました]"
            }
    
    def _estimate_tokens(self, messages: List[Dict]) -> int:
        """トークン数を概算"""
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        # 1文字 ≈ 0.5トークン（日本語・英語混在を考慮）
        return int(total_chars * 0.5)
