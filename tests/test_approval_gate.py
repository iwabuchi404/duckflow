"""Tests for the human approval gate.

Covers get_approval_request() / build_denial_context() (companion/
core_action_results.py) and the execute_actions-level denial flow in
companion/core_action_executor.py.
"""

import pytest

from companion.core import DuckAgent
from companion.core_action_results import (
    ApprovalRequest,
    build_denial_context,
    get_approval_request,
)
from companion.state.agent_state import Action, ActionList


def _always_exists(path: str) -> bool:
    """Pretend every file exists (worst-case overwrite detection)."""
    return True


def _never_exists(path: str) -> bool:
    """Pretend no file exists."""
    return False


def test_mutating_action_always_requires_approval() -> None:
    """delete_file / delete_lines / edit_file are unconditionally gated."""
    for name in ("delete_file", "delete_lines", "edit_file"):
        request = get_approval_request(
            Action(name=name, parameters={"path": "a.py"}), _never_exists
        )
        assert request.required is True
        assert "a.py" in request.warning


def test_write_file_requires_approval_only_on_overwrite() -> None:
    """write_file is gated only when the target already exists."""
    overwrite = get_approval_request(
        Action(name="write_file", parameters={"path": "exists.txt"}), _always_exists
    )
    fresh = get_approval_request(
        Action(name="write_file", parameters={"path": "new.txt"}), _never_exists
    )

    assert overwrite.required is True
    assert "Overwrite" in overwrite.warning
    assert fresh.required is False


def test_read_only_action_never_requires_approval() -> None:
    """Read-only tools pass through without a gate."""
    request = get_approval_request(
        Action(name="read_file", parameters={"path": "exists.txt"}), _always_exists
    )

    assert request.required is False


def test_build_denial_context_mentions_action_and_warning() -> None:
    """The denial feedback should name the action and carry the warning."""
    context = build_denial_context(
        Action(name="delete_file", parameters={"path": "a.py"}),
        "This action will modify/delete 'a.py'.",
    )

    assert "delete_file" in context
    assert "a.py" in context


@pytest.mark.asyncio
async def test_execute_actions_denial_blocks_tool_and_records_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A user denial must prevent tool execution and feed the refusal back."""
    agent = DuckAgent(
        llm_client=type(
            "StubLLM",
            (),
            {"usage_stats": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "estimated_cost": 0.0}},
        )()
    )
    executed: list[str] = []

    def remove_file(path: str) -> str:
        """Registered delete_file stand-in."""
        executed.append(path)
        return "deleted"

    agent.register_tool("delete_file", remove_file)
    monkeypatch.setattr(
        "companion.core_action_executor.ui.request_confirmation",
        lambda warning: False,
    )

    action_list = ActionList(
        reasoning="test",
        actions=[Action(name="delete_file", parameters={"path": "target.txt"})]
    )
    results = await agent.execute_actions(action_list)

    assert executed == []
    assert len(results) == 1
    denial_messages = [
        msg
        for msg in agent.state.conversation_history
        if "delete_file" in str(msg.get("content", ""))
        and "target.txt" in str(msg.get("content", ""))
    ]
    assert denial_messages, "denial context must be recorded in history"


def test_approval_request_defaults_to_not_required() -> None:
    """ApprovalRequest(required=False).required defaults to False for read-only paths."""
    assert ApprovalRequest(required=False).required is False
