"""Tests for the native tool-calling probe (no live API calls)."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.tool_probe.fetch_catalog import (  # noqa: E402
    configured_openrouter_ids,
    extract_catalog,
)
from evals.tool_probe.probe import (  # noqa: E402
    build_tool_result_messages,
    extract_tool_calls,
    run_probe,
)


def _catalog_fixture() -> list[dict]:
    """Minimal OpenRouter-style model list."""
    return [
        {
            "id": "minimax/minimax-m2.1",
            "supported_parameters": ["temperature", "tool_choice", "tools"],
        },
        {
            "id": "inference-net/schematron-v2-small",
            "supported_parameters": ["temperature", "structured_outputs"],
        },
    ]


def test_extract_catalog_flags_tools() -> None:
    """Tool advertisement flags follow supported_parameters."""
    entries = extract_catalog(
        _catalog_fixture(),
        ["minimax/minimax-m2.1", "inference-net/schematron-v2-small", "no/such-model"],
    )
    by_id = {e["id"]: e for e in entries}
    assert by_id["minimax/minimax-m2.1"]["found"] is True
    assert by_id["minimax/minimax-m2.1"]["tools_advertised"] is True
    assert by_id["minimax/minimax-m2.1"]["structured_outputs_advertised"] is False
    assert by_id["inference-net/schematron-v2-small"]["tools_advertised"] is False
    assert (
        by_id["inference-net/schematron-v2-small"]["structured_outputs_advertised"]
        is True
    )
    missing = by_id["no/such-model"]
    assert missing["found"] is False
    assert missing["tools_advertised"] is None


def test_configured_ids_include_extras_and_controls(tmp_path: Path) -> None:
    """Catalog targets come from yaml plus evaluation/control extras."""
    (tmp_path / "duckflow.yaml").write_text(
        "llm:\n  available_models:\n"
        "  - {name: A, provider: openrouter, model: x/y}\n"
        "  - {name: B, provider: cloudflare, model: '@cf/z'}\n",
        encoding="utf-8",
    )
    ids = configured_openrouter_ids(tmp_path)
    assert "x/y" in ids
    assert "@cf/z" not in ids
    assert "z-ai/glm-4.5-air:free" in ids
    assert "inference-net/schematron-v2-small" in ids
    for eval_id in (
        "z-ai/glm-4.5-air",
        "minimax/minimax-m2.1",
        "deepseek/deepseek-v4.1-flash",
    ):
        assert eval_id in ids
    assert len(ids) == len(set(ids))


def _tool_call(call_id: str, name: str, args: str) -> SimpleNamespace:
    """Build a fake tool-call object."""
    return SimpleNamespace(
        id=call_id, function=SimpleNamespace(name=name, arguments=args)
    )


def _response(message: SimpleNamespace) -> SimpleNamespace:
    """Wrap a fake message in a completion-shaped object."""
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_extract_single_and_multiple_calls() -> None:
    """Names, arguments, and IDs are recorded per call."""
    message = SimpleNamespace(
        content=None,
        tool_calls=[
            _tool_call("c1", "probe_echo", '{"message": "hi"}'),
            _tool_call("c2", "probe_echo", '{"message": "yo"}'),
        ],
    )
    calls = extract_tool_calls(_response(message))
    assert [c["id"] for c in calls] == ["c1", "c2"]
    assert calls[0]["arguments"] == {"message": "hi"}


def test_extract_keeps_raw_unparseable_arguments() -> None:
    """Broken argument JSON is kept raw instead of crashing."""
    message = SimpleNamespace(
        content=None, tool_calls=[_tool_call("c1", "probe_echo", "{oops")]
    )
    calls = extract_tool_calls(_response(message))
    assert calls[0]["arguments"] == {"_raw": "{oops"}


def test_extract_empty_for_plain_text() -> None:
    """A refusal/avoidance without calls is an empty list, not an error."""
    assert extract_tool_calls(_response(SimpleNamespace(content="hello"))) == []
    assert extract_tool_calls(SimpleNamespace()) == []


def test_build_tool_result_messages_preserves_ids() -> None:
    """Reply re-sends the assistant message plus one tool message per ID."""
    message = SimpleNamespace(
        content=None, tool_calls=[_tool_call("c1", "probe_echo", '{"message": "hi"}')]
    )
    calls = extract_tool_calls(_response(message))
    messages = build_tool_result_messages(message, calls)
    assert messages[0]["role"] == "assistant"
    assert messages[0]["tool_calls"][0]["id"] == "c1"
    assert messages[1] == {
        "role": "tool",
        "tool_call_id": "c1",
        "content": '{"echo": "hi"}',
    }


def _fake_client(first: SimpleNamespace, second: SimpleNamespace | None = None):
    """Build a fake chat client returning canned responses."""

    class _Completions:
        def __init__(self) -> None:
            self.calls = 0

        async def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                assert kwargs.get("tools"), "first call must send tools"
                return first
            assert second is not None
            sent = kwargs["messages"]
            assert sent[-2]["role"] == "assistant" and sent[-2]["tool_calls"]
            assert sent[-1]["role"] == "tool" and sent[-1]["tool_call_id"]
            return second

    return SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))


def test_probe_round_trip_ok() -> None:
    """Full round trip records calls and follow-up text."""
    first = _response(
        SimpleNamespace(
            content=None,
            tool_calls=[_tool_call("c1", "probe_echo", '{"message": "duckflow-probe-123"}')],
        )
    )
    second = _response(SimpleNamespace(content="Echoed it.", tool_calls=None))
    result = asyncio.run(
        run_probe("m", client_factory=lambda provider: _fake_client(first, second))
    )
    assert result["outcome"] == "round_trip_ok"
    assert result["calls"][0]["arguments"] == {"message": "duckflow-probe-123"}
    assert result["follow_up"] == "Echoed it."


def test_probe_no_call_is_finding_not_error() -> None:
    """A model that never calls is recorded as no_call."""
    first = _response(SimpleNamespace(content="I will not.", tool_calls=None))
    result = asyncio.run(
        run_probe("m", client_factory=lambda provider: _fake_client(first))
    )
    assert result["outcome"] == "no_call"
    assert result["calls"] == []
    assert result["follow_up"] == "I will not."


def test_probe_api_failure_is_error_not_nonsupport() -> None:
    """Transport failures must not be classified as model non-support."""

    class _Fail:
        async def create(self, **kwargs):
            raise ConnectionError("boom")

    client = SimpleNamespace(chat=SimpleNamespace(completions=_Fail()))
    result = asyncio.run(
        run_probe("m", client_factory=lambda provider: client)
    )
    assert result["outcome"] == "error"
    assert "boom" in result["error"]


def test_probe_factory_rejects_unknown_provider() -> None:
    """Only the wired provider is supported for now."""
    with pytest.raises(ValueError):
        __import__("evals.tool_probe.probe", fromlist=["default_client_factory"]).default_client_factory(
            "groq"
        )
