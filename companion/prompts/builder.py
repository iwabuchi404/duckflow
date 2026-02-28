"""
PromptBuilder モジュール。

AgentState を受け取り、動的にシステムプロンプトを組み立てる。
プロンプトキャッシュを最大限活用するために、静的な部分を前半に、
動的な部分を後半に配置する階層構造を持つ。
"""

from typing import List

from companion.state.agent_state import AgentState
from companion.prompts.templates import SYSTEM_PROMPT_TEMPLATE, MODE_MAP
from companion.prompts.few_shot import get_examples_for_mode
from companion.utils.response_format import SYMOPS_SYSTEM_PROMPT


class PromptBuilder:
    """
    AgentState からシステムプロンプトを組み立てるビルダー。
    """

    def __init__(self, state: AgentState) -> None:
        self.state = state

    def build_messages(self, tool_descriptions: str) -> List[dict]:
        """
        プロンプトキャッシュを最大限活用するためにメッセージリストを構成する。
        
        構成順序:
        1. system: 静的なプロトコル指示（常にキャッシュ）
        2. system: モード固有のツール説明（同一モード内ではキャッシュ）
        3. user/assistant: モード固有の Few-shot 例（同一モード内ではキャッシュ）
        4. system: 動的な状態コンテキスト（ターンごとに変化）
        """
        mode = self.state.get_context_mode()
        
        # 1. 静的なシステム指示（最上位：哲学とプロトコル）
        messages = [
            {"role": "system", "content": SYMOPS_SYSTEM_PROMPT}
        ]
        
        # 2. モード固有の指示（ツール説明、モード別の掟）
        mode_instruction = self._build_mode_static(tool_descriptions)
        messages.append({"role": "system", "content": mode_instruction})
        
        # 3. モード固有の Few-shot 例
        few_shots = get_examples_for_mode(mode)
        if few_shots:
            # 最後の Few-shot メッセージにキャッシュマーカーを付与（Anthropic/OpenRouter用）
            few_shots = [msg.copy() for msg in few_shots]
            few_shots[-1]["cache_control"] = {"type": "ephemeral"}
            messages.extend(few_shots)
        
        # 4. 動的なコンテキスト（ここから毎ターン確実に変動する）
        dynamic_context = (
            "## Current State & Context\n" +
            self.state.to_prompt_context() + "\n\n" +
            self._build_error_feedback()
        ).strip()
        
        if dynamic_context:
            messages.append({"role": "system", "content": dynamic_context})
            
        return messages

    def _build_mode_static(self, tool_descriptions: str) -> str:
        """
        モード固有の指示とツール説明を組み立てる。
        """
        mode = self.state.get_context_mode()
        mode_instructions = MODE_MAP.get(mode, '')
        
        return SYSTEM_PROMPT_TEMPLATE.format(
            tool_descriptions=tool_descriptions,
            mode_specific_instructions=mode_instructions,
            state_context="" 
        ).strip()

    def _build_error_feedback(self) -> str:
        """
        直前ターンの構文エラーから Correction Guide セクションを生成する。
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
