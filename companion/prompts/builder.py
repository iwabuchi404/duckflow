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


def interpretation_gate_enabled() -> bool:
    """Return whether the Interpretation Gate prompt circuit is active.

    Experiment switch shared by prompt building and eval metadata.
    Reads DUCKFLOW_INTERPRETATION_GATE ("1"/"true"/"on" enable it).

    Returns:
        True when the gate block should be injected into the prompt.
    """
    import os

    return os.getenv("DUCKFLOW_INTERPRETATION_GATE", "").lower() in (
        "1",
        "true",
        "on",
    )


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

    def build_messages(
        self, tool_descriptions: str, protocol: str = "symops"
    ) -> List[dict]:
        """
        プロンプトキャッシュを最大限活用するためにメッセージリストを構成する。

        構成順序:
        1. system: 静的なプロトコル指示（常にキャッシュ）
        2. system: モード固有のツール説明（同一モード内ではキャッシュ）
        3. user/assistant: モード固有の Few-shot 例（同一モード内ではキャッシュ）
        4. system: 動的な状態コンテキスト（ターンごとに変化）

        Args:
            tool_descriptions: Sym-Opsツール説明。native時はAPI定義で
                渡すため本文には含めない。
            protocol: "symops" または "native"。native時はプロトコル指示を
                差し替え、Few-shotはminimalで汚染を抑える。
        """
        from companion.prompts.templates import NATIVE_TOOL_PREAMBLE

        mode = self.state.get_context_mode()
        native = protocol == "native"

        # 1. 静的なシステム指示（最上位：哲学とプロトコル）
        messages = [
            {
                "role": "system",
                "content": NATIVE_TOOL_PREAMBLE if native else SYMOPS_SYSTEM_PROMPT,
            }
        ]

        # 2. モード固有の指示（ツール説明、モード別の掟）
        mode_instruction = self._build_mode_static(
            "" if native else tool_descriptions,
            protocol="native" if native else "symops",
        )
        messages.append({"role": "system", "content": mode_instruction})

        # 3. モード固有の Few-shot 例
        # 既定は framed（例を参考資料として明示し、実履歴との混同を防ぐ）。
        # DUCKFLOW_FEW_SHOT_FRAMING=bare/minimal で切替可（実験用）。
        # native時はFew-shotを送らない: minimal含め全例がSym-Ops構文
        # (::action, <<< >>>)を含み、出力様式を汚染するため。
        if not native:
            from companion.prompts.few_shot import get_effective_framing

            few_shots = get_examples_for_mode(mode, framing=get_effective_framing())
            if few_shots:
                # 最後の Few-shot メッセージにキャッシュマーカーを付与（Anthropic/OpenRouter用）
                few_shots = [msg.copy() for msg in few_shots]
                few_shots[-1]["cache_control"] = {"type": "ephemeral"}
                messages.extend(few_shots)

        # 3.5 Interpretation Gate（実験回路: DUCKFLOW_INTERPRETATION_GATE=1）
        # 静的ブロックの直後・動的コンテキストの直前に挿入し、静的部分の
        # キャッシュを条件間で共有できるようにする。
        if interpretation_gate_enabled():
            from companion.prompts.templates import INTERPRETATION_GATE_PROMPT

            messages.append(
                {"role": "system", "content": INTERPRETATION_GATE_PROMPT}
            )

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
            "## Current State & Context\n" + self.state.to_prompt_context(),
        ]
        if repo_map_text:
            dynamic_parts.append(repo_map_text)
        error_feedback = self._build_error_feedback(protocol=protocol)
        if error_feedback:
            dynamic_parts.append(error_feedback)

        dynamic_context = "\n\n".join(dynamic_parts).strip()

        if dynamic_context:
            messages.append({"role": "system", "content": dynamic_context})

        return messages

    def _native_template(self) -> str:
        """Build the Sym-Ops-free system template for native mode.

        Replaces the Unified-Action section, the reasoning lines about
        ::action placement, and the whole <tools> schema section with
        native equivalents. Anchors fail loudly on template drift.

        Returns:
            Native system prompt template with format placeholders intact.
        """
        import re as _re

        from companion.prompts.templates import (
            NATIVE_MODE_MAP,
            NATIVE_REASONING_LINES,
            NATIVE_TOOLS_SECTION,
            NATIVE_UNIFIED_ACTION,
        )

        template = SYSTEM_PROMPT_TEMPLATE
        anchor = (
            "6. Unified Action\n"
            "   You interact with the world ONLY through Sym-Ops v3.2 format.\n"
            "   All responses MUST follow the protocol. No JSON or unstructured text."
        )
        if anchor not in template:
            raise ValueError("native template: Unified-Action anchor not found")
        template = template.replace(anchor, NATIVE_UNIFIED_ACTION)
        anchor = (
            "- ALWAYS write your Sym-Ops actions (::action) in the response body, "
            "NOT in the reasoning field."
        )
        if anchor not in template:
            raise ValueError("native template: reasoning anchor not found")
        template = template.replace(anchor, NATIVE_REASONING_LINES)
        anchor = (
            "- If you write :: actions in reasoning, they will be extracted and executed,\n"
            "  but it is more reliable to write them directly in the body."
        )
        if anchor not in template:
            raise ValueError("native template: reasoning-extract anchor not found")
        template = template.replace(
            anchor,
            "- If you describe actions in reasoning only, they will NOT execute.",
        )
        native_template, count = _re.subn(
            r"<tools>.*?</tools>", NATIVE_TOOLS_SECTION, template, flags=_re.DOTALL
        )
        if count != 1:
            raise ValueError("native template: <tools> section not found")
        return native_template

    def _build_mode_static(
        self, tool_descriptions: str, protocol: str = "symops"
    ) -> str:
        """
        モード固有の指示とツール説明を組み立てる。

        Args:
            tool_descriptions: Sym-Opsツール説明（native時は空）。
            protocol: "symops" または "native"。native時はSym-Ops文法を
                含まないテンプレートとモード指示を使う。
        """
        from companion.prompts.templates import NATIVE_MODE_MAP

        mode = self.state.get_context_mode()
        if protocol == "native":
            mode_instructions = NATIVE_MODE_MAP.get(mode, "")
            return (
                self._native_template()
                .format(
                    tool_descriptions=tool_descriptions,
                    mode_specific_instructions=mode_instructions,
                    state_context="",
                )
                .strip()
            )
        mode_instructions = MODE_MAP.get(mode, "")

        return SYSTEM_PROMPT_TEMPLATE.format(
            tool_descriptions=tool_descriptions,
            mode_specific_instructions=mode_instructions,
            state_context="",
        ).strip()

    # エラータイプ別の「正しい例」マップ
    _CORRECTION_EXAMPLES: dict = {
        "unknown_tool": (
            "  Good: `::note @Done. Moving to next step.`\n"
            "  Good: `::response @Here is the result.`"
        ),
        "edit_find_mismatch": (
            "  Step 1: `::read_file @path/to/file.py` — confirm the current file content\n"
            "  Step 2: retry `::edit_file` with the SEARCH block copied EXACTLY from the file\n"
            "          (no line-number prefixes, matching whitespace and punctuation)\n"
            "  Step 3: do NOT resend the failed SEARCH text unchanged — re-copy it from Step 1"
        ),
        "missing_param": (
            "  For edit_file, use SEARCH/REPLACE markers in the content block:\n"
            "  ::edit_file @path/to/file.py\n"
            "  <<<\n"
            "  <<<<<<< SEARCH\n"
            "  old code (exact match, no line numbers)\n"
            "  =======\n"
            "  new code\n"
            "  >>>>>>> REPLACE\n"
            "  >>>\n"
            "  Check the tool description for required parameters."
        ),
        "empty_response": (
            "  If investigation is in progress:\n"
            "    `::read_file @path/to/file.py`  — observe first\n"
            "  If ready to deliver result:\n"
            "    `::response @Your analysis here.`  — inline\n"
            "    or use <<< >>> block for long output"
        ),
        "investigation_edit_blocked": (
            "  You are in Investigation Mode — file edits are blocked.\n"
            "  Step 1: `::finish_investigation @<root cause conclusion>`\n"
            "  Step 2: After switching to Planning/Task mode, apply edits."
        ),
        "unexpected_params": (
            "  Remove the unsupported parameter(s) and only pass the ones\n"
            "  listed for this tool. Extra parameters are silently dropped,\n"
            "  not applied — repeating them will not change the outcome."
        ),
        "parse_failed": (
            "  Your last output could not be parsed as Sym-Ops.\n"
            "  Use `::action_name @target key=value` for actions and\n"
            "  `<<< ... >>>` blocks only for large content (code, file text).\n"
            "  Do not wrap actions in markdown code fences."
        ),
        "empty_actions": (
            "  Your last output produced no action and no response.\n"
            "  Every turn must end with either another `::tool_name` action\n"
            "  or `::response @...` to hand control back to the user."
        ),
        "api_error": (
            "  The API call itself failed (not your output format).\n"
            "  Retry the same actions unchanged."
        ),
        "tool_call_parse_error": (
            "  A tool call had malformed JSON arguments.\n"
            '  Resend it with valid JSON, e.g. {"path": "a.py", "content": "..."}'
        ),
        "fabricated_tool_result": (
            "  Never write `[TOOL_RESULT]` or `::status` lines yourself.\n"
            "  Results come only from the system after real execution.\n"
            "  Emit the `::tool_name` action, then wait for its result."
        ),
        "premature_response": (
            "  You announced work but executed nothing. Do it now:\n"
            "    `::edit_file @path/to/file.py` / `::write_file @path` / "
            "`::run_command @cmd`\n"
            "  If the work is already complete, report the RESULT\n"
            "  (past tense), not a plan of what you will do."
        ),
        "repeated_failure": (
            "  You sent the SAME failing call multiple times — it cannot\n"
            "  succeed unchanged. Change the form, not the retry count:\n"
            "  Step 1: `::read_file @path` — re-confirm current content\n"
            "  Step 2: retry with a corrected call, or switch tools\n"
            "          (e.g. ::write_file for a full rewrite)."
        ),
        "no_progress_stall": (
            "  Planning without execution changes nothing. Pick ONE:\n"
            "    `::read_file @path` / `::edit_file @path` — do real work\n"
            "    `::response @<result>` — if the work is already done\n"
            "    `::duck_call @<question>` — if you need the user"
        ),
    }

    # Native variants without Sym-Ops grammar (only keys that differ).
    _NATIVE_CORRECTION_EXAMPLES: dict = {
        "edit_find_mismatch": (
            "  Step 1: call `read_file` on the path — confirm current content\n"
            "  Step 2: retry `edit_file` with the SEARCH argument copied EXACTLY\n"
            "  Step 3: do NOT resend the failed SEARCH text unchanged"
        ),
        "missing_param": (
            "  Pass all required arguments as JSON, e.g.\n"
            '  {"path": "a.py", "content": "file text here"}\n'
            "  Check the tool schema for required parameters."
        ),
        "empty_response": (
            "  If investigation is in progress: call `read_file` — observe first\n"
            "  If ready to deliver: write the final message as plain text"
        ),
        "investigation_edit_blocked": (
            "  You are in Investigation Mode — file edits are blocked.\n"
            "  Step 1: call `finish_investigation` with the conclusion\n"
            "  Step 2: After switching modes, apply edits."
        ),
        "parse_failed": (
            "  Your last output was not usable.\n"
            "  Call tools with valid JSON arguments."
        ),
        "empty_actions": (
            "  Your last output produced no tool call and no message.\n"
            "  Every turn must end with either another tool call\n"
            "  or a final plain-text message."
        ),
        "unknown_tool": ("  Call only the tools listed in your available tools."),
        "repeated_failure": (
            "  You sent the SAME failing call multiple times — it cannot\n"
            "  succeed unchanged. Change the form, not the retry count:\n"
            "  Step 1: call `read_file` — re-confirm current content\n"
            "  Step 2: retry with corrected arguments, or switch tools\n"
            "          (e.g. write_file for a full rewrite)."
        ),
        "premature_response": (
            "  You announced work but executed nothing. Call the tools\n"
            "  now (edit_file / write_file / run_command ...).\n"
            "  If the work is already complete, report the result in\n"
            "  past tense, not a plan of what you will do."
        ),
        "no_progress_stall": (
            "  Planning without execution changes nothing. Pick ONE:\n"
            "    call read_file / edit_file — do real work\n"
            "    send a final message — if the work is already done\n"
            "    call duck_call — if you need the user"
        ),
    }

    def _build_error_feedback(self, protocol: str = "symops") -> str:
        """
        直前ターンの構文エラーから Correction Guide セクションを生成する。

        Args:
            protocol: "symops" または "native"。native時はSym-Ops文法を
                含まない例示を使う。
        """
        errors = self.state.last_syntax_errors
        if not errors:
            return ""

        # Correction hints live on shared SyntaxErrorInfo objects written
        # for the Sym-Ops surface; native mode rewrites "::name @target"
        # to bare function names so the model is not guided into emitting
        # Sym-Ops text (which would terminate the turn as a response).
        from companion.base.native_protocol import sanitize_tool_references

        examples = (
            self._NATIVE_CORRECTION_EXAMPLES
            if protocol == "native"
            else self._CORRECTION_EXAMPLES
        )
        lines = ["## Correction Guide (from previous turn)"]
        for err in errors:
            hint = err.correction_hint
            if protocol == "native":
                hint = sanitize_tool_references(hint)
            lines.append(f"- **{err.error_type}**: {hint}")
            if err.raw_snippet:
                lines.append(f"  Your output: `{err.raw_snippet[:300]}`")
            example = examples.get(err.error_type)
            if example is None and protocol == "native":
                example = self._CORRECTION_EXAMPLES.get(err.error_type)
                if example:
                    example = sanitize_tool_references(example)
            if example:
                lines.append(f"  Example fix:\n{example}")
        lines.append("Apply these corrections in your next output.")
        return "\n".join(lines)
