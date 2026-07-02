"""Tests for CoreActions extracted from DuckAgent."""

import pytest

from companion.core_actions import CoreActions
from companion.core import DuckAgent
from companion.state.agent_state import Action, ActionList


class DummyLLM:
    """Minimal LLM stub for DuckAgent tests."""

    usage_stats = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_cost": 0.0,
    }


def _make_agent() -> DuckAgent:
    return DuckAgent(llm_client=DummyLLM())


def _make_actions(agent: DuckAgent) -> CoreActions:
    return agent._actions


# --- action_note ---


@pytest.mark.asyncio
async def test_action_note_prints_and_returns():
    actions = _make_actions(_make_agent())
    result = await actions.action_note(message="hello")
    assert "Notified" in result
    assert "hello" in result


# --- action_response ---


@pytest.mark.asyncio
async def test_action_response_adds_to_history():
    agent = _make_agent()
    actions = _make_actions(agent)
    result = await actions.action_response(message="test reply")
    assert result == "Responded to user."
    assert agent.state.conversation_history[-1]["role"] == "assistant"
    assert agent.state.conversation_history[-1]["content"] == "test reply"


@pytest.mark.asyncio
async def test_action_response_empty_returns_no_message():
    actions = _make_actions(_make_agent())
    result = await actions.action_response(message="")
    assert result == "No message provided."


# --- action_exit ---


@pytest.mark.asyncio
async def test_action_exit_sets_running_false():
    agent = _make_agent()
    agent.running = True
    actions = _make_actions(agent)
    result = await actions.action_exit()
    assert result == "Exiting."
    assert agent.running is False


# --- action_investigate ---


@pytest.mark.asyncio
async def test_action_investigate_switches_mode():
    agent = _make_agent()
    actions = _make_actions(agent)
    result = await actions.action_investigate(reason="test error")
    assert "Investigation Mode started" in result
    assert agent.state.get_context_mode() == "investigation"


# --- action_submit_hypothesis ---


@pytest.mark.asyncio
async def test_action_submit_hypothesis_increments_counter():
    agent = _make_agent()
    agent.state.enter_investigation_mode()
    actions = _make_actions(agent)
    result = await actions.action_submit_hypothesis(hypothesis="bad config")
    assert "Hypothesis #1" in result
    assert agent.state.investigation_state.hypothesis_attempts == 1


@pytest.mark.asyncio
async def test_action_submit_hypothesis_auto_enters_investigation():
    agent = _make_agent()
    actions = _make_actions(agent)
    assert agent.state.investigation_state is None
    result = await actions.action_submit_hypothesis(hypothesis="auto start")
    assert agent.state.investigation_state is not None
    assert "Hypothesis #1" in result


# --- action_finish_investigation ---


@pytest.mark.asyncio
async def test_action_finish_investigation_returns_to_planning():
    agent = _make_agent()
    agent.state.enter_investigation_mode()
    actions = _make_actions(agent)
    result = await actions.action_finish_investigation(conclusion="root cause found")
    assert "Investigation complete" in result
    assert "root cause found" in result
    assert agent.state.get_context_mode() == "planning"


# --- action_execute_batch ---


@pytest.mark.asyncio
async def test_action_execute_batch_returns_fallback_message():
    actions = _make_actions(_make_agent())
    result = await actions.action_execute_batch()
    assert "execute_batch is handled by the parser" in result


# --- _action_noop_symops_marker ---


def test_noop_symops_marker_returns_guidance():
    actions = _make_actions(_make_agent())
    result = actions._action_noop_symops_marker()
    assert "::status" in result
    assert "::result" in result
    assert ">>" in result
