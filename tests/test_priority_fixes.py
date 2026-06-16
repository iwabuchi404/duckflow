import os
import sys

import pytest

sys.path.append(os.getcwd())

from companion.base.llm_client import LLMClient
from companion.execution.result_summarizer import ExecutionSummary
from companion.execution.task_executor import TaskExecutor
from companion.modules.memory import SummaryResponse
from companion.state.agent_state import Action, AgentState, Task
from companion.tools.sub_llm_tools import SubLLMTools
from companion.tools.task_tool import TaskListProposal


def test_llm_client_respects_non_action_response_model() -> None:
    """
    LLMClient._parse_response should validate JSON into the requested model
    when response_model is not ActionList.
    """
    client = LLMClient(api_key="dummy")

    task_result = client._parse_response(
        '{"tasks":[{"title":"Task 1","description":"Desc"}]}',
        TaskListProposal,
    )
    summary_result = client._parse_response(
        '{"summary":"done","highlights":[],"next_steps":""}',
        ExecutionSummary,
    )
    memory_result = client._parse_response(
        '{"summary":"important context"}',
        SummaryResponse,
    )

    assert isinstance(task_result, TaskListProposal)
    assert task_result.tasks[0]["title"] == "Task 1"
    assert isinstance(summary_result, ExecutionSummary)
    assert summary_result.summary == "done"
    assert isinstance(memory_result, SummaryResponse)
    assert memory_result.summary == "important context"


def test_task_executor_requires_confirmation_handles_no_action() -> None:
    """
    TaskExecutor._requires_confirmation must not assume task.action is present.
    """
    executor = TaskExecutor(AgentState(), {})

    assert executor._requires_confirmation(Task(title="plain")) is False
    assert executor._requires_confirmation(Task(title="command", command="echo hi")) is True
    assert executor._requires_confirmation(
        Task(
            title="edit",
            action=Action(
                name="edit_file",
                parameters={"path": "a.py", "content": ""},
            ),
        )
    ) is True


@pytest.mark.asyncio
async def test_task_executor_plain_task_yields_instead_of_crashing() -> None:
    """
    A plain task without an action, command, or file path should yield for
    replanning instead of failing before execution.
    """
    executor = TaskExecutor(AgentState(), {})
    summary = await executor.execute_task_list([Task(title="needs planning")])

    assert summary["failed"] == 0
    assert summary["yielded"] is True
    assert "Dynamic planning required" in summary["yield_reason"]


@pytest.mark.asyncio
async def test_sub_llm_tools_use_current_read_file_parameters(monkeypatch) -> None:
    """
    SubLLMTools should call file_ops.read_file with start/end, not removed
    start_line/max_lines parameters.
    """
    calls = []

    async def fake_read_file(path: str, start: int = 1, end: int = 300) -> dict:
        calls.append({"path": path, "start": start, "end": end})
        return {
            "path": path,
            "showing_lines": f"{start}-{start + end - 1}",
            "content": "1|def sample():\n2|    return 1",
        }

    class FakeManager:
        async def analyze_structure(self, code: str) -> str:
            return f"analyzed:{len(code)}"

        async def summarize(self, content: str) -> str:
            return content

        async def generate_code(self, instruction: str, context: str) -> str:
            return instruction + context

    monkeypatch.setattr("companion.tools.sub_llm_tools.file_ops.read_file", fake_read_file)

    result = await SubLLMTools(FakeManager()).analyze_structure("sample.py")

    assert result.startswith("analyzed:")
    assert calls == [{"path": "sample.py", "start": 1, "end": 5000}]
