import pytest

from companion.state.agent_state import AgentState, TaskStatus
from companion.tools.plan_tool import PlanTool


@pytest.mark.asyncio
async def test_propose_plan_parses_markdown_steps() -> None:
    """propose_plan should create steps from markdown headings."""
    state = AgentState()
    tool = PlanTool(state)

    result = await tool.propose_plan(
        "## Step 1: Inspect\n"
        "Read the relevant files.\n\n"
        "## Step 2: Patch\n"
        "Apply the fix."
    )

    assert "Plan created with 2 steps" in result
    assert state.current_plan is not None
    assert [step.title for step in state.current_plan.steps] == ["Inspect", "Patch"]
    assert state.current_plan.steps[0].description == "Read the relevant files."


@pytest.mark.asyncio
async def test_mark_step_complete_advances_to_next_step() -> None:
    """mark_step_complete should complete the current step and advance."""
    state = AgentState()
    tool = PlanTool(state)
    await tool.propose_plan("## Step 1: One\nDo one.\n\n## Step 2: Two\nDo two.")

    result = await tool.mark_step_complete()

    assert "Next step: 'Two'" in result
    assert state.current_plan.current_step_index == 1
    assert state.current_plan.steps[0].status == TaskStatus.COMPLETED
    assert state.current_plan.is_complete is False


@pytest.mark.asyncio
async def test_mark_step_complete_marks_plan_complete_on_last_step() -> None:
    """Completing the final step should mark the plan complete."""
    state = AgentState()
    tool = PlanTool(state)
    await tool.propose_plan("## Step 1: Only\nDo it.")

    result = await tool.mark_step_complete()

    assert "All steps finished" in result
    assert state.current_plan.is_complete is True


@pytest.mark.asyncio
async def test_mark_step_complete_without_plan_returns_error_message() -> None:
    """mark_step_complete should handle missing plans without crashing."""
    result = await PlanTool(AgentState()).mark_step_complete()

    assert result == "No active plan."
