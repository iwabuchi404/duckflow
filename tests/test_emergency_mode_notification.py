"""
緊急メモリ整理（emergency_mode）発生時に、LLMへその旨が会話履歴で
通知されることを検証するテスト。

背景: MemoryManager.prune_history は emergency_mode（トークン予算を
100%超過し、要約を挟まず強制的に履歴を削減した）かどうかを stats に
含めて返すが、従来は呼び出し側 2 箇所
（companion/core.py の自律ループ内 pruning、
  companion/state/agent_state.py の add_message_with_pruning）
がこの情報を握りつぶしており、LLMは文脈が突然失われたことに
気づけなかった。
"""

import pytest
from companion.modules.memory import MemoryManager, ScoringConfig
from companion.state.agent_state import AgentState


class _StubArchiveStorage:
    """ディスク書き込みを行わない ArchiveStorage スタブ。"""

    def archive_messages(self, messages):
        """アーカイブを行わないノーオペレーション実装。"""
        pass


def _make_manager(max_tokens: int = 100) -> MemoryManager:
    """
    緊急モードに入りやすい小さな max_tokens で MemoryManager を構築する。

    Args:
        max_tokens: 会話履歴のトークン上限

    Returns:
        テスト用の MemoryManager インスタンス
    """
    m = MemoryManager.__new__(MemoryManager)
    m.llm = None
    m.max_tokens = max_tokens
    m.config = ScoringConfig()
    m.prune_count = 0
    m.archive_storage = _StubArchiveStorage()
    return m


def _build_emergency_history() -> list:
    """
    emergency_mode を確実に発火させるための会話履歴を構築する。

    Returns:
        本物のユーザー発言1件 + 大きなジャンクメッセージ9件のリスト
    """
    junk = "X" * 400
    history = [{"role": "user", "content": "実装を開始してください"}]
    for i in range(9):
        history.append({"role": "user", "content": f"junk-{i}: {junk}"})
    return history


class TestAddMessageWithPruningEmergencyNotification:
    """AgentState.add_message_with_pruning の緊急モード通知のテスト"""

    @pytest.mark.asyncio
    async def test_emergency_mode_appends_system_notice(self) -> None:
        """
        emergency_mode が True になった場合、整理後の履歴の末尾に
        '[SYSTEM]' で始まる緊急整理の通知メッセージが追加されることを確認する。

        Args: なし
        Returns: なし
        """
        manager = _make_manager(max_tokens=100)
        state = AgentState()
        state.conversation_history = _build_emergency_history()

        # 事前に emergency_mode に入ることを確認
        original_tokens = manager._estimate_tokens(state.conversation_history)
        assert original_tokens > manager.max_tokens

        await state.add_message_with_pruning("user", "次の指示です", memory_manager=manager)

        last_msg = state.conversation_history[-1]
        assert last_msg["role"] == "user"
        assert "[SYSTEM]" in last_msg["content"]
        assert "緊急" in last_msg["content"]

    @pytest.mark.asyncio
    async def test_no_notice_when_pruning_not_triggered(self) -> None:
        """
        pruning が発生しない通常時は、緊急整理の通知メッセージが
        追加されないことを確認する。

        Args: なし
        Returns: なし
        """
        manager = _make_manager(max_tokens=1_000_000)
        state = AgentState()
        state.conversation_history = [{"role": "user", "content": "短い指示"}]

        await state.add_message_with_pruning("user", "次の指示です", memory_manager=manager)

        for msg in state.conversation_history:
            assert "[SYSTEM]" not in msg["content"]
