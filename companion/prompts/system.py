"""
後方互換ラッパーモジュール。

テンプレートとFew-Shotは templates.py / few_shot.py に分離済み。
既存コードからの `from companion.prompts.system import get_system_prompt, FEW_SHOT_EXAMPLES`
が壊れないように re-export する。
"""

from companion.prompts.templates import (
    SYSTEM_PROMPT_TEMPLATE,
    INVESTIGATION_MODE_INSTRUCTIONS,
    PLANNING_MODE_INSTRUCTIONS,
    TASK_MODE_INSTRUCTIONS,
    MODE_MAP,
)
from companion.prompts.few_shot import FEW_SHOT_EXAMPLES
from companion.utils.response_format import SYMOPS_SYSTEM_PROMPT

# 後方互換: ActionList のインポートも維持
from companion.state.agent_state import ActionList  # noqa: F401


def get_system_prompt(tool_descriptions: str, state_context: str, mode: str = "planning") -> str:
    """
    システムプロンプトを組み立てる（後方互換ラッパー）。

    Args:
        tool_descriptions: ツール一覧の説明文
        state_context: AgentState.to_prompt_context() の出力
mode: "planning" | "investigation" | "task"

    Returns:
        完全なシステムプロンプト文字列
    """
    mode_instructions = MODE_MAP.get(mode, '')

    base_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        tool_descriptions=tool_descriptions,
        state_context=state_context,
        mode_specific_instructions=mode_instructions,
    )

    return base_prompt + '\n\n' + SYMOPS_SYSTEM_PROMPT