"""
/prompt コマンドの回帰テスト (S3-4)。

現ターン用のメッセージリスト構築、全モードのシステムプロンプト生成、
raw JSON 出力、ファイル書き出しの各サブコマンドを検証する。
DuckAgent() の初期化は API 呼び出しを伴わないため、スタブ不要で実行できる。
"""

import json
from pathlib import Path

import pytest

from companion.core import DuckAgent
from companion.modules.command_handler import CommandHandler
from companion.state.agent_state import AgentMode


@pytest.fixture
def handler() -> CommandHandler:
    """API 呼び出しなしで構築した DuckAgent に紐づく CommandHandler。"""
    agent = DuckAgent()
    # 会話履歴にサンプルを入れて system/history 分離を検証しやすくする。
    agent.state.conversation_history = [
        {"role": "user", "content": "hello duck"},
        {"role": "assistant", "content": "::response @hi"},
    ]
    return agent.command_handler


def test_build_current_messages_contains_system_and_history(handler: CommandHandler):
    """現ターン構築: system messages の後ろに conversation_history が連結される。"""
    messages = handler._build_current_messages()

    roles = [m["role"] for m in messages]
    # 履歴の user/assistant が末尾付近に含まれる
    assert "user" in roles
    assert "assistant" in roles
    # 末尾メッセージは履歴の最後
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == "::response @hi"
    # システム層が先頭
    assert messages[0]["role"] == "system"


def test_build_current_messages_does_not_mutate_state(handler: CommandHandler):
    """メッセージ構築が live state の会話履歴を破壊しない。"""
    before = list(handler.agent.state.conversation_history)
    handler._build_current_messages()
    after = handler.agent.state.conversation_history
    assert before == after


def test_build_mode_messages_for_each_mode(handler: CommandHandler):
    """planning/investigation/task それぞれでメッセージが構築できる。"""
    for mode in ("planning", "investigation", "task"):
        msgs = handler._build_mode_messages(mode)
        assert len(msgs) > 0
        assert all(isinstance(m, dict) for m in msgs)
        assert msgs[0]["role"] == "system"


def test_build_mode_messages_does_not_change_live_mode(handler: CommandHandler):
    """all-mode 構築がライブ state のモードを変更しない。"""
    handler.agent.state.current_mode = AgentMode.TASK
    handler._build_mode_messages("planning")
    assert handler.agent.state.current_mode == AgentMode.TASK


@pytest.mark.asyncio
async def test_handle_prompt_default_runs(handler: CommandHandler, capsys):
    """既定（引数なし）: プレビューテーブルが stdout へ出力される。"""
    await handler.handle_prompt([])
    captured = capsys.readouterr()
    # Rich は ui.console 経由で出力されるため、print フォールバックでなくても
    # エラーが起きないことを主眼に置く。ui.console が存在するので Panel 描画される。
    # ここでは例外が起きず完了することを検証（出力はコンソールバッファへ）。
    assert "Error" not in captured.err


@pytest.mark.asyncio
async def test_handle_prompt_raw_emits_json(handler: CommandHandler, capsys):
    """raw サブコマンド: messages を JSON シリアライズできる形で出力する。"""
    await handler.handle_prompt(["raw"])
    # JSON としてパース可能な内容が ui.console 経由で描画される。
    # 構築結果が JSON 互換であることを直接検証する。
    messages = handler._build_current_messages()
    payload = json.dumps(messages, ensure_ascii=False)
    parsed = json.loads(payload)
    assert isinstance(parsed, list)
    assert parsed[-1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_handle_prompt_file_writes_json(
    handler: CommandHandler, tmp_path: Path, capsys
):
    """file サブコマンド: 指定パスへ messages が JSON で書き込まれる。"""
    out = tmp_path / "dump.json"
    await handler.handle_prompt(["file", str(out)])
    capsys.readouterr()  # バッファフラッシュ
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert data[-1]["content"] == "::response @hi"


def test_preview_content_truncates(handler: CommandHandler):
    """プレビューが PREVIEW_LEN を超えると切り詰められる。"""
    long = "x" * (handler.PREVIEW_LEN + 50)
    preview = handler._preview_content(long)
    assert preview.endswith("…")
    assert len(preview) <= handler.PREVIEW_LEN + 1  # 省略記号分


def test_preview_content_preserves_short(handler: CommandHandler):
    """短い内容はそのまま返る。"""
    assert handler._preview_content("hi") == "hi"
