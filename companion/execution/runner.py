import asyncio
import sys
from pathlib import Path

from companion.tools.shell_tool import ShellTool

from .summary import summarize_result


class CodeRunner:
    """Run code execution tasks and return concise user-facing summaries."""

    async def run_command(self, command: str) -> str:
        """Execute a shell command through the project shell tool.

        Args:
            command: Shell command text to execute.

        Returns:
            Combined stdout/stderr text returned by ShellTool.
        """
        return await ShellTool.run_command(command)

    async def run_python_file(self, file_path: str) -> str:
        """Execute a Python file directly and summarize the result.

        Args:
            file_path: Path to the Python file to execute.

        Returns:
            A concise execution summary generated from stdout, stderr, and exit code.
        """
        target = Path(file_path)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-X",
            "utf8",
            str(target),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return "❌ TimeoutError: Python execution timed out after 30 seconds"

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        return summarize_result(stdout, stderr, process.returncode or 0)
