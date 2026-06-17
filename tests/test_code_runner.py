import os
import sys

import pytest

sys.path.append(os.getcwd())

from companion.execution.runner import CodeRunner


@pytest.mark.asyncio
async def test_run_python_file_summarizes_success_with_spaced_path(tmp_path) -> None:
    """
    run_python_file should execute a file path containing spaces without shell quoting issues.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None.
    """
    script = tmp_path / "script with spaces.py"
    script.write_text("print('hello')\n", encoding="utf-8")

    result = await CodeRunner().run_python_file(str(script))

    assert "実行結果" in result
    assert "hello" in result


@pytest.mark.asyncio
async def test_run_python_file_summarizes_failure(tmp_path) -> None:
    """
    run_python_file should summarize Python stderr when the process fails.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None.
    """
    script = tmp_path / "failing_script.py"
    script.write_text("raise ValueError('boom')\n", encoding="utf-8")

    result = await CodeRunner().run_python_file(str(script))

    assert "ValueError" in result
    assert "boom" in result
