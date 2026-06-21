"""
Tool registration and mode-scoped tool description helpers for DuckAgent.
"""

import inspect
from typing import Any, Callable, Mapping

from companion.tools import get_project_tree
from companion.tools.file_ops import file_ops
from companion.tools.memory_tool import MemoryTool


UNIVERSAL_TOOLS = {
    "note",
    "response",
    "exit",
    "duck_call",
    "search_archives",
    "recall",
    "get_project_tree",
}

MODE_TOOL_MAPPING = {
    "planning": {
        "read_file",
        "list_directory",
        "find_files",
        "grep_files",
        "edit_file",
        "write_file",
        "delete_lines",
        "delete_file",
        "analyze_structure",
        "run_command",
        "generate_code",
        "investigate",
        "submit_hypothesis",
        "finish_investigation",
    },
    "investigation": {
        "read_file",
        "list_directory",
        "find_files",
        "grep_files",
        "analyze_structure",
        "propose_plan",
        "generate_tasks",
        "investigate",
        "submit_hypothesis",
        "finish_investigation",
    },
    "task": {
        "read_file",
        "list_directory",
        "find_files",
        "grep_files",
        "edit_file",
        "write_file",
        "delete_lines",
        "delete_file",
        "analyze_structure",
        "mark_step_complete",
        "mark_task_complete",
        "run_command",
        "execute_tasks",
        "execute_batch",
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
    agent.register_tool("note", agent.action_note)
    agent.register_tool("response", agent.action_response)
    agent.register_tool("exit", agent.action_exit)
    agent.register_tool("duck_call", agent.approval_tool.duck_call)

    agent.register_tool("read_file", file_ops.read_file)
    agent.register_tool("write_file", file_ops.write_file)
    agent.register_tool("list_directory", file_ops.list_files)
    agent.register_tool("edit_file", file_ops.edit_file)
    agent.register_tool("find_files", file_ops.find_files)
    agent.register_tool("grep_files", file_ops.grep_files)
    agent.register_tool("delete_lines", file_ops.delete_lines)
    agent.register_tool("delete_file", file_ops.delete_file)

    agent.register_tool("propose_plan", agent.plan_tool.propose_plan)
    agent.register_tool("mark_step_complete", agent.plan_tool.mark_step_complete)
    agent.register_tool("generate_tasks", agent.task_tool.generate_tasks)
    agent.register_tool("mark_task_complete", agent.task_tool.mark_task_complete)

    agent.register_tool("execute_tasks", agent.action_execute_tasks)
    agent.register_tool("run_command", agent.action_run_command)

    agent.memory_tool = MemoryTool()
    agent.register_tool("search_archives", agent.memory_tool.search_archives)
    agent.register_tool("recall", agent.memory_tool.search_archives)

    agent.register_tool("analyze_structure", agent.sub_llm_tools.analyze_structure)
    agent.register_tool("generate_code", agent.sub_llm_tools.generate_code)

    agent.register_tool("investigate", agent.action_investigate)
    agent.register_tool("submit_hypothesis", agent.action_submit_hypothesis)
    agent.register_tool("finish_investigation", agent.action_finish_investigation)

    agent.register_tool("execute_batch", agent.action_execute_batch)
    agent.register_tool("get_project_tree", get_project_tree)

    agent.register_tool("status", agent._action_noop_symops_marker)
    agent.register_tool("result", agent._action_noop_symops_marker)


def get_tool_descriptions(
    tools: Mapping[str, Callable[..., Any]], mode: str | None = None
) -> str:
    """
    Generate mode-scoped tool descriptions in Sym-Ops syntax.

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
            content_param = None

            for p_name in sig.parameters:
                if (
                    p_name
                    in ["path", "command", "reason", "hypothesis", "message", "result"]
                    and not target_param
                ):
                    target_param = p_name
                elif (
                    p_name in ["content", "body", "code", "plan_data"]
                    and not content_param
                ):
                    content_param = p_name
                else:
                    params_list.append(f"{p_name}=val")

            target_str = f" @<{target_param}>" if target_param else ""
            params_str = f" {' '.join(params_list)}" if params_list else ""
            content_str = "\n  <<< <content> >>>" if content_param else ""

            descriptions.append(
                f"- ::{name}{target_str}{params_str}{content_str}: {summary}"
            )
        except (ValueError, TypeError):
            descriptions.append(f"- ::{name}: {summary}")

    return "\n".join(descriptions)
