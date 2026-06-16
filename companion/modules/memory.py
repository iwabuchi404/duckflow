from typing import List, Dict, Optional, Tuple
from pydantic import BaseModel, Field
import logging
from companion.base.llm_client import get_default_client, LLMClient
from companion.modules.archive import ArchiveStorage

logger = logging.getLogger(__name__)


class ScoringConfig(BaseModel):
    """重要度スコアリングの設定"""
    recency_weight: float = 0.3
    kind_weight: float = 0.4
    content_weight: float = 0.3

    # タスクの文脈（目標・計画・合意）を示すキーワードを優先保持する。
    # 注意: "error" / "failed" 等のエラー系キーワードを入れてはならない。
    # 過去のエラーメッセージが「重要」として生き残り、本来のタスク指示が
    # 先に削られて文脈が崩壊する逆転現象が実際に起きていた。
    important_keywords: List[str] = [
        "plan", "task", "goal", "objective", "duck_call", "approval",
        "計画", "タスク", "目標", "要件", "仕様",
    ]

    min_content_length: int = 20
    short_content_penalty: float = 0.7


class SummaryResponse(BaseModel):
    """LLM-generated summary response."""

    summary: str = Field(..., description="Condensed summary text")


class MemoryManager:
    """
    会話履歴のコンテキスト管理を担当
    
    主な機能:
    - トークン数の監視
    - 重要度に基づくメッセージの選択
    - 低優先度メッセージの削除
    - 削除されたメッセージの要約
    """
    
    # システムプロンプト + Few-shot のトークン概算（動的計算のマージン）
    SYSTEM_PROMPT_RESERVE = 4000
    # コンテキスト長のうち会話履歴に割り当てる割合
    HISTORY_RATIO = 0.6

    def __init__(
        self,
        llm_client: LLMClient = get_default_client(),
        max_tokens: int = 8000,
        config: Optional[ScoringConfig] = None
    ):
        self.llm = llm_client
        self.max_tokens = max_tokens
        self.config = config or ScoringConfig()
        self.prune_count = 0  # 整理実行回数（統計用）
        self.archive_storage = ArchiveStorage()

    def configure_from_context_length(self, context_length: int) -> int:
        """
        モデルのコンテキスト長から max_tokens を動的に計算・設定する。

        計算式:
            max_tokens = (context_length - SYSTEM_PROMPT_RESERVE) * HISTORY_RATIO

        下限 8,000 / 上限 200,000 でクランプ。

        Args:
            context_length: モデルのコンテキスト長（トークン数）

        Returns:
            設定された max_tokens 値
        """
        raw = int((context_length - self.SYSTEM_PROMPT_RESERVE) * self.HISTORY_RATIO)
        self.max_tokens = max(8_000, min(raw, 200_000))
        logger.info(
            f"MemoryManager max_tokens configured: {self.max_tokens:,} "
            f"(from context_length={context_length:,})"
        )
        return self.max_tokens
        
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

        # 最初の「本物のユーザー発言」（セッションの元タスク指示）は
        # 予算やスコアに関わらず必ず保持する
        first_user_idx = next(
            (i for i, msg in enumerate(conversation_history)
             if self._is_genuine_user_message(msg)),
            None,
        )
        if first_user_idx is not None and all(idx != first_user_idx for idx, _ in selected_messages):
            selected_messages.append((first_user_idx, conversation_history[first_user_idx]))

        # インデックス順に並び替え
        selected_messages.sort(key=lambda x: x[0])
        
        # 削除されたメッセージを特定してアーカイブ
        selected_indices = {idx for idx, _ in selected_messages}
        removed_messages = []
        for i in range(len(conversation_history)):
            if i not in selected_indices:
                removed_messages.append(conversation_history[i])
        
        if removed_messages:
            logger.info(f"Archiving {len(removed_messages)} removed messages")
            self.archive_storage.archive_messages(removed_messages)
        
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
    
    @staticmethod
    def _is_genuine_user_message(message: Dict) -> bool:
        """
        メッセージが「本物のユーザー発言」かどうかを判定する。

        会話履歴の role="user" にはツール結果（[TOOL_RESULT] エンベロープ）や
        システム通知（[System...] 等のブラケット行）が混在しているため、
        role だけでは判定できない。

        Args:
            message: 会話履歴のメッセージ辞書（role / content キーを持つ）

        Returns:
            ユーザーが実際に入力したメッセージなら True
        """
        from companion.tools.results import is_tool_result_message

        if message.get("role") != "user":
            return False
        content = message.get("content", "")
        if is_tool_result_message(content):
            return False
        if content.startswith(("[System", "[SYSTEM", "[Error]", "[User denied")):
            return False
        return True

    def _calculate_importance(
        self,
        message: Dict,
        index: int,
        total: int
    ) -> float:
        """
        メッセージの重要度を0-1でスコアリングする。

        設計方針: 「ユーザーの指示・エージェントの応答（＝会話の本体）」を守り、
        「ツール結果・過去のエラー（＝再取得可能なデータ）」から先に削る。

        Args:
            message: 会話履歴のメッセージ辞書
            index: 履歴内のインデックス（古いほど小さい）
            total: 履歴の総メッセージ数

        Returns:
            0.0〜1.0 の重要度スコア
        """
        from companion.tools.results import is_tool_result_message

        content = message.get("content", "")
        role = message.get("role", "")

        # Recency score
        recency_score = index / max(total - 1, 1)

        # Kind score: メッセージの種別（誰が発したか・再取得可能か）
        if self._is_genuine_user_message(message):
            # 本物のユーザー発言 = タスクの源泉。最優先で保持する
            kind_score = 1.0
        elif role == "assistant":
            # エージェントの応答 = 会話の流れの保持に必要
            kind_score = 0.6
        elif is_tool_result_message(content):
            # ツール結果 = 必要なら再実行で取り直せるデータ。優先的に削る
            kind_score = 0.15
            if "::status error" in content:
                # 過去のエラー出力はノイズ。最優先で削る
                kind_score = 0.05
        else:
            # システム通知などその他
            kind_score = 0.3

        # Content score
        content_score = 0.0
        content_lower = content.lower()

        # タスク文脈キーワードチェック
        if any(kw in content_lower for kw in self.config.important_keywords):
            content_score += 0.5

        # 長さペナルティ
        if len(content) < self.config.min_content_length:
            content_score *= self.config.short_content_penalty

        content_score = min(content_score, 1.0)

        # 総合スコア
        total_score = (
            recency_score * self.config.recency_weight +
            kind_score * self.config.kind_weight +
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
                response_model=SummaryResponse,
                max_tokens=150,
                temperature=0.3
            )
            
            summary_text = response.summary
            
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
    
    async def restore_with_summary(
        self,
        conversation_history: List[Dict]
    ) -> List[Dict]:
        """
        セッション復元時に大きな履歴を「LLM要約 + 最近N件」に圧縮する。
        起動時に1回だけ呼ぶこと。

        圧縮アルゴリズム:
            1. トークン上限の70%以内に収まる最近のメッセージを保持
            2. それより古い部分をLLMで一括要約してsystemメッセージとして先頭に挿入

        Args:
            conversation_history: セッションファイルから読み込んだ全履歴

        Returns:
            [セッション要約メッセージ（省略なし）] + [最近N件] の圧縮済み履歴。
            サイズがしきい値以下の場合はそのまま返す。
        """
        if not self.should_prune(conversation_history):
            return conversation_history  # サイズが小さければそのまま使用

        # 最近N件をトークン上限70%で切り出す（新しい方から逆順に積む）
        target_tokens = int(self.max_tokens * 0.7)
        recent_messages: List[Dict] = []
        total = 0
        for msg in reversed(conversation_history):
            t = self._estimate_tokens([msg])
            if total + t > target_tokens:
                break
            recent_messages.insert(0, msg)
            total += t

        # 保持できる分だけ残った場合はそのまま返す
        if len(recent_messages) >= len(conversation_history):
            return conversation_history

        # 古い部分をLLMで要約
        old_messages = conversation_history[: len(conversation_history) - len(recent_messages)]
        logger.info(
            f"Session restore: summarizing {len(old_messages)} old messages, "
            f"keeping {len(recent_messages)} recent messages"
        )
        summary_msg = await self._summarize_session(old_messages)
        return [summary_msg] + recent_messages

    async def _summarize_session(self, messages: List[Dict]) -> Dict:
        """
        セッション全体（古い部分）を箇条書きで要約したsystemメッセージを生成する。

        Args:
            messages: 要約対象のメッセージ群（古い履歴）

        Returns:
            role="system" の要約メッセージ辞書
        """
        # 各メッセージを200文字以内に切り詰めてトークン消費を抑える
        combined = "\n\n".join([
            f"{msg['role']}: {msg['content'][:200]}"
            for msg in messages
        ])

        prompt = f"""以下は前回の作業セッションの会話ログです。
次回のセッションで引き継ぐべき重要な情報を箇条書きで要約してください。
出力は必ず以下のJSON形式にしてください：
{{
    "summary": "箇条書きの要約（各行を「- 」で始める、合計200文字以内）"
}}

会話ログ（{len(messages)}件）:
{combined}"""

        try:
            response = await self.llm.chat(
                [{"role": "user", "content": prompt}],
                response_model=SummaryResponse,
                max_tokens=300,
                temperature=0.3
            )
            summary_text = response.summary
            return {
                "role": "system",
                "content": (
                    f"[前回セッション要約（{len(messages)}件のメッセージを圧縮）]\n"
                    f"{summary_text}"
                )
            }
        except Exception as e:
            logger.error(f"Session summarization failed: {e}")
            return {
                "role": "system",
                "content": f"[前回セッションの{len(messages)}件のメッセージが省略されました]"
            }

    def _estimate_tokens(self, messages: List[Dict]) -> int:
        """トークン数を概算"""
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        # 1文字 ≈ 0.5トークン（日本語・英語混在を考慮）
        return int(total_chars * 0.5)
