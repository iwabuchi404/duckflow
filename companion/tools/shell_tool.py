import asyncio
import logging

from companion.config.config_loader import config
from companion.tools.file_ops import file_ops
from companion.tools.results import ToolResult

logger = logging.getLogger(__name__)


def _decode_output(data: bytes) -> str:
    """Decode subprocess output, tolerating mixed console encodings.

    Windows consoles often emit the system encoding (e.g. CP932) while the
    tool layer assumes UTF-8. Pure UTF-8 decoding turns Japanese text into
    mojibake, which models misdiagnose as encoding failures. Try UTF-8
    first, then the locale preferred encoding, always with replacement.

    Args:
        data: Raw stdout/stderr bytes.

    Returns:
        Decoded text.
    """
    import locale

    candidates = ["utf-8", locale.getpreferredencoding(False), "cp932"]
    seen: set[str] = set()
    for encoding in candidates:
        if not encoding or encoding.lower().replace("-", "") in seen:
            continue
        seen.add(encoding.lower().replace("-", ""))
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


class ShellTool:
    """
    Tool for executing shell commands safely.
    """

    @staticmethod
    async def run_command(command: str) -> str | ToolResult:
        """
        Execute a shell command in the agent workspace root.
        Commands already run inside the workspace: use workspace-relative
        paths directly (e.g. "pytest test_calc.py -v"). Do NOT cd anywhere —
        there is no /workspace directory; the workspace root IS the cwd.
        ⚑ BEFORE CALLING: set ::s0.3 or lower for destructive commands (rm, drop, reset).
        Returns command output (stdout/stderr).
        """
        logger.info(f"Executing shell command: {command}")

        try:
            # Use asyncio.create_subprocess_shell for non-blocking execution.
            # Always run inside the configured workspace root so that commands
            # (pytest, python, git, ...) see the same files as the file tools.
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(file_ops.workspace_root),
            )

            try:
                timeout = config.get("tool.shell_timeout", 30)
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult.error(
                    "run_command",
                    command,
                    f"Command timed out after {timeout} seconds: {command}",
                )

            output = ""
            if stdout:
                output += _decode_output(stdout)
            if stderr:
                output += f"\nstderr:\n{_decode_output(stderr)}"

            # Surface the exit code so the model can tell failures from
            # successes (e.g. pytest exit 5 = "no tests collected").
            # A header marker is prepended for nonzero exits so failures are
            # visible without reading to the end of long outputs. Control
            # flow is unchanged: plain string results are successful tool
            # executions regardless of the command's own exit code.
            if process.returncode != 0:
                output = f"[command exited with code {process.returncode}]\n" + output
            output += f"\nexit_code: {process.returncode}"

            return output.strip()

        except Exception as e:
            error_msg = f"Error executing command '{command}': {str(e)}"
            logger.error(error_msg)
            return ToolResult.error("run_command", command, error_msg)
