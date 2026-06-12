"""
MemoryManager スコアリング機能のテスト。

検証観点:
1. _is_genuine_user_message: 本物のユーザー発言の判定
2. スコアリング順序: genuine_user > assistant > tool_result > tool_result(エラー)
3. エラーキーワードがスコアをブーストしないこと
4. タスクキーワード（"計画" 等）がスコアをブーストすること
5. prune_history: 最初の本物ユーザー発言が予算超過でも強制保持されること
"""

import pytest
from companion.modules.memory import MemoryManager, ScoringConfig
from companion.tools.results import TOOL_RESULT_OPEN, TOOL_RESULT_CLOSE


# ------------------------------------------------------------------ #
#  テスト用スタブ
# ------------------------------------------------------------------ #

class _StubArchiveStorage:
    """ディスク書き込みを行わない ArchiveStorage スタブ。"""

    def archive_messages(self, messages):
        """
        アーカイブを行わないノーオペレーション実装。

        Args:
            messages: アーカイブ対象のメッセージリスト（無視する）

        Returns:
            None
        """
        pass  # ディスクに書き込まない


def _make_manager(max_tokens: int = 8000) -> MemoryManager:
    """
    テスト用の MemoryManager を構築する。

    LLM クライアントを None に設定し、ArchiveStorage をスタブで置き換える。
    コンストラクタのデフォルト引数 get_default_client() が副作用を持つ場合があるため
    __new__ + 手動初期化で構築する。

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


def _user_msg(content: str) -> dict:
    """
    role="user" の普通のメッセージ辞書を返す。

    Args:
        content: メッセージ内容

    Returns:
        {"role": "user", "content": content} の辞書
    """
    return {"role": "user", "content": content}


def _tool_result_msg(content: str) -> dict:
    """
    [TOOL_RESULT] エンベロープで包んだ role="user" メッセージを返す。

    Args:
        content: ツール結果の本文

    Returns:
        [TOOL_RESULT] ラップ済みの role="user" メッセージ辞書
    """
    wrapped = f"{TOOL_RESULT_OPEN}\n{content}\n{TOOL_RESULT_CLOSE}"
    return {"role": "user", "content": wrapped}


def _assistant_msg(content: str) -> dict:
    """
    role="assistant" のメッセージ辞書を返す。

    Args:
        content: メッセージ内容

    Returns:
        {"role": "assistant", "content": content} の辞書
    """
    return {"role": "assistant", "content": content}


# ------------------------------------------------------------------ #
#  テスト 1: _is_genuine_user_message
# ------------------------------------------------------------------ #

class TestIsGenuineUserMessage:
    """_is_genuine_user_message の判定ロジックのテスト"""

    def test_plain_user_message_returns_true(self) -> None:
        """
        通常の role="user" メッセージは True を返す。

        Args: なし
        Returns: なし
        """
        m = _make_manager()
        msg = _user_msg("新しい機能を実装してください")
        assert m._is_genuine_user_message(msg) is True

    def test_assistant_message_returns_false(self) -> None:
        """
        role="assistant" のメッセージは False を返す。

        Args: なし
        Returns: なし
        """
        m = _make_manager()
        msg = _assistant_msg("了解しました。実装を開始します。")
        assert m._is_genuine_user_message(msg) is False

    def test_tool_result_wrapped_user_message_returns_false(self) -> None:
        """
        [TOOL_RESULT] エンベロープで包まれた role="user" メッセージは False を返す。

        ツール実行結果は role="user" で注入されるが、本物のユーザー発言ではない。

        Args: なし
        Returns: なし
        """
        m = _make_manager()
        msg = _tool_result_msg("::status ok\n::read_file @foo.py\n<<<\ncontent\n>>>")
        assert m._is_genuine_user_message(msg) is False

    def test_system_bracket_prefix_returns_false(self) -> None:
        """
        [System ... で始まる role="user" メッセージは False を返す。

        システム通知は本物のユーザー発言ではない。

        Args: なし
        Returns: なし
        """
        m = _make_manager()
        msg = _user_msg("[System: workspace changed to /new/path]")
        assert m._is_genuine_user_message(msg) is False

    def test_system_upper_prefix_returns_false(self) -> None:
        """
        [SYSTEM ... で始まる role="user" メッセージは False を返す。

        Args: なし
        Returns: なし
        """
        m = _make_manager()
        msg = _user_msg("[SYSTEM: init]")
        assert m._is_genuine_user_message(msg) is False

    def test_error_bracket_prefix_returns_false(self) -> None:
        """
        [Error] で始まる role="user" メッセージは False を返す。

        Args: なし
        Returns: なし
        """
        m = _make_manager()
        msg = _user_msg("[Error] something went wrong")
        assert m._is_genuine_user_message(msg) is False

    def test_user_denied_prefix_returns_false(self) -> None:
        """
        [User denied で始まる role="user" メッセージは False を返す。

        Args: なし
        Returns: なし
        """
        m = _make_manager()
        msg = _user_msg("[User denied the action]")
        assert m._is_genuine_user_message(msg) is False


# ------------------------------------------------------------------ #
#  テスト 2: スコアリング順序（同一 recency で比較）
# ------------------------------------------------------------------ #

class TestScoringOrder:
    """
    同一 recency における kind スコアの優先順位テスト。

    設計方針: genuine_user=1.0 > assistant=0.6 > tool_result=0.15 > tool_result_error=0.05
    """

    def _get_score(self, m: MemoryManager, msg: dict, idx: int = 0, total: int = 1) -> float:
        """
        1 件のメッセージのスコアを計算して返す。

        Args:
            m: MemoryManager インスタンス
            msg: スコアリング対象のメッセージ辞書
            idx: 履歴内のインデックス（新旧の相対位置）
            total: 履歴の総メッセージ数

        Returns:
            0.0〜1.0 の重要度スコア
        """
        return m._calculate_importance(msg, idx, total)

    def test_genuine_user_scores_higher_than_assistant(self) -> None:
        """
        genuine user メッセージは assistant メッセージよりスコアが高い。

        Args: なし
        Returns: なし
        """
        m = _make_manager()
        user_score = self._get_score(m, _user_msg("タスクを開始してください"))
        asst_score = self._get_score(m, _assistant_msg("タスクを開始します"))
        assert user_score > asst_score

    def test_assistant_scores_higher_than_tool_result(self) -> None:
        """
        assistant メッセージは tool_result メッセージよりスコアが高い。

        Args: なし
        Returns: なし
        """
        m = _make_manager()
        asst_score = self._get_score(m, _assistant_msg("調査を完了しました"))
        tool_score = self._get_score(m, _tool_result_msg("::status ok\n<<< result >>>"))
        assert asst_score > tool_score

    def test_tool_result_scores_higher_than_tool_result_with_error(self) -> None:
        """
        通常の tool_result は ::status error を含む tool_result よりスコアが高い。

        過去のエラー出力はノイズであり、最優先で削除される。

        Args: なし
        Returns: なし
        """
        m = _make_manager()
        ok_tool_score = self._get_score(m, _tool_result_msg("::status ok\n<<<\ndata\n>>>"))
        err_tool_score = self._get_score(m, _tool_result_msg("::status error\nReason: not found"))
        assert ok_tool_score > err_tool_score


# ------------------------------------------------------------------ #
#  テスト 3: エラーキーワードがブーストしないこと
# ------------------------------------------------------------------ #

class TestErrorKeywordNoBoost:
    """
    "error" キーワードは ScoringConfig.important_keywords に含まれないため、
    スコアをブーストしないことのテスト。
    """

    def test_error_keyword_does_not_boost_score(self) -> None:
        """
        "error" という単語だけを含む assistant メッセージと
        キーワードなしの assistant メッセージのスコアが同等であること。

        v2.3 以前は "error" が important_keywords に含まれていたため
        過去のエラーメッセージが優先保持される逆転現象が起きていた。
        v2.4 では "error" はリストから削除済みであること。

        Args: なし
        Returns: なし
        """
        m = _make_manager()
        # important_keywords に "error" が含まれていないことを事前確認
        assert "error" not in m.config.important_keywords, (
            "important_keywords に 'error' が含まれている（v2.3 以前の設定が混入）"
        )

        with_error = _assistant_msg("error")
        without_keyword = _assistant_msg("some generic message here")

        score_with = m._calculate_importance(with_error, 0, 2)
        score_without = m._calculate_importance(without_keyword, 0, 2)

        # "error" がブーストをかけないため、両者は同等スコアになるはず
        # （content_score = 0.0 for both, same recency/kind）
        assert score_with == score_without, (
            f"'error' がスコアをブーストしている: {score_with} vs {score_without}"
        )


# ------------------------------------------------------------------ #
#  テスト 4: タスクキーワードがスコアをブーストすること
# ------------------------------------------------------------------ #

class TestTaskKeywordBoost:
    """
    important_keywords に含まれるタスク文脈キーワードがスコアをブーストすることのテスト。
    """

    def test_task_keyword_boosts_score(self) -> None:
        """
        "計画" を含む assistant メッセージは、キーワードなしの同種メッセージより
        スコアが高いこと。

        Args: なし
        Returns: なし
        """
        m = _make_manager()
        assert "計画" in m.config.important_keywords, (
            "important_keywords に '計画' が含まれていない"
        )

        with_keyword = _assistant_msg("計画を立案しました。タスクを開始します。")
        without_keyword = _assistant_msg("処理を実行しました。")

        score_with = m._calculate_importance(with_keyword, 0, 2)
        score_without = m._calculate_importance(without_keyword, 0, 2)

        assert score_with > score_without, (
            f"タスクキーワード '計画' がスコアをブーストしていない: "
            f"{score_with} vs {score_without}"
        )

    def test_plan_keyword_boosts_score(self) -> None:
        """
        "plan" を含む genuine user メッセージは、キーワードなしの同種メッセージより
        スコアが高いこと。

        Args: なし
        Returns: なし
        """
        m = _make_manager()
        assert "plan" in m.config.important_keywords

        with_keyword = _user_msg("plan the implementation steps")
        without_keyword = _user_msg("please proceed")

        score_with = m._calculate_importance(with_keyword, 0, 2)
        score_without = m._calculate_importance(without_keyword, 0, 2)

        assert score_with > score_without


# ------------------------------------------------------------------ #
#  テスト 5: prune_history で最初の本物ユーザー発言が強制保持されること
# ------------------------------------------------------------------ #

class TestPruneHistoryPinning:
    """
    prune_history の「最初の本物ユーザー発言を強制保持する」機能のテスト。
    """

    @pytest.mark.asyncio
    async def test_first_genuine_user_message_is_pinned(self) -> None:
        """
        予算が非常に小さく大部分のメッセージが削除される場合でも、
        履歴の最初の本物ユーザー発言（インデックス 0）は結果に保持されること。

        セットアップ:
        - インデックス 0: 短い genuine user メッセージ（"実装を開始してください"）
        - インデックス 1〜9: 大きな [TOOL_RESULT] ラップのジャンクメッセージ

        max_tokens を非常に小さく設定することで emergency_mode に入り、
        LLM 要約をスキップして純粋な選択ロジックのみをテストする。

        Args: なし
        Returns: なし
        """
        # ジャンクコンテンツ（各約 400 文字、ゆるくトークン換算で ~200 トークン）
        junk = "X" * 400

        history = [
            _user_msg("実装を開始してください"),   # インデックス 0: 保持すべき本物のユーザー発言
        ]
        for i in range(9):
            history.append(_tool_result_msg(f"::status ok\n<<<\n{junk}\n>>>"))

        # 全体トークン数を概算: 各メッセージ ~200 トークン × 10 件 = ~2000 トークン
        # max_tokens = 100 に設定 → should_prune が True になり emergency_mode に入る
        m = _make_manager(max_tokens=100)

        # emergency_mode であることを事前確認
        original_tokens = m._estimate_tokens(history)
        assert original_tokens > m.max_tokens, (
            f"emergency_mode に入らない: original_tokens={original_tokens}, max_tokens={m.max_tokens}"
        )

        result_history, stats = await m.prune_history(history)

        assert stats["pruned"] is True
        assert stats["emergency_mode"] is True

        # 結果に最初の genuine user メッセージが含まれること
        contents = [msg["content"] for msg in result_history]
        assert "実装を開始してください" in contents, (
            f"最初の本物ユーザー発言が prune_history 後に失われた。\n"
            f"結果の履歴: {[c[:50] for c in contents]}"
        )
