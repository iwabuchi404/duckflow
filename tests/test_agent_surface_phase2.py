"""Tests for Phase 2 of docs/agent_surface_redesign_design.md: tool surface
reduction (list_files / find_symbol / complete_step consolidation, and mode
mapping updates).
"""

import pytest

from companion.core import DuckAgent
from companion.core_tools import MODE_TOOL_MAPPING, UNIVERSAL_TOOLS
from companion.state.agent_state import AgentState, TaskStatus
from companion.tools.file_ops import FileOps
from companion.tools.plan_tool import PlanTool
from companion.tools.symbols import find_symbol


class DummyLLM:
    """Minimal LLM stub for DuckAgent registration tests."""

    usage_stats = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_cost": 0.0,
    }


# --- list_files ---


@pytest.fixture
def workspace(tmp_path):
    """Create a small workspace tree for list_files tests."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n")
    (tmp_path / "src" / "util.py").write_text("def helper(): pass\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "readme.md").write_text("# Readme\n")
    return tmp_path


@pytest.fixture
def file_ops(workspace):
    return FileOps(workspace_root=str(workspace))


@pytest.mark.asyncio
async def test_list_files_tree_mode_without_glob(file_ops):
    """Without glob, list_files should show a directory tree."""
    result = await file_ops.list_files(path=".")

    assert "src" in result
    assert "docs" in result


@pytest.mark.asyncio
async def test_list_files_glob_mode_finds_matching_files(file_ops):
    """With glob, list_files should recursively find matching files."""
    result = await file_ops.list_files(path=".", glob="*.py")

    assert "src/main.py" in result.replace("\\", "/")
    assert "src/util.py" in result.replace("\\", "/")
    assert "readme.md" not in result


@pytest.mark.asyncio
async def test_list_files_glob_mode_no_matches(file_ops):
    """With glob and no matches, list_files should say so instead of erroring."""
    result = await file_ops.list_files(path=".", glob="*.rs")

    assert "No files matching" in result


# --- find_symbol ---


@pytest.fixture
def symbol_workspace(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text(
        '''def alpha():
    """Alpha function."""
    return 1


class Beta:
    """Beta class."""

    def gamma(self):
        return 2
'''
    )
    return tmp_path


@pytest.mark.asyncio
async def test_find_symbol_by_name_delegates_to_find_definition(symbol_workspace):
    """find_symbol(name=...) should behave like find_definition."""
    result = await find_symbol(name="alpha", scope="pkg", workspace_root=str(symbol_workspace))

    assert "alpha" in result
    assert "pkg" in result.replace("\\", "/")


@pytest.mark.asyncio
async def test_find_symbol_by_path_delegates_to_list_symbols(symbol_workspace):
    """find_symbol(path=...) should behave like list_symbols."""
    result = await find_symbol(path="pkg/mod.py", workspace_root=str(symbol_workspace))

    assert "alpha" in result
    assert "Beta" in result
    assert "gamma" in result


@pytest.mark.asyncio
async def test_find_symbol_requires_name_or_path(symbol_workspace):
    """find_symbol with neither name nor path should return a clear error."""
    result = await find_symbol(workspace_root=str(symbol_workspace))

    from companion.tools.results import ToolResult

    assert isinstance(result, ToolResult)
    assert "requires either" in result.content


# --- complete_step ---


@pytest.mark.asyncio
async def test_complete_step_advances_through_tasks_before_closing_step():
    """complete_step should complete tasks one at a time before closing the step."""
    state = AgentState()
    tool = PlanTool(state)
    await tool.propose_plan("## Step 1: Only\nDo it.")
    current_step = state.current_plan.get_current_step()
    current_step.add_task("Task A")
    current_step.add_task("Task B")

    result1 = await tool.complete_step()
    assert "Task 'Task A' completed" in result1
    assert "1 task(s) remaining" in result1
    assert current_step.tasks[0].status == TaskStatus.COMPLETED
    assert state.current_plan.is_complete is False

    # Completing the last task in the step closes the step in the same call
    # (no extra no-op call needed).
    result2 = await tool.complete_step()
    assert current_step.tasks[1].status == TaskStatus.COMPLETED
    assert "All steps finished" in result2
    assert state.current_plan.is_complete is True


@pytest.mark.asyncio
async def test_complete_step_without_tasks_closes_step_directly():
    """complete_step on a step with no tasks should behave like the old
    mark_step_complete()."""
    state = AgentState()
    tool = PlanTool(state)
    await tool.propose_plan("## Step 1: One\nDo one.\n\n## Step 2: Two\nDo two.")

    result = await tool.complete_step()

    assert "Next step: 'Two'" in result
    assert state.current_plan.current_step_index == 1


@pytest.mark.asyncio
async def test_complete_step_without_plan_returns_error_message():
    """complete_step should handle missing plans without crashing."""
    result = await PlanTool(AgentState()).complete_step()

    assert result == "No active plan."


# --- mode mapping / tool surface reduction ---


def test_retired_actions_are_no_longer_registered():
    """Tools merged into list_files / find_symbol / complete_step must not
    remain independently callable — otherwise the surface reduction is
    cosmetic only (the model could still discover and use the old names)."""
    agent = DuckAgent(llm_client=DummyLLM())

    retired = {
        "list_directory",
        "find_files",
        "get_project_tree",
        "list_symbols",
        "find_definition",
        "mark_step_complete",
        "mark_task_complete",
    }
    assert retired.isdisjoint(agent.tools.keys())


def test_hidden_actions_remain_registered_internally():
    """Tools hidden from the prompt (not merged, capability paused pending
    later phases) must stay registered so nothing silently breaks."""
    agent = DuckAgent(llm_client=DummyLLM())

    hidden_but_kept = {
        "note",
        "delete_lines",
        "append_file",
        "search_archives",
        "analyze_structure",
        "generate_code",
        "generate_tasks",
        "execute_tasks",
        "execute_batch",
    }
    assert hidden_but_kept.issubset(agent.tools.keys())


def test_unified_tools_are_registered_and_universal():
    """list_files / find_symbol should be registered and exposed in every mode."""
    agent = DuckAgent(llm_client=DummyLLM())

    assert "list_files" in agent.tools
    assert "find_symbol" in agent.tools
    assert "complete_step" in agent.tools
    assert {"list_files", "find_symbol"}.issubset(UNIVERSAL_TOOLS)


def test_hidden_tools_are_excluded_from_every_mode_mapping():
    """Hidden tools must not appear in any mode's exposed tool set, even
    though they remain registered internally."""
    hidden = {
        "note",
        "delete_lines",
        "append_file",
        "search_archives",
        "analyze_structure",
        "generate_code",
        "generate_tasks",
        "execute_tasks",
        "execute_batch",
    }
    for mode, mode_tools in MODE_TOOL_MAPPING.items():
        exposed = UNIVERSAL_TOOLS | mode_tools
        assert hidden.isdisjoint(exposed), f"hidden tool leaked into mode '{mode}'"


def test_task_mode_tool_surface_matches_design_count():
    """Task mode should expose exactly the 14-tool surface from
    docs/agent_surface_redesign_design.md §4.2."""
    exposed = UNIVERSAL_TOOLS | MODE_TOOL_MAPPING["task"]
    assert len(exposed) == 14
    assert "complete_step" in exposed
    assert "generate_tasks" not in exposed


def test_planning_mode_tool_surface_matches_design_count():
    """Planning mode should expose exactly the 15-tool surface."""
    exposed = UNIVERSAL_TOOLS | MODE_TOOL_MAPPING["planning"]
    assert len(exposed) == 15


def test_investigation_mode_tool_surface_matches_design_count():
    """Investigation mode should expose exactly the 11-tool surface."""
    exposed = UNIVERSAL_TOOLS | MODE_TOOL_MAPPING["investigation"]
    assert len(exposed) == 11


# --- tool description type annotations (§4.3) ---


def test_tool_descriptions_show_required_and_optional_param_types():
    """Tool descriptions must show a type for every parameter, and mark
    optional ones with their default — this is the direct fix for
    hallucinated parameter names/types identified in the Phase 2 design doc."""
    agent = DuckAgent(llm_client=DummyLLM())
    desc = agent.get_tool_descriptions("task")

    grep_line = next(line for line in desc.splitlines() if line.startswith("- ::grep_files"))
    assert "pattern:str" in grep_line  # required, no default shown
    assert '[include:str="*"]' in grep_line  # optional, default shown


def test_tool_descriptions_unwrap_optional_type_instead_of_showing_union():
    """Optional[str] params must render as `name:str=null`, not the
    uninformative literal 'Union' (Python 3.10+ typing quirk)."""
    agent = DuckAgent(llm_client=DummyLLM())
    desc = agent.get_tool_descriptions("task")

    list_files_line = next(
        line for line in desc.splitlines() if line.startswith("- ::list_files")
    )
    assert "[glob:str=null]" in list_files_line
    assert "Union" not in list_files_line
