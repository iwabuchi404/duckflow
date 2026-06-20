from typing import Any, Dict, List, Optional

import pytest

from companion.state.agent_state import AgentState, Plan
from companion.tools.results import ToolStatus, format_symops_response
from companion.tools.task_tool import TaskListProposal, TaskTool


class MockTaskLLM:
    """Mock LLM that returns a structured task proposal."""

    def __init__(self) -> None:
        """Initialize the mock call log."""
        self.calls: List[Dict[str, Any]] = []

    async def chat(
        self,
        messages: List[Dict[str, str]],
        response_model: Optional[type] = None,
    ) -> TaskListProposal:
        """
        Return a deterministic TaskListProposal.

        Args:
            messages: Prompt messages passed by TaskTool.
            response_model: Expected Pydantic model.

        Returns:
            A populated TaskListProposal instance.
        """
        self.calls.append({"messages": messages, "response_model": response_model})
        assert response_model is TaskListProposal
        prompt = " ".join(messages[0]["content"].split())
        assert "Return a JSON object" in prompt
        assert "do not emit Sym-Ops actions" in prompt

        return TaskListProposal(
            tasks=[
                {
                    "title": "Create file",
                    "description": "Create a small text file.",
                    "action": {
                        "name": "write_file",
                        "parameters": {"path": "t1.txt", "content": "hello"},
                    },
                },
                {"title": "Review output", "description": "Inspect generated file."},
            ]
        )


@pytest.mark.asyncio
async def test_generate_tasks_uses_structured_json_and_formats_symops_result() -> None:
    """
    TaskTool.generate_tasks should use the auxiliary JSON path and still produce
    a ToolResult that can be embedded as a Sym-Ops tool result.
    """
    state = AgentState()
    state.current_plan = Plan(goal="Test generating tasks")
    state.current_plan.add_step("Step 1", "Create a file and run it")

    llm = MockTaskLLM()
    result = await TaskTool(state, llm).generate_tasks()

    assert len(llm.calls) == 1
    assert result.status is ToolStatus.OK
    assert result.tool_name == "generate_tasks"
    assert result.target == "Step 1"
    assert result.content[0]["title"] == "Create file"
    assert result.content[0]["action"]["name"] == "write_file"
    assert state.current_plan.get_current_step().tasks[0].action.name == "write_file"

    formatted = format_symops_response(result)
    assert formatted.startswith("::status ok\n::generate_tasks @Step 1\n<<<")
    assert "title: Create file" in formatted
    assert "name: write_file" in formatted
