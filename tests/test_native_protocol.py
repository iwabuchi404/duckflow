"""Tests for the native tool-calling swap machinery (Phase A)."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from companion.base import native_protocol as np  # noqa: E402


async def _read_file(path: str, start: int = 1) -> str:
    """Read a file.

    Args:
        path: Target path.
        start: First line.

    Returns:
        File content.
    """
    return f"{path}:{start}"


async def _write_file(path: str, content: str) -> str:
    """Write a file.

    Args:
        path: Target path.
        content: Full body text.

    Returns:
        Status message.
    """
    return f"{path}:{len(content)}"


def _tool_call(call_id: str, name: str, args: str):
    """Build a fake native tool-call object."""
    from types import SimpleNamespace as _NS

    return _NS(id=call_id, function=_NS(name=name, arguments=args))


def _tools() -> dict:
    """Fake registry mirroring mode-scoped names."""
    return {
        "read_file": _read_file,
        "write_file": _write_file,
        "response": lambda message: message,
        "duck_call": lambda message: message,
    }


def test_resolve_protocol_defaults_symops(monkeypatch) -> None:
    """Unset switch means Sym-Ops."""
    monkeypatch.delenv("DUCKFLOW_TOOL_PROTOCOL", raising=False)
    assert np.resolve_protocol() == "symops"


def test_resolve_protocol_native(monkeypatch) -> None:
    """Explicit native switch is honored."""
    monkeypatch.setenv("DUCKFLOW_TOOL_PROTOCOL", "native")
    assert np.resolve_protocol() == "native"


def test_build_native_tools_task_mode(monkeypatch) -> None:
    """Mode scoping matches Sym-Ops; control actions excluded."""
    monkeypatch.delenv("DUCKFLOW_TOOL_PROTOCOL", raising=False)
    from companion.core_tools import MODE_TOOL_MAPPING

    MODE_TOOL_MAPPING["task"]  # mapping must exist for the test mode
    defs = np.build_native_tools(_tools(), mode="task")
    names = {d["function"]["name"] for d in defs}
    assert "read_file" in names
    assert "write_file" in names
    assert "response" not in names
    assert "duck_call" not in names


def test_build_native_tools_schema_shape() -> None:
    """Required/optional split and block params as strings."""
    defs = np.build_native_tools(_tools(), mode=None)
    by_name = {d["function"]["name"]: d["function"] for d in defs}
    read = by_name["read_file"]["parameters"]
    assert read["type"] == "object"
    assert read["required"] == ["path"]
    assert read["properties"]["start"]["type"] == "integer"
    write = by_name["write_file"]["parameters"]
    assert write["required"] == ["path", "content"]
    assert write["properties"]["content"]["type"] == "string"


def test_tool_calls_to_actions() -> None:
    """Native calls map to action dicts; unknown names pass through."""
    message = SimpleNamespace(
        content="reasoning here",
        tool_calls=[
            SimpleNamespace(
                id="c1",
                function=SimpleNamespace(
                    name="write_file",
                    arguments='{"path": "a.py", "content": "x"}',
                ),
            ),
            SimpleNamespace(
                id="c2",
                function=SimpleNamespace(name="made_up", arguments="{}"),
            ),
        ],
    )
    actions = np.tool_calls_to_actions(message)
    assert actions[0] == {
        "name": "write_file",
        "parameters": {"path": "a.py", "content": "x"},
        "thought": "",
        "call_id": "c1",
    }
    assert actions[1]["name"] == "made_up"


def test_tool_calls_bad_arguments_become_empty() -> None:
    """Unparseable arguments degrade to empty params, not a crash."""
    message = SimpleNamespace(
        content=None,
        tool_calls=[
            SimpleNamespace(
                id="c1",
                function=SimpleNamespace(name="read_file", arguments="{bad"),
            )
        ],
    )
    assert np.tool_calls_to_actions(message)[0]["parameters"] == {}


def _assistant_log(turn: str = "e:1") -> list:
    """One verbatim native assistant turn with two calls."""
    return [
        {
            "role": "assistant",
            "content": "doing it",
            "_turn": turn,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"path": "a.py"}',
                    },
                },
                {
                    "id": "c2",
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"path": "b.py", "content": "y"}',
                    },
                },
            ],
        }
    ]


def test_rebuild_restores_calls_and_pairs_results() -> None:
    """Summaries drop out; tool results pair with call IDs in order."""
    text = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "do it"},
        {
            "role": "assistant",
            "content": ":: read_file @a.py\n:: write_file @b.py",
            "_native_turn": "e:1",
        },
        {
            "role": "user",
            "content": "[TOOL_RESULT]\n::status ok\n::read_file @a.py\n<<<\nx\n>>>\n[/TOOL_RESULT]",
        },
        {
            "role": "user",
            "content": "[TOOL_RESULT]\n::status ok\n::write_file @b.py\n<<<\nwrote\n>>>\n[/TOOL_RESULT]",
        },
    ]
    out = np.build_native_messages(text, _assistant_log())
    roles = [m["role"] for m in out]
    assert roles == ["system", "user", "assistant", "tool", "tool"]
    assert out[2]["tool_calls"][0]["id"] == "c1"
    # Internal turn metadata must never reach the wire.
    assert "_turn" not in out[2]
    assert out[3] == {"role": "tool", "tool_call_id": "c1", "content": "x"}
    assert out[4]["tool_call_id"] == "c2"


def test_rebuild_keeps_prose_and_denials() -> None:
    """Response prose, history notes, and denial contexts survive."""
    text = [
        {"role": "assistant", "content": "report.json を作成しました。"},
        {"role": "assistant", "content": ":: response"},
        {"role": "assistant", "content": "履歴注記：write_file の本文3文字を送信済み。"},
        {"role": "user", "content": "[User denied approval for action 'x'] Reason: y."},
    ]
    out = np.build_native_messages(text, [])
    assert [m["role"] for m in out] == ["assistant", "user"]
    assert out[0]["content"] == "report.json を作成しました。"
    assert "denied" in out[1]["content"]


def test_rebuild_unrecorded_calls_get_placeholder() -> None:
    """Calls without results still answer every tool_call id.

    An assistant message with tool_calls but missing tool results is
    rejected by OpenAI-compatible APIs, so unrecorded calls (denial,
    abort) emit a placeholder tool message instead of being dropped.
    """
    text = [
        {
            "role": "assistant",
            "content": ":: read_file @a.py\n:: write_file @b.py",
            "_native_turn": "e:1",
        },
        {"role": "user", "content": "[User denied approval for action 'x']"},
        {"role": "assistant", "content": "done"},
    ]
    out = np.build_native_messages(text, _assistant_log(), journal={})
    assistant = next(m for m in out if m.get("tool_calls"))
    call_ids = [c["id"] for c in assistant["tool_calls"]]
    tools = [m for m in out if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tools] == call_ids
    assert all("no recorded result" in m["content"] for m in tools)
    assert any("denied" in (m.get("content") or "") for m in out)
    assert out[-1]["content"] == "done"


def test_tool_calls_carry_call_ids() -> None:
    """Converted actions keep the API call ID for journal pairing."""
    message = SimpleNamespace(
        content=None,
        tool_calls=[
            _tool_call("c9", "read_file", '{"path": "a.py"}'),
        ],
    )
    actions = np.tool_calls_to_actions(message)
    assert actions[0]["call_id"] == "c9"


def test_native_text_question_becomes_duck_call() -> None:
    """Trailing questions map to internal consultation, not response."""
    action = np.native_text_to_action("Which file should I write to?")
    assert action["name"] == "duck_call"
    assert action["parameters"]["message"].endswith("?")
    assert action["call_id"] is None


def test_native_text_statement_becomes_response() -> None:
    """Plain statements map to a terminal response action."""
    action = np.native_text_to_action("Done.")
    assert action["name"] == "response"


def test_rebuild_pairs_by_journal_id() -> None:
    """Journal pairing survives result reordering across turns."""
    log = [
        {
            "role": "assistant",
            "content": "",
            "_turn": "e:1",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": "{}"},
                },
                {
                    "id": "c2",
                    "type": "function",
                    "function": {"name": "write_file", "arguments": "{}"},
                },
            ],
        }
    ]
    text = [
        {
            "role": "assistant",
            "content": ":: read_file @a\n:: write_file @b",
            "_native_turn": "e:1",
        },
        {
            "role": "user",
            "content": "[TOOL_RESULT]\n::status ok\n::write_file @b\n<<<\nok\n>>>\n[/TOOL_RESULT]",
        },
        {
            "role": "user",
            "content": "[TOOL_RESULT]\n::status ok\n::read_file @a\n<<<\nx\n>>>\n[/TOOL_RESULT]",
        },
    ]
    journal = {
        "c1": {"turn": 1, "tool_name": "read_file", "status": "ok",
               "executed": True, "body": "x"},
        "c2": {"turn": 1, "tool_name": "write_file", "status": "ok",
               "executed": True, "body": "ok"},
    }
    out = np.build_native_messages(text, log, journal)
    tools = [m for m in out if m["role"] == "tool"]
    assert [(m["tool_call_id"], m["content"]) for m in tools] == [
        ("c1", "x"),
        ("c2", "ok"),
    ]
    assert not any(
        m.get("role") == "user" and "[TOOL_RESULT]" in (m.get("content") or "")
        for m in out
    )


def test_rebuild_partial_journal_covers_all_calls() -> None:
    """A call missing from the journal gets a placeholder, not a drop."""
    log = [
        {
            "role": "assistant",
            "content": "",
            "_turn": "e:1",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": "{}"},
                },
                {
                    "id": "c2",
                    "type": "function",
                    "function": {"name": "write_file", "arguments": "{}"},
                },
            ],
        }
    ]
    text = [
        {
            "role": "assistant",
            "content": ":: read_file @a\n:: write_file @b",
            "_native_turn": "e:1",
        },
        {
            "role": "user",
            "content": "[TOOL_RESULT]\n::status ok\n::read_file @a\n<<<\nx\n>>>\n[/TOOL_RESULT]",
        },
    ]
    journal = {
        "c1": {"turn": 1, "tool_name": "read_file", "status": "ok",
               "executed": True, "body": "x"},
    }
    out = np.build_native_messages(text, log, journal)
    tools = {m["tool_call_id"]: m["content"] for m in out
             if m["role"] == "tool"}
    # Every emitted tool_call must have a tool result, or the API 400s.
    assistant = next(m for m in out if m.get("tool_calls"))
    assert {c["id"] for c in assistant["tool_calls"]} == set(tools)
    assert tools["c1"] == "x"
    assert "no recorded result" in tools["c2"]


def test_rebuild_turn_keyed_ignores_pretask_summaries() -> None:
    """Summaries from a previous task must not consume new log entries.

    reset_native_log() clears the log but leaves prior summaries in the
    text history; without turn-id pairing, the first old summary would
    absorb the new task's log entry.
    """
    text = [
        {"role": "user", "content": "old task"},
        {"role": "assistant", "content": ":: read_file @old.py"},
        {
            "role": "user",
            "content": "[TOOL_RESULT]\n::status ok\n::read_file @old.py\n<<<\nold\n>>>\n[/TOOL_RESULT]",
        },
        {"role": "user", "content": "new task"},
        {
            "role": "assistant",
            "content": ":: read_file @new.py",
            "_native_turn": "e:5",
        },
        {
            "role": "user",
            "content": "[TOOL_RESULT]\n::status ok\n::read_file @new.py\n<<<\nnew\n>>>\n[/TOOL_RESULT]",
        },
    ]
    log = [
        {
            "role": "assistant",
            "content": "",
            "_turn": "e:5",
            "tool_calls": [
                {
                    "id": "n1",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": "{}"},
                }
            ],
        }
    ]
    journal = {
        "n1": {"turn": 5, "tool_name": "read_file", "status": "ok",
               "executed": True, "body": "new-body"},
    }
    out = np.build_native_messages(text, log, journal)
    assistant = next(m for m in out if m.get("tool_calls"))
    assert assistant["tool_calls"][0]["id"] == "n1"
    tool = next(m for m in out if m["role"] == "tool")
    assert tool["content"] == "new-body"


def test_rebuild_stale_turn_id_does_not_pair() -> None:
    """A summary stamped with an unknown turn never pairs positionally."""
    text = [
        {
            "role": "assistant",
            "content": ":: read_file @a",
            "_native_turn": "e:1",
        },
        {
            "role": "user",
            "content": "[TOOL_RESULT]\n::status ok\n::read_file @a\n<<<\nx\n>>>\n[/TOOL_RESULT]",
        },
    ]
    log = [
        {
            "role": "assistant",
            "content": "",
            "_turn": "e:9",
            "tool_calls": [
                {
                    "id": "c9",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": "{}"},
                }
            ],
        }
    ]
    out = np.build_native_messages(text, log, {})
    assert not any(m.get("tool_calls") for m in out)
    # The envelope survives as user text rather than pairing wrongly.
    assert any("TOOL_RESULT" in (m.get("content") or "") for m in out)


def test_rebuild_drops_journal_misses() -> None:
    """Summaries without a logged turn pass envelopes through as text."""
    text = [
        {"role": "assistant", "content": ":: read_file @a"},
        {"role": "user", "content": "[User denied approval for action 'x']"},
    ]
    out = np.build_native_messages(text, [], {})
    assert not any(m.get("tool_calls") for m in out)
    assert any("denied" in (m.get("content") or "") for m in out)


def test_native_static_prompt_has_no_symops_grammar() -> None:
    """Native mode instructions carry no ::action/<<<>>>/YAML grammar."""
    from companion.prompts.builder import PromptBuilder
    from companion.state.agent_state import AgentState

    builder = PromptBuilder(AgentState())
    native = builder._build_mode_static("", protocol="native")
    for marker in ("::read_file", "::duck_call", "::response", "<<<", ">>>", "Sym-Ops"):
        assert marker not in native, f"leaked marker: {marker}"
    symops = builder._build_mode_static("DESC", protocol="symops")
    assert "::read_file" in symops or "DESC" in symops


def test_native_correction_examples_have_no_symops() -> None:
    """Native Correction Guide examples avoid Sym-Ops syntax."""
    from companion.prompts.builder import PromptBuilder
    from companion.state.agent_state import AgentState, SyntaxErrorInfo

    state = AgentState()
    state.last_syntax_errors.append(
        SyntaxErrorInfo(
            error_type="edit_find_mismatch",
            raw_snippet="x",
            correction_hint="y",
        )
    )
    feedback = PromptBuilder(state)._build_error_feedback(protocol="native")
    assert "Correction Guide" in feedback
    assert "::read_file" not in feedback
    assert ">>>" not in feedback


def test_native_correction_hint_sanitized() -> None:
    """Real Sym-Ops correction hints are rewritten for native prompts."""
    from companion.prompts.builder import PromptBuilder
    from companion.state.agent_state import AgentState, SyntaxErrorInfo

    state = AgentState()
    state.last_syntax_errors.append(
        SyntaxErrorInfo(
            error_type="edit_find_mismatch",
            raw_snippet="x",
            correction_hint=(
                "Next: run ::read_file on the file, copy the target lines "
                "EXACTLY, then retry ::edit_file."
            ),
        )
    )
    feedback = PromptBuilder(state)._build_error_feedback(protocol="native")
    assert "::" not in feedback
    assert "read_file" in feedback
    # Sym-Ops path keeps the original hint untouched.
    symops = PromptBuilder(state)._build_error_feedback(protocol="symops")
    assert "::read_file" in symops


def test_native_build_messages_send_no_fewshot(tmp_path) -> None:
    """Full native prompt assembly contains no Sym-Ops grammar at all."""
    from companion.prompts.builder import PromptBuilder
    from companion.state.agent_state import AgentState

    # Empty working dir keeps the generated repo map out of the check.
    messages = PromptBuilder(
        AgentState(working_directory=str(tmp_path))
    ).build_messages("DESC", protocol="native")
    blob = "\n".join(m.get("content", "") for m in messages)
    for marker in (
        "::read_file",
        "::edit_file",
        "::response",
        "::duck_call",
        "<<<",
        ">>>",
        "Sym-Ops",
    ):
        assert marker not in blob, f"leaked marker: {marker}"


def test_sanitize_tool_references_boundaries() -> None:
    """Only Sym-Ops call notation is rewritten; code tokens survive."""
    assert np.sanitize_tool_references("run ::read_file @a.py first") == (
        "run read_file first"
    )
    assert np.sanitize_tool_references(
        "::finish_investigation @<root cause conclusion>"
    ) == "finish_investigation"
    # C++/code tokens must not be mangled.
    assert np.sanitize_tool_references("std::vector<int> v;") == (
        "std::vector<int> v;"
    )
    assert np.sanitize_tool_references("a::b::c") == "a::b::c"


def test_build_native_tools_param_docs() -> None:
    """Parameter descriptions come from the tool's Args: docstring."""
    defs = np.build_native_tools(_tools(), mode=None)
    by_name = {d["function"]["name"]: d["function"] for d in defs}
    props = by_name["read_file"]["parameters"]["properties"]
    assert props["path"]["description"] == "Target path."
    assert props["start"]["description"] == "First line."


def test_record_native_event_and_reset() -> None:
    """Journal records outcomes and resets per task."""
    from companion.base.llm_client import LLMClient

    client = LLMClient(api_key="dummy")
    client._native_turn = 3
    client.record_native_event("c1", "read_file", "ok", True, "body-text")
    assert client._native_journal["c1"]["turn"] == 3
    assert client._native_journal["c1"]["body"] == "body-text"
    client.reset_native_log()
    assert client._native_journal == {}
    assert client._native_assistant_log == []


def test_record_parse_error_native_hints() -> None:
    """Native api_error uses retry wording, not Sym-Ops format orders."""
    from companion.core_loop_helpers import record_parse_error_if_any
    from companion.state.agent_state import ActionList, AgentState

    state = AgentState()
    action_list = ActionList(
        actions=[],
        reasoning="x",
        parse_error_type="api_error",
        parse_error_detail="boom",
    )
    record_parse_error_if_any(state, action_list, protocol="native")
    assert len(state.last_syntax_errors) == 1
    hint = state.last_syntax_errors[0].correction_hint
    assert "Sym-Ops" not in hint
    assert "Retry" in hint or "retry" in hint


def test_experiment_meta_records_protocol(monkeypatch) -> None:
    """Runner experiment metadata carries the active protocol."""
    from evals.runner import _collect_experiment_meta

    monkeypatch.setenv("DUCKFLOW_TOOL_PROTOCOL", "native")
    meta = _collect_experiment_meta({"id": "x", "task": "t"})
    assert meta["tool_protocol"] == "native"
    assert "expects_question" in meta
    assert os.getenv("DUCKFLOW_TOOL_PROTOCOL") == "native"
