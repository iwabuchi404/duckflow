"""Tests for concrete edit-failure recovery guidance (施策2).

MiniMaxの multi-file-rename 失敗（本文欠落の反復・SEARCH不一致後の
立て直し失敗）を受け、エラーメッセージと Correction Guide が
「次に何をどう出すか」まで具体的に示すことを保証する。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from companion.core_action_results import (  # noqa: E402
    build_action_exception_syntax_error,
)
from companion.prompts.builder import PromptBuilder  # noqa: E402
from companion.state.agent_state import Action  # noqa: E402
from companion.tools.file_ops import FileOps  # noqa: E402
from companion.tools.results import ToolResult, ToolStatus  # noqa: E402


@pytest.fixture
def file_ops(tmp_path: Path) -> FileOps:
    """Return FileOps rooted at tmp_path."""
    return FileOps(str(tmp_path))


def _error_text(result: str | ToolResult) -> str:
    """Extract message text from an edit_file result."""
    assert isinstance(result, ToolResult)
    assert result.status == ToolStatus.ERROR
    return result.content


@pytest.mark.asyncio
async def test_empty_body_error_shows_next_steps(
    file_ops: FileOps, tmp_path: Path
) -> None:
    """本文なし編集は read_file→再送の手順と形式例を示す。"""
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    result = await file_ops.edit_file("a.py", content="")
    text = _error_text(result)
    assert "::read_file @a.py" in text
    assert "SEARCH" in text
    assert "Do not resend" in text


@pytest.mark.asyncio
async def test_find_mismatch_error_shows_next_steps(
    file_ops: FileOps, tmp_path: Path
) -> None:
    """SEARCH不一致は再読取→逐語コピー→同一文の再送禁止を示す。"""
    (tmp_path / "b.py").write_text("value = 1\n", encoding="utf-8")
    result = await file_ops.edit_file(
        "b.py", find="value = 999", replace="value = 2"
    )
    text = _error_text(result)
    assert "::read_file @b.py" in text
    assert "SEARCH" in text
    assert "Do not resend the same SEARCH text unchanged" in text


def test_exception_hint_uses_search_wording() -> None:
    """例外経路の Correction Hint も旧find:表現を使わない。"""
    action = Action(name="edit_file", parameters={"path": "c.py"})
    info = build_action_exception_syntax_error(
        action, ValueError("find_not_matched")
    )
    assert info is not None
    assert info.error_type == "edit_find_mismatch"
    assert "SEARCH" in info.correction_hint
    assert "into find:" not in info.correction_hint
    assert "Do not resend the identical SEARCH text unchanged" in (
        info.correction_hint
    )


def test_builder_example_has_no_repeat_step() -> None:
    """Correction Guide の例示は失敗文の再送禁止まで含む。"""
    example: str = PromptBuilder._CORRECTION_EXAMPLES["edit_find_mismatch"]
    assert "::read_file" in example
    assert "SEARCH" in example
    assert "do NOT resend the failed SEARCH text unchanged" in example
