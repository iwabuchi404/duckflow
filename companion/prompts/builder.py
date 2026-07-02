"""
PromptBuilder モジュール。

AgentState を受け取り、動的にシステムプロンプトを組み立てる。
プロンプトキャッシュを最大限活用するために、静的な部分を前半に、
動的な部分を後半に配置する階層構造を持つ。
"""

from typing import List, Optional

from companion.state.agent_state import AgentState
from companion.prompts.templates import SYSTEM_PROMPT_TEMPLATE, MODE_MAP
from companion.prompts.few_shot import get_examples_for_mode
from companion.utils.response_format import SYMOPS_SYSTEM_PROMPT
from companion.modules.repo_map import generate_repo_map_text
from companion.config.tier_profile import TierProfile


class PromptBuilder:
    """
    AgentState からシステムプロンプトを組み立てるビルダー。
    """

    def __init__(
        self, state: AgentState, tier_profile: Optional[TierProfile] = None
    ) -> None:
        """
        Args:
            state: プロンプト構築元の AgentState。
            tier_profile: 現在のモデルの TierProfile。渡された場合、
                repo map のトークン予算を `tier_profile.repo_map_token_budget`
                で配給する（docs/agent_surface_redesign_design.md §5.2）。
                省略時は repo_map モジュールの既定予算を使う。
        """
        self.state = state
        self.tier_profile = tier_profile

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
        # 4a. Repo Map (先回りコンテキスト: ast-based symbol map)
        repo_map_budget = (
            self.tier_profile.repo_map_token_budget
            if self.tier_profile is not None
            else None
        )
        repo_map_text = generate_repo_map_text(
            self.state.working_directory, token_budget=repo_map_budget
        )

        # 4b. 動的コンテキスト組み立て
        dynamic_parts = [
            "## Current State & Context\n" +
            self.state.to_prompt_context(),
        ]
        if repo_map_text:
            dynamic_parts.append(repo_map_text)
        error_feedback = self._build_error_feedback()
        if error_feedback:
            dynamic_parts.append(error_feedback)

        dynamic_context = "\n\n".join(dynamic_parts).strip()
        
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

    # エラータイプ別の「正しい例」マップ
    _CORRECTION_EXAMPLES: dict = {
        'unknown_tool': (
            '  Good: `::note @Done. Moving to next step.`\n'
            '  Good: `::response @Here is the result.`'
        ),
        'edit_find_mismatch': (
            '  Step 1: `::read_file @path/to/file.py` — confirm the current file content\n'
            '  Step 2: retry `::edit_file` with the SEARCH block copied EXACTLY from the file\n'
            '          (no line-number prefixes, matching whitespace and punctuation)'
        ),
        'missing_param': (
            '  For edit_file, use SEARCH/REPLACE markers in the content block:\n'
            '  ::edit_file @path/to/file.py\n'
            '  <<<\n'
            '  <<<<<<< SEARCH\n'
            '  old code (exact match, no line numbers)\n'
            '  =======\n'
            '  new code\n'
            '  >>>>>>> REPLACE\n'
            '  >>>\n'
            '  Check the tool description for required parameters.'
        ),
        'empty_response': (
            '  If investigation is in progress:\n'
            '    `::read_file @path/to/file.py`  — observe first\n'
            '  If ready to deliver result:\n'
            '    `::response @Your analysis here.`  — inline\n'
            '    or use <<< >>> block for long output'
        ),
        'investigation_edit_blocked': (
            '  You are in Investigation Mode — file edits are blocked.\n'
            '  Step 1: `::finish_investigation @<root cause conclusion>`\n'
            '  Step 2: After switching to Planning/Task mode, apply edits.'
        ),
        'unexpected_params': (
            '  Remove the unsupported parameter(s) and only pass the ones\n'
            '  listed for this tool. Extra parameters are silently dropped,\n'
            '  not applied — repeating them will not change the outcome.'
        ),
        'parse_failed': (
            '  Your last output could not be parsed as Sym-Ops.\n'
            '  Use `::action_name @target key=value` for actions and\n'
            '  `<<< ... >>>` blocks only for large content (code, file text).\n'
            '  Do not wrap actions in markdown code fences.'
        ),
        'empty_actions': (
            '  Your last output produced no action and no response.\n'
            '  Every turn must end with either another `::tool_name` action\n'
            '  or `::response @...` to hand control back to the user.'
        ),
    }

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
                lines.append(f'  Your output: `{err.raw_snippet[:300]}`')
            example = self._CORRECTION_EXAMPLES.get(err.error_type)
            if example:
                lines.append(f'  Example fix:\n{example}')
        lines.append('Apply these corrections in your next output.')
        return '\n'.join(lines)
