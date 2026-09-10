"""Tests for GPT-round-2 fixes: summary body notes, bare param recovery."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from companion.core_action_invocation import invoke_tool  # noqa: E402
from companion.core_action_results import build_action_summary  # noqa: E402
from companion.state.agent_state import Action, ActionList  # noqa: E402
from companion.tools.shell_tool import _decode_output  # noqa: E402
from companion.utils.sym_ops import extract_bare_key_params  # noqa: E402


def test_summary_notes_body_size() -> None:
    """Write summaries record that a body was passed (with size)."""
    action_list = ActionList(
        reasoning="test",
        actions=[
            Action(
                name="write_file",
                parameters={"path": "f.py", "content": "x" * 373},
            )
        ],
    )

    summary = build_action_summary(action_list)

    assert ":: write_file @f.py" in summary
    assert "373" in summary
    assert "送信済み" in summary


def test_summary_note_on_separate_line() -> None:
    """The body note must not share the action line (copy-paste safety)."""
    action_list = ActionList(
        reasoning="test",
        actions=[
            Action(
                name="write_file",
                parameters={"path": "f.py", "content": "x" * 10},
            )
        ],
    )

    lines = build_action_summary(action_list).split("\n")

    assert lines[0] == ":: write_file @f.py"
    assert len(lines) == 2
    assert lines[1].startswith("履歴注記")


def test_summary_without_body_unchanged() -> None:
    """Read-only actions keep the plain summary form."""
    action_list = ActionList(
        reasoning="test",
        actions=[Action(name="read_file", parameters={"path": "a.py"})],
    )

    assert build_action_summary(action_list) == ":: read_file @a.py"


def test_bare_key_params_full_yaml_block() -> None:
    """A ---less key block with a literal body parses correctly."""
    text = (
        "path: utils/helpers.py\n"
        "name: helo\n"
        "body: |\n"
        "  def greet(): ...\n"
    )

    params, remaining = extract_bare_key_params(
        text, valid_keys={"path", "name", "body"}
    )

    assert params["path"] == "utils/helpers.py"
    assert params["name"] == "helo"
    assert "def greet" in params["body"]
    assert remaining == ""


def test_bare_key_params_rejects_unknown_keys() -> None:
    """Keys outside the tool signature are not extracted."""
    params, remaining = extract_bare_key_params(
        "Summary: fixed the bug\nDetails: all good\n", valid_keys={"path"}
    )

    assert params == {}
    assert "Summary" in remaining


def test_bare_key_params_ignores_plain_prose() -> None:
    """Prose without leading key lines passes through."""
    text = "Just some notes\nabout the task."

    params, remaining = extract_bare_key_params(text, valid_keys={"path"})

    assert params == {}
    assert remaining == text


@pytest.mark.asyncio
async def test_invoke_tool_recovers_body_from_block() -> None:
    """A replace_function-style block fills missing params by signature."""

    async def fake_replace(path: str, name: str, body: str) -> str:
        """Fake tool with path/name/body contract."""
        return f"replaced {name} in {path} ({len(body)} chars)"

    block = "path: a.py\nname: old_fn\nbody: |\n  def new_fn(): ...\n"
    result, dropped = await invoke_tool(
        fake_replace, {"content": block}, tool_name="fake_replace"
    )

    assert "replaced old_fn in a.py" in result
    assert "content" not in dropped
    assert "body" not in dropped


@pytest.mark.asyncio
async def test_invoke_tool_leaves_valid_content_alone() -> None:
    """Tools accepting 'content' never trigger recovery."""

    async def fake_write(path: str, content: str) -> str:
        """Fake tool accepting content directly."""
        return f"wrote {len(content)} chars"

    result, dropped = await invoke_tool(
        fake_write, {"path": "a.py", "content": "title: hello\nbody text"}
    )

    assert result == "wrote 22 chars"
    assert dropped == set()


def test_decode_output_handles_cp932() -> None:
    """CP932 bytes decode to readable Japanese, not mojibake."""
    data = "テスト失敗".encode("cp932")

    assert _decode_output(data) == "テスト失敗"


def test_decode_output_keeps_utf8() -> None:
    """UTF-8 output still decodes normally."""
    assert _decode_output("hello テスト".encode("utf-8")) == "hello テスト"
