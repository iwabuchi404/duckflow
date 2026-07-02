"""
Tool registration and mode-scoped tool description helpers for DuckAgent.
"""

import inspect
import types
import typing
from typing import Any, Callable, Mapping

from companion.tools.file_ops import file_ops
from companion.tools.memory_tool import MemoryTool
from companion.tools.symbols import find_symbol, replace_function
from companion.tools.retrieve_result_tool import make_retrieve_result_tool


# モデル接触面の再設計（docs/agent_surface_redesign_design.md §4）に基づく
# ツール面。25個から14〜15個へ縮小し、選択の曖昧さを減らす。
#
# 縮小の内訳:
#   - list_directory / find_files / get_project_tree → list_files に統合
#   - list_symbols / find_definition → find_symbol に統合
#   - mark_step_complete / mark_task_complete → complete_step に統合
#     （上記6ツールの旧アクション名は register_default_tools() で
#       登録されなくなり、内部実装のみとして残る）
#   - note / delete_lines / append_file / search_archives / analyze_structure /
#     generate_code / generate_tasks / execute_tasks / execute_batch は
#     ツール面（UNIVERSAL_TOOLS / MODE_TOOL_MAPPING）から除外するが、
#     register_default_tools() では引き続き登録し、内部的には呼び出し可能に
#     保つ（generate_tasks/execute_tasks はハーネス駆動化するPhase 4まで、
#     execute_batch はパーサーによる %%% 展開のフォールバックとして必要）。
UNIVERSAL_TOOLS = {
    "response",
    "exit",
    "duck_call",
    "list_files",
    "find_symbol",
    "retrieve_result",
}

MODE_TOOL_MAPPING = {
    "planning": {
        "read_file",
        "grep_files",
        "edit_file",
        "write_file",
        "delete_file",
        "run_command",
        "propose_plan",
        "investigate",
        "replace_function",
    },
    "investigation": {
        "read_file",
        "grep_files",
        "run_command",
        "submit_hypothesis",
        "finish_investigation",
    },
    "task": {
        "read_file",
        "grep_files",
        "edit_file",
        "write_file",
        "delete_file",
        "run_command",
        "replace_function",
        "complete_step",
    },
}


def register_default_tools(agent: Any) -> None:
    """
    Register DuckAgent's default callable tools.

    Args:
        agent: DuckAgent-like object with initialized tool dependencies and
            action methods.

    Returns:
        None.
    """
    actions = agent._actions
    # note はツール面から撤去済み（>> Thought に統合）だが、レガシー呼び出しが
    # 来ても壊れないよう内部的には登録を維持する。
    agent.register_tool("note", actions.action_note)
    agent.register_tool("response", actions.action_response)
    agent.register_tool("exit", actions.action_exit)
    agent.register_tool("duck_call", agent.approval_tool.duck_call)

    agent.register_tool("read_file", file_ops.read_file)
    agent.register_tool("write_file", file_ops.write_file)
    # append_file / delete_lines はツール面から撤去済み（edit_file で代替可能）。
    # 実装は内部的に維持（delete_lines は find:/replace: 後方互換の単体テスト対象）。
    agent.register_tool("append_file", file_ops.append_file)
    # list_files は list_directory / find_files / get_project_tree の統合ツール。
    agent.register_tool("list_files", file_ops.list_files)
    agent.register_tool("edit_file", file_ops.edit_file)
    agent.register_tool("grep_files", file_ops.grep_files)
    agent.register_tool("delete_lines", file_ops.delete_lines)
    agent.register_tool("delete_file", file_ops.delete_file)

    agent.register_tool("propose_plan", agent.plan_tool.propose_plan)
    # complete_step は mark_step_complete / mark_task_complete の統合ツール。
    agent.register_tool("complete_step", agent.plan_tool.complete_step)
    # generate_tasks / execute_tasks はツール面から撤去済み（Phase 4でハーネス
    # 駆動化するまでの間、内部的には維持。complete_step は現行タスク階層と
    # 独立に動作するため、これらが呼ばれなくても Step 完了は可能）。
    agent.register_tool("generate_tasks", agent.task_tool.generate_tasks)
    agent.register_tool("execute_tasks", actions.action_execute_tasks)
    agent.register_tool("run_command", actions.action_run_command)

    agent.memory_tool = MemoryTool()
    # search_archives はツール面から撤去済み（将来の長期記憶自動注入 L-c の
    # 受け皿として ArchiveStorage・検索実装は維持）。
    agent.register_tool("search_archives", agent.memory_tool.search_archives)

    # analyze_structure / generate_code はツール面から撤去済み（システム駆動の
    # 自動エスカレーションに置き換え予定。SubLLMManager 基盤は維持）。
    agent.register_tool("analyze_structure", agent.sub_llm_tools.analyze_structure)
    agent.register_tool("generate_code", agent.sub_llm_tools.generate_code)

    agent.register_tool("investigate", actions.action_investigate)
    agent.register_tool("submit_hypothesis", actions.action_submit_hypothesis)
    agent.register_tool("finish_investigation", actions.action_finish_investigation)

    # execute_batch はツール面から非表示化済み（パーサーが %%% を個別アクション
    # へ展開するため、展開成功時はこの関数まで到達しない。展開失敗時の
    # フォールバックとして維持）。
    agent.register_tool("execute_batch", actions.action_execute_batch)

    # find_symbol は list_symbols / find_definition の統合ツール。
    agent.register_tool("find_symbol", find_symbol)
    agent.register_tool("replace_function", replace_function)

    agent.register_tool("retrieve_result", make_retrieve_result_tool(agent))

    agent.register_tool("status", actions._action_noop_symops_marker)
    agent.register_tool("result", actions._action_noop_symops_marker)


def _format_type_name(annotation: Any) -> str:
    """
    Render a parameter annotation as a short, model-readable type name.

    `Optional[X]` / `X | None` unwraps to just "X" — the surrounding
    `[name:type=default]` bracket notation already conveys optionality,
    so showing "Union"/"Optional[X]" here would be redundant and, on
    Python 3.10+, `Union[...].__name__` renders as the uninformative
    literal "Union".

    Args:
        annotation: The `inspect.Parameter.annotation` value.

    Returns:
        A short type name (e.g. "str", "int"), or "any" when unannotated.
    """
    if annotation is inspect.Parameter.empty:
        return "any"

    origin = typing.get_origin(annotation)
    if origin is typing.Union or origin is types.UnionType:
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return _format_type_name(args[0])
        return "|".join(_format_type_name(a) for a in args)

    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


def _format_default(default: Any) -> str:
    """
    Render a parameter default value for display in a tool description.

    Args:
        default: The `inspect.Parameter.default` value.

    Returns:
        A compact string representation (quoted for strings, "null" for None).
    """
    if isinstance(default, str):
        return f'"{default}"'
    if default is None:
        return "null"
    return str(default)


def get_tool_descriptions(
    tools: Mapping[str, Callable[..., Any]], mode: str | None = None
) -> str:
    """
    Generate mode-scoped tool descriptions in Sym-Ops syntax.

    Each parameter is annotated with its type, and optional parameters show
    their default value (e.g. `path:str="."`, required params show only
    `pattern:str`). This is intended to reduce hallucinated parameter names
    and types, particularly for weaker models (docs/agent_surface_redesign_design.md §4.3).

    Args:
        tools: Registered tool name to callable mapping.
        mode: Agent mode name. Unknown modes expose universal tools only.

    Returns:
        Formatted tool descriptions in Sym-Ops style.
    """
    allowed_tools = None
    if mode and mode in MODE_TOOL_MAPPING:
        allowed_tools = UNIVERSAL_TOOLS | MODE_TOOL_MAPPING[mode]
    elif mode:
        allowed_tools = UNIVERSAL_TOOLS

    descriptions = []
    for name, func in tools.items():
        if allowed_tools is not None and name not in allowed_tools:
            continue

        full_doc = inspect.getdoc(func) or "No description."
        summary = full_doc.split("\n\n")[0].replace("\n", " ")

        try:
            sig = inspect.signature(func)
            params_list = []
            target_param = None
            target_type = "any"
            content_param = None

            # Params that are passed inside the <<<>>> content block,
            # not as inline key=value arguments
            _CONTENT_BLOCK_PARAMS = {
                "content", "body", "code", "plan_data", "goal",
                "find", "replace", "occurrence",  # edit_file: SEARCH/REPLACE in block
            }

            for p_name, p in sig.parameters.items():
                # **kwargs はツール説明に出さない
                if p.kind == inspect.Parameter.VAR_KEYWORD:
                    continue
                if (
                    p_name
                    in [
                        "path",
                        "command",
                        "reason",
                        "hypothesis",
                        "message",
                        "result",
                        "query",
                        "task_index",
                        "name",
                        "conclusion",
                        "cache_id",
                    ]
                    and not target_param
                ):
                    target_param = p_name
                    target_type = _format_type_name(p.annotation)
                elif p_name in _CONTENT_BLOCK_PARAMS:
                    # 最初の content-block パラメータだけ「ブロックあり」を示す。
                    # 残り（edit_file の find/replace/occurrence 等）は
                    # SEARCH/REPLACE マーカー内に含まれるためインライン表示しない。
                    if not content_param:
                        content_param = p_name
                else:
                    type_name = _format_type_name(p.annotation)
                    if p.default is inspect.Parameter.empty:
                        params_list.append(f"{p_name}:{type_name}")
                    else:
                        params_list.append(
                            f"[{p_name}:{type_name}={_format_default(p.default)}]"
                        )

            target_str = f" @<{target_param}:{target_type}>" if target_param else ""
            params_str = f" {' '.join(params_list)}" if params_list else ""
            content_str = "\n  <<< <content> >>>" if content_param else ""

            descriptions.append(
                f"- ::{name}{target_str}{params_str}{content_str}: {summary}"
            )
        except (ValueError, TypeError):
            descriptions.append(f"- ::{name}: {summary}")

    return "\n".join(descriptions)
