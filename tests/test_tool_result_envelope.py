"""
ツール結果エンベロープ機能のテスト。

検証観点:
1. wrap_tool_result が [TOOL_RESULT] ～ [/TOOL_RESULT] でラップすること
2. is_tool_result_message が正しく判定すること
3. format_symops_response との round-trip でマーカーと ::status ok が含まれること
4. (統合) DuckAgent.execute_actions がツール結果をエンベロープで履歴に注入すること
"""

import pytest
from companion.tools.results import (
    TOOL_RESULT_OPEN,
    TOOL_RESULT_CLOSE,
    ToolResult,
    ToolStatus,
    format_symops_response,
    wrap_tool_result,
    is_tool_result_message,
)


class TestWrapToolResult:
    """wrap_tool_result のユニットテスト"""

    def test_basic_wrap_structure(self) -> None:
        """
        wrap_tool_result が [TOOL_RESULT]\\n<body>\\n[/TOOL_RESULT] の構造を返すことを確認する。

        Args: なし
        Returns: なし
        """
        body = "hello world"
        result = wrap_tool_result(body)
        assert result == f"{TOOL_RESULT_OPEN}\n{body}\n{TOOL_RESULT_CLOSE}"

    def test_wrap_starts_with_open_marker(self) -> None:
        """
        ラップされた文字列が開始マーカーで始まることを確認する。

        Args: なし
        Returns: なし
        """
        result = wrap_tool_result("some content")
        assert result.startswith(TOOL_RESULT_OPEN)

    def test_wrap_ends_with_close_marker(self) -> None:
        """
        ラップされた文字列が終了マーカーで終わることを確認する。

        Args: なし
        Returns: なし
        """
        result = wrap_tool_result("some content")
        assert result.endswith(TOOL_RESULT_CLOSE)

    def test_wrap_preserves_body(self) -> None:
        """
        元の body がラップ後も保持されることを確認する。

        Args: なし
        Returns: なし
        """
        body = "::status ok\n::read_file @foo.py\n<<<\ncontent\n>>>"
        result = wrap_tool_result(body)
        assert body in result

    def test_wrap_empty_body(self) -> None:
        """
        空の body でもマーカー構造が壊れないことを確認する。

        Args: なし
        Returns: なし
        """
        result = wrap_tool_result("")
        assert result == f"{TOOL_RESULT_OPEN}\n\n{TOOL_RESULT_CLOSE}"

    def test_constants_values(self) -> None:
        """
        定数の値が期待通りであることを確認する。

        Args: なし
        Returns: なし
        """
        assert TOOL_RESULT_OPEN == "[TOOL_RESULT]"
        assert TOOL_RESULT_CLOSE == "[/TOOL_RESULT]"


class TestIsToolResultMessage:
    """is_tool_result_message のユニットテスト"""

    def test_wrapped_content_returns_true(self) -> None:
        """
        wrap_tool_result でラップされたコンテンツは True を返すことを確認する。

        Args: なし
        Returns: なし
        """
        wrapped = wrap_tool_result("some result")
        assert is_tool_result_message(wrapped) is True

    def test_plain_text_returns_false(self) -> None:
        """
        通常のテキストは False を返すことを確認する。

        Args: なし
        Returns: なし
        """
        assert is_tool_result_message("Hello, how can I help?") is False

    def test_marker_mid_string_returns_false(self) -> None:
        """
        マーカーが文字列の途中にある場合（冒頭ではない）は False を返すことを確認する。

        Args: なし
        Returns: なし
        """
        # マーカーが先頭ではなく途中に含まれる場合
        content = f"Some text before {TOOL_RESULT_OPEN}\nresult\n{TOOL_RESULT_CLOSE}"
        assert is_tool_result_message(content) is False

    def test_empty_string_returns_false(self) -> None:
        """
        空文字列は False を返すことを確認する。

        Args: なし
        Returns: なし
        """
        assert is_tool_result_message("") is False

    def test_user_message_with_tool_result_marker_only_if_starts(self) -> None:
        """
        is_tool_result_message は startswith で判定するため、
        ユーザーメッセージが偶然マーカーを含んでも先頭でなければ False になることを確認する。

        Args: なし
        Returns: なし
        """
        assert is_tool_result_message("The [TOOL_RESULT] tag appeared") is False


class TestRoundTrip:
    """format_symops_response + wrap_tool_result の round-trip テスト"""

    def test_round_trip_starts_with_open_marker(self) -> None:
        """
        ToolResult を format_symops_response でフォーマットし wrap_tool_result でラップすると
        開始マーカーで始まることを確認する。

        Args: なし
        Returns: なし
        """
        tool_res = ToolResult.ok(
            tool_name="ping",
            target="localhost",
            content="pong"
        )
        wrapped = wrap_tool_result(format_symops_response(tool_res))
        assert wrapped.startswith(TOOL_RESULT_OPEN)

    def test_round_trip_contains_status_ok(self) -> None:
        """
        成功時の round-trip 結果に '::status ok' が含まれることを確認する。

        Args: なし
        Returns: なし
        """
        tool_res = ToolResult.ok(
            tool_name="read_file",
            target="test.py",
            content="def main(): pass"
        )
        wrapped = wrap_tool_result(format_symops_response(tool_res))
        assert "::status ok" in wrapped

    def test_round_trip_error_contains_status_error(self) -> None:
        """
        エラー時の round-trip 結果に '::status error' が含まれることを確認する。

        Args: なし
        Returns: なし
        """
        tool_res = ToolResult.error(
            tool_name="write_file",
            target="out.txt",
            content=Exception("Permission denied")
        )
        wrapped = wrap_tool_result(format_symops_response(tool_res))
        assert "::status error" in wrapped

    def test_round_trip_is_tool_result_message(self) -> None:
        """
        round-trip の結果は is_tool_result_message で True になることを確認する。

        Args: なし
        Returns: なし
        """
        tool_res = ToolResult.ok(
            tool_name="list_directory",
            target=".",
            content=["file1.py", "file2.py"]
        )
        wrapped = wrap_tool_result(format_symops_response(tool_res))
        assert is_tool_result_message(wrapped) is True

    def test_round_trip_contains_tool_name_and_target(self) -> None:
        """
        round-trip の結果にツール名とターゲットが含まれることを確認する。

        Args: なし
        Returns: なし
        """
        tool_res = ToolResult.ok(
            tool_name="grep_files",
            target="src/",
            content="match found"
        )
        wrapped = wrap_tool_result(format_symops_response(tool_res))
        assert "::grep_files" in wrapped
        assert "src/" in wrapped


class TestDuckAgentExecuteActionsEnvelope:
    """
    DuckAgent.execute_actions がツール結果をエンベロープで履歴に注入することの統合テスト。

    注意: DuckAgent の初期化は Rich UI やモジュールの import 副作用が多いため、
    ヘッドレス環境での実行が可能か慎重に確認する。
    API キーが不在の場合は Mock LLM フォールバックが使用される。
    """

    @pytest.mark.asyncio
    async def test_execute_actions_wraps_result_in_envelope(self) -> None:
        """
        DuckAgent.execute_actions を実行すると、ツール結果が
        [TOOL_RESULT] エンベロープに包まれて role='user' として
        会話履歴に追加されることを確認する。

        Args: なし
        Returns: なし
        """
        # DuckAgent の import は副作用が大きいため try/except で囲む
        try:
            from companion.core import DuckAgent
            from companion.state.agent_state import ActionList, Action
        except Exception as exc:
            pytest.skip(f"DuckAgent import failed (entangled): {exc}")

        # エージェントを初期化（API キーなし → Mock LLM）
        try:
            agent = DuckAgent()
        except Exception as exc:
            pytest.skip(f"DuckAgent instantiation failed: {exc}")

        # trivial ツールを登録（同期関数でも可）
        def ping_tool() -> str:
            """テスト用の ping ツール。'pong' を返す。"""
            return "pong"

        agent.register_tool("ping", ping_tool)

        # ActionList を組み立てる（ping アクション 1 件）
        action_list = ActionList(
            actions=[Action(name="ping", parameters={})],
            reasoning="テスト: ping を実行する"
        )

        # 実行前の履歴長を記録
        history_len_before = len(agent.state.conversation_history)

        # execute_actions を実行
        await agent.execute_actions(action_list)

        # 実行後に履歴が増えていること
        assert len(agent.state.conversation_history) > history_len_before, (
            "execute_actions 後に会話履歴が増えていない"
        )

        # execute_actions は末尾に「推論+アクション概要」を assistant ロールで
        # 追加する（multi_turn_context_fix_plan.md Phase 1）。
        # そのためツール結果メッセージは最後から2番目になる。
        tool_msg = agent.state.conversation_history[-2]
        summary_msg = agent.state.conversation_history[-1]

        # ツール結果メッセージの role が 'user' であること（ツール結果はユーザーロールで注入される）
        assert tool_msg["role"] == "user", (
            f"ツール結果メッセージの role が 'user' ではない: {tool_msg['role']}"
        )

        content = tool_msg["content"]

        # エンベロープで包まれていること
        assert is_tool_result_message(content), (
            f"ツール結果メッセージがエンベロープで包まれていない: {content[:100]}"
        )

        # 'pong' が含まれていること
        assert "pong" in content, (
            f"ツール結果 'pong' が履歴に含まれていない: {content[:200]}"
        )

        # 末尾の行動要約メッセージが assistant ロールであること
        assert summary_msg["role"] == "assistant", (
            f"行動要約メッセージの role が 'assistant' ではない: {summary_msg['role']}"
        )
        assert "ping" in summary_msg["content"], (
            f"行動要約に実行したアクション名 'ping' が含まれていない: {summary_msg['content'][:200]}"
        )
