"""
PromptBuilder モジュール。

AgentState を受け取り、動的にシステムプロンプトを組み立てる。
エラーフィードバックセクションの注入もここで行う。
"""

from typing import List

from companion.state.agent_state import AgentState
from companion.prompts.templates import SYSTEM_PROMPT_TEMPLATE, MODE_MAP
from companion.prompts.few_shot import FEW_SHOT_EXAMPLES
from companion.utils.response_format import SYMOPS_SYSTEM_PROMPT


class PromptBuilder:
    """
    AgentState からシステムプロンプトを組み立てるビルダー。

    Args:
        state: 現在のエージェント状態
    """

    def __init__(self, state: AgentState) -> None:
        self.state = state

    def build(self, tool_descriptions: str) -> str:
        """
        完全なシステムプロンプトを組み立てる。

        Args:
            tool_descriptions: ツール一覧の説明文

        Returns:
            ベーステンプレート + エラーフィードバック + Sym-Ops仕様 を結合した文字列
        """
        sections = [
            self._build_base(tool_descriptions),
            self._build_error_feedback(),
            SYMOPS_SYSTEM_PROMPT,
        ]
        return '\n\n'.join(s for s in sections if s)

    def get_few_shot_examples(self) -> List[dict]:
        """
        Few-Shot例を返す。

        Returns:
            LLMがSym-Ops構文を学習するための会話ペアのリスト
        """
        return FEW_SHOT_EXAMPLES

    def _build_base(self, tool_descriptions: str) -> str:
        """
        ベーステンプレートをフォーマットして返す。

        Args:
            tool_descriptions: ツール一覧の説明文

        Returns:
            モード指示を含むベースプロンプト
        """
        mode = self.state.get_context_mode()
        mode_instructions = MODE_MAP.get(mode, '')
        return SYSTEM_PROMPT_TEMPLATE.format(
            tool_descriptions=tool_descriptions,
            state_context=self.state.to_prompt_context(),
            mode_specific_instructions=mode_instructions,
        )

    def _build_error_feedback(self) -> str:
        """
        直前ターンの構文エラーから Correction Guide セクションを生成する。

        Returns:
            エラーがなければ空文字列、あれば修正ガイドのMarkdown
        """
        errors = self.state.last_syntax_errors
        if not errors:
            return ''

        lines = ['## Correction Guide (from previous turn)']
        for err in errors:
            lines.append(f'- **{err.error_type}**: {err.correction_hint}')
            if err.raw_snippet:
                lines.append(f'  Your output: `{err.raw_snippet[:100]}`')
        lines.append('Apply these corrections in your next output.')
        return '\n'.join(lines)
