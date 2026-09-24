#!/usr/bin/env python3
"""
会話記憶管理 - 会話履歴の管理と要約

codecrafterから分離し、companion内で完結するように調整
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class ConversationEntry:
    """会話エントリ"""

    id: str
    timestamp: datetime
    speaker: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "speaker": self.speaker,
            "message": self.message,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationEntry":
        """辞書から作成"""
        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            speaker=data["speaker"],
            message=data["message"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class ConversationSummary:
    """会話サマリー"""

    total_messages: int
    user_messages: int
    assistant_messages: int
    session_duration: timedelta
    key_topics: list[str]
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """辞書形式に変換"""
        return {
            "total_messages": self.total_messages,
            "user_messages": self.user_messages,
            "assistant_messages": self.assistant_messages,
            "session_duration": str(self.session_duration),
            "key_topics": self.key_topics,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class ConversationMemory:
    """会話記憶管理クラス"""

    def __init__(self, max_entries: int = 1000, auto_summarize: bool = True):
        self.max_entries = max_entries
        self.auto_summarize = auto_summarize

        # 会話履歴
        self.conversations: list[ConversationEntry] = []

        # サマリー
        self.summary: ConversationSummary | None = None

        # ログ設定
        self.logger = logging.getLogger(__name__)

        self.logger.info("ConversationMemory初期化完了")

    def add_message(
        self, speaker: str, message: str, metadata: dict[str, Any] | None = None
    ) -> str:
        """メッセージを追加"""
        try:
            entry_id = f"msg_{len(self.conversations)}_{datetime.now().timestamp()}"

            entry = ConversationEntry(
                id=entry_id,
                timestamp=datetime.now(),
                speaker=speaker,
                message=message,
                metadata=metadata or {},
            )

            self.conversations.append(entry)

            # 最大エントリ数を超えた場合、古いものを削除
            if len(self.conversations) > self.max_entries:
                self.conversations = self.conversations[-self.max_entries :]
                self.logger.debug(f"会話履歴を{self.max_entries}件に制限")

            # 自動サマリー更新
            if self.auto_summarize:
                self._update_summary()

            self.logger.debug(f"メッセージ追加: {speaker} - {message[:50]}...")
            return entry_id

        except Exception as e:
            self.logger.error(f"メッセージ追加エラー: {e}")
            return ""

    def get_conversation_history(
        self, limit: int | None = None
    ) -> list[ConversationEntry]:
        """会話履歴を取得"""
        if limit is None:
            return self.conversations.copy()
        else:
            return self.conversations[-limit:]

    def get_messages_by_speaker(
        self, speaker: str, limit: int | None = None
    ) -> list[ConversationEntry]:
        """特定の話者のメッセージを取得"""
        messages = [entry for entry in self.conversations if entry.speaker == speaker]

        if limit:
            messages = messages[-limit:]

        return messages

    def search_messages(
        self, query: str, limit: int | None = None
    ) -> list[ConversationEntry]:
        """メッセージを検索"""
        results = []

        for entry in self.conversations:
            if query.lower() in entry.message.lower():
                results.append(entry)

                if limit and len(results) >= limit:
                    break

        return results

    def get_recent_context(self, minutes: int = 30) -> list[ConversationEntry]:
        """最近のコンテキストを取得"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)

        recent_entries: list[ConversationEntry] = []
        for entry in reversed(self.conversations):
            if entry.timestamp >= cutoff_time:
                recent_entries.insert(0, entry)
            else:
                break

        return recent_entries

    def _update_summary(self) -> None:
        """会話履歴からサマリーを更新する。"""
        try:
            if not self.conversations:
                return

            # 基本統計
            total_messages = len(self.conversations)
            user_messages = len([e for e in self.conversations if e.speaker == "user"])
            assistant_messages = len(
                [e for e in self.conversations if e.speaker == "assistant"]
            )

            # セッション時間
            if len(self.conversations) >= 2:
                session_duration = (
                    self.conversations[-1].timestamp - self.conversations[0].timestamp
                )
            else:
                session_duration = timedelta(0)

            # キートピック（簡易版）
            key_topics = self._extract_key_topics()

            # サマリー作成
            self.summary = ConversationSummary(
                total_messages=total_messages,
                user_messages=user_messages,
                assistant_messages=assistant_messages,
                session_duration=session_duration,
                key_topics=key_topics,
                created_at=(
                    self.conversations[0].timestamp
                    if self.conversations
                    else datetime.now()
                ),
                updated_at=datetime.now(),
            )

        except Exception as e:
            self.logger.error(f"サマリー更新エラー: {e}")

    def _extract_key_topics(self) -> list[str]:
        """キートピックを抽出（簡易版）"""
        try:
            # ユーザーメッセージからキーワードを抽出
            user_messages = [
                e.message for e in self.conversations if e.speaker == "user"
            ]

            if not user_messages:
                return []

            # 簡単なキーワード抽出（実際の実装ではより高度なNLPを使用）
            keywords: list[str] = []
            for message in user_messages[-10:]:  # 最近10件
                words = message.lower().split()
                # 特定のキーワードを抽出
                for word in words:
                    if len(word) > 3 and word not in keywords[:5]:  # 最大5件
                        keywords.append(word)

            return keywords[:5]

        except Exception as e:
            self.logger.error(f"キートピック抽出エラー: {e}")
            return []

    def get_summary(self) -> ConversationSummary | None:
        """サマリーを取得"""
        if not self.summary:
            self._update_summary()
        return self.summary

    def clear_history(self) -> None:
        """会話履歴とサマリーをクリアする。"""
        self.conversations.clear()
        self.summary = None
        self.logger.info("会話履歴をクリアしました")

    def export_history(self, format: str = "json") -> str:
        """履歴をエクスポート"""
        try:
            if format.lower() == "json":
                data = {
                    "conversations": [entry.to_dict() for entry in self.conversations],
                    "summary": self.summary.to_dict() if self.summary else None,
                }
                return json.dumps(data, indent=2, ensure_ascii=False)
            else:
                # テキスト形式
                lines = []
                for entry in self.conversations:
                    timestamp = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    lines.append(f"[{timestamp}] {entry.speaker}: {entry.message}")

                return "\n".join(lines)

        except Exception as e:
            self.logger.error(f"履歴エクスポートエラー: {e}")
            return ""

    def import_history(self, data: str, format: str = "json") -> bool:
        """履歴をインポート"""
        try:
            if format.lower() == "json":
                json_data = json.loads(data)

                # 既存履歴をクリア
                self.conversations.clear()

                # 新しい履歴を追加
                for entry_data in json_data.get("conversations", []):
                    entry = ConversationEntry.from_dict(entry_data)
                    self.conversations.append(entry)

                # サマリーを更新
                self._update_summary()

                self.logger.info(
                    f"履歴をインポートしました: {len(self.conversations)}件"
                )
                return True

            else:
                # テキスト形式のインポート（簡易版）
                lines = data.strip().split("\n")

                for line in lines:
                    if ":" in line:
                        try:
                            # [timestamp] speaker: message 形式を解析
                            parts = line.split(":", 1)
                            if len(parts) == 2:
                                timestamp_part = parts[0].strip()
                                speaker_message = parts[1].strip()

                                # タイムスタンプを解析
                                timestamp_str = timestamp_part[
                                    1:-1
                                ]  # [timestamp] から [] を除去
                                datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

                                # 話者とメッセージを分離
                                if " " in speaker_message:
                                    speaker, message = speaker_message.split(" ", 1)
                                else:
                                    speaker = speaker_message
                                    message = ""

                                # エントリを追加
                                self.add_message(speaker, message)

                        except Exception as e:
                            self.logger.warning(f"行の解析に失敗: {line} - {e}")
                            continue

                self.logger.info(
                    f"テキスト履歴をインポートしました: {len(self.conversations)}件"
                )
                return True

        except Exception as e:
            self.logger.error(f"履歴インポートエラー: {e}")
            return False

    def get_statistics(self) -> dict[str, Any]:
        """統計情報を取得"""
        try:
            total_messages = len(self.conversations)

            if total_messages == 0:
                return {
                    "total_messages": 0,
                    "user_messages": 0,
                    "assistant_messages": 0,
                    "session_duration": "0:00:00",
                    "average_message_length": 0,
                    "key_topics": [],
                }

            # 基本統計
            user_messages = len([e for e in self.conversations if e.speaker == "user"])
            assistant_messages = len(
                [e for e in self.conversations if e.speaker == "assistant"]
            )

            # セッション時間
            if total_messages >= 2:
                session_duration = (
                    self.conversations[-1].timestamp - self.conversations[0].timestamp
                )
                session_duration_str = str(session_duration).split(".")[
                    0
                ]  # マイクロ秒を除去
            else:
                session_duration_str = "0:00:00"

            # 平均メッセージ長
            total_length = sum(len(e.message) for e in self.conversations)
            average_length = total_length / total_messages

            # キートピック
            key_topics = self._extract_key_topics()

            return {
                "total_messages": total_messages,
                "user_messages": user_messages,
                "assistant_messages": assistant_messages,
                "session_duration": session_duration_str,
                "average_message_length": round(average_length, 1),
                "key_topics": key_topics,
            }

        except Exception as e:
            self.logger.error(f"統計情報取得エラー: {e}")
            return {}

    def to_dict(self) -> dict[str, Any]:
        """オブジェクトの状態を辞書形式で取得"""
        return {
            "max_entries": self.max_entries,
            "auto_summarize": self.auto_summarize,
            "conversations_count": len(self.conversations),
            "summary": self.summary.to_dict() if self.summary else None,
            "statistics": self.get_statistics(),
        }


# グローバルインスタンス
conversation_memory = ConversationMemory()


# 便利な関数
def add_message(
    speaker: str, message: str, metadata: dict[str, Any] | None = None
) -> str:
    """メッセージを追加"""
    return conversation_memory.add_message(speaker, message, metadata)


def get_conversation_history(limit: int | None = None) -> list[ConversationEntry]:
    """会話履歴を取得"""
    return conversation_memory.get_conversation_history(limit)


def get_recent_context(minutes: int = 30) -> list[ConversationEntry]:
    """最近のコンテキストを取得"""
    return conversation_memory.get_recent_context(minutes)


def get_summary() -> ConversationSummary | None:
    """サマリーを取得"""
    return conversation_memory.get_summary()


def clear_history() -> None:
    """会話履歴をクリアする。"""
    conversation_memory.clear_history()


def export_history(format: str = "json") -> str:
    """履歴をエクスポート"""
    return conversation_memory.export_history(format)


def import_history(data: str, format: str = "json") -> bool:
    """履歴をインポート"""
    return conversation_memory.import_history(data, format)
