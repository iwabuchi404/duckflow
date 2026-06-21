"""
/tokens コマンド と MemoryManager 公開メソッドの回帰テスト (S3-5)。

estimate_history_tokens の概算式、max_tokens に対する使用率、
推定 context_length の逆算を検証する。
"""

import pytest

from companion.core import DuckAgent
from companion.modules.command_handler import CommandHandler
from companion.modules.memory import MemoryManager


@pytest.fixture
def handler() -> CommandHandler:
    agent = DuckAgent()
    agent.state.conversation_history = [
        {"role": "user", "content": "a" * 100},
        {"role": "assistant", "content": "b" * 60},
    ]
    # 予算を既知の値に固定（テスト安定化）
    agent.memory_manager.max_tokens = 10_000
    return agent.command_handler


def test_estimate_history_tokens_matches_chars_times_half():
    """1文字 ≈ 0.5 トークンの概算式が適用される。"""
    mm = MemoryManager(max_tokens=1000)
    msgs = [{"role": "user", "content": "x" * 200}]
    # 200 文字 → 100 トークン
    assert mm.estimate_history_tokens(msgs) == 100


def test_estimate_history_tokens_sums_all_messages():
    """複数メッセージの文字数が合算される。"""
    mm = MemoryManager(max_tokens=1000)
    msgs = [
        {"role": "user", "content": "a" * 100},
        {"role": "assistant", "content": "b" * 100},
    ]
    assert mm.estimate_history_tokens(msgs) == 100  # 200 文字 * 0.5


def test_estimate_history_tokens_empty():
    """空リストは 0。"""
    mm = MemoryManager(max_tokens=1000)
    assert mm.estimate_history_tokens([]) == 0


def test_estimate_history_tokens_ignores_non_content_keys():
    """cache_control 等の補助キーは文字数に影響しない。"""
    mm = MemoryManager(max_tokens=1000)
    msgs = [
        {"role": "system", "content": "abcd", "cache_control": {"type": "ephemeral"}}
    ]
    assert mm.estimate_history_tokens(msgs) == 2  # 4 文字 * 0.5


@pytest.mark.asyncio
async def test_handle_tokens_runs_without_error(handler: CommandHandler, capsys):
    """/tokens が例外なく実行完了する。"""
    await handler.handle_tokens([])
    err = capsys.readouterr().err
    assert "Error" not in err


def test_usage_ratio_calculation(handler: CommandHandler):
    """履歴トークン数 / max_tokens の使用率が正しく計算できる。"""
    mm = handler.agent.memory_manager
    history = handler.agent.state.conversation_history
    hist_tokens = mm.estimate_history_tokens(history)
    # 履歴: 100 + 60 = 160 文字 → 80 トークン
    assert hist_tokens == 80
    ratio = hist_tokens / mm.max_tokens
    assert ratio == pytest.approx(80 / 10_000)


def test_context_length_reverse_engineering(handler: CommandHandler):
    """max_tokens から context_length の逆算式が MEMORY_RATIO / RESERVE と整合する。

    int() 切り捨てによる ±1 の誤差を許容する（display用途の概算逆算のため）。
    """
    mm = handler.agent.memory_manager
    max_tokens = mm.max_tokens
    # max_tokens = (ctx - 4000) * 0.6  →  ctx = max_tokens / 0.6 + 4000
    approx_ctx = int(max_tokens / 0.6 + 4000)
    recomputed = int((approx_ctx - MemoryManager.SYSTEM_PROMPT_RESERVE) * MemoryManager.HISTORY_RATIO)
    assert recomputed == pytest.approx(max_tokens, abs=1)
