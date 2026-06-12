"""
PromptBuilder の Correction Guide 機能のテスト。

検証観点:
1. _CORRECTION_EXAMPLES に edit_find_mismatch キーが存在し、
   anchor_mismatch キーが存在しないこと
2. builder.py 内のいかなる _CORRECTION_EXAMPLES 値にも
   "anchor" という文字列（大文字小文字問わず）が含まれないこと
3. _build_error_feedback の統合テスト: SyntaxErrorInfo を state に追加した場合に
   "Correction Guide"、hint text、"read_file" のガイダンスが出力に含まれること
"""

import pytest
from companion.prompts.builder import PromptBuilder
from companion.state.agent_state import AgentState, SyntaxErrorInfo


class TestCorrectionExamplesKeys:
    """_CORRECTION_EXAMPLES のキー構成に関するテスト"""

    def test_edit_find_mismatch_key_exists(self) -> None:
        """
        _CORRECTION_EXAMPLES に edit_find_mismatch キーが存在すること。

        Fix C での変更: anchor_mismatch → edit_find_mismatch にリネームされた。

        Args: なし
        Returns: なし
        """
        assert "edit_find_mismatch" in PromptBuilder._CORRECTION_EXAMPLES, (
            "_CORRECTION_EXAMPLES に 'edit_find_mismatch' キーが見つからない"
        )

    def test_anchor_mismatch_key_does_not_exist(self) -> None:
        """
        _CORRECTION_EXAMPLES に anchor_mismatch キーが存在しないこと。

        Fix C での変更: anchor_mismatch キーは edit_find_mismatch に置き換えられた。

        Args: なし
        Returns: なし
        """
        assert "anchor_mismatch" not in PromptBuilder._CORRECTION_EXAMPLES, (
            "_CORRECTION_EXAMPLES にまだ 'anchor_mismatch' キーが残っている"
        )


class TestNoAnchorWordInExamples:
    """_CORRECTION_EXAMPLES のすべての値に "anchor" が含まれないことのテスト"""

    def test_anchor_word_absent_from_all_example_values(self) -> None:
        """
        _CORRECTION_EXAMPLES のすべての値（例文テキスト）に、
        大文字・小文字を問わず "anchor" という単語が含まれないこと。

        Fix C の要件: builder.py 内に "anchor" という単語が残ってはならない。
        クラス属性のテキストを検査することで、ソースファイルの読み込みなしに
        ロバストに検証する。

        Args: なし
        Returns: なし
        """
        for key, example_text in PromptBuilder._CORRECTION_EXAMPLES.items():
            assert "anchor" not in example_text.lower(), (
                f"_CORRECTION_EXAMPLES['{key}'] に 'anchor' が含まれている: "
                f"{example_text!r}"
            )


class TestBuildErrorFeedbackIntegration:
    """_build_error_feedback の統合テスト"""

    def test_error_feedback_contains_correction_guide_header(self) -> None:
        """
        last_syntax_errors にエラーが存在する場合、
        _build_error_feedback の出力に "Correction Guide" が含まれること。

        Args: なし
        Returns: なし
        """
        state = AgentState()
        state.last_syntax_errors.append(
            SyntaxErrorInfo(
                error_type="edit_find_mismatch",
                raw_snippet="x",
                correction_hint="hint text"
            )
        )
        builder = PromptBuilder(state)
        feedback = builder._build_error_feedback()

        assert "Correction Guide" in feedback, (
            f"_build_error_feedback の出力に 'Correction Guide' が含まれていない:\n{feedback}"
        )

    def test_error_feedback_contains_hint_text(self) -> None:
        """
        _build_error_feedback の出力に correction_hint に指定したテキストが含まれること。

        Args: なし
        Returns: なし
        """
        state = AgentState()
        state.last_syntax_errors.append(
            SyntaxErrorInfo(
                error_type="edit_find_mismatch",
                raw_snippet="x",
                correction_hint="hint text"
            )
        )
        builder = PromptBuilder(state)
        feedback = builder._build_error_feedback()

        assert "hint text" in feedback, (
            f"_build_error_feedback の出力に correction_hint が含まれていない:\n{feedback}"
        )

    def test_error_feedback_contains_read_file_guidance(self) -> None:
        """
        edit_find_mismatch エラーに対する Correction Guide の例文に
        read_file のガイダンスが含まれること。

        Fix C での変更: edit_find_mismatch の例文はファイルを read_file で確認し、
        find: を正確にコピーするよう誘導する内容になっている。

        Args: なし
        Returns: なし
        """
        state = AgentState()
        state.last_syntax_errors.append(
            SyntaxErrorInfo(
                error_type="edit_find_mismatch",
                raw_snippet="some bad snippet",
                correction_hint="hint text"
            )
        )
        builder = PromptBuilder(state)
        feedback = builder._build_error_feedback()

        assert "read_file" in feedback, (
            f"edit_find_mismatch の Correction Guide に 'read_file' ガイダンスが含まれていない:\n"
            f"{feedback}"
        )

    def test_error_feedback_empty_when_no_errors(self) -> None:
        """
        last_syntax_errors が空の場合、_build_error_feedback は空文字列を返すこと。

        Args: なし
        Returns: なし
        """
        state = AgentState()
        builder = PromptBuilder(state)
        feedback = builder._build_error_feedback()

        assert feedback == "", (
            f"エラーがないのに _build_error_feedback が空でない: {repr(feedback)}"
        )
