import subprocess
import logging
import asyncio
from typing import Tuple

from companion.config.config_loader import config
from companion.tools.results import ToolResult

logger = logging.getLogger(__name__)

class ShellTool:
    """
    Tool for executing shell commands safely.
    """
    
    @staticmethod
    async def run_command(command: str) -> str | ToolResult:
        """
        Execute a shell command.
        ⚑ BEFORE CALLING: set ::s0.3 or lower for destructive commands (rm, drop, reset).
        Returns command output (stdout/stderr).
        """
        logger.info(f"Executing shell command: {command}")
        
        try:
            # Use asyncio.create_subprocess_shell for non-blocking execution
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                timeout = config.get("tool.shell_timeout", 30)
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult.error(
                    "run_command", command, f"Command timed out after {timeout} seconds: {command}"
                )

            output = ""
            if stdout:
                output += stdout.decode('utf-8', errors='replace')
            if stderr:
                output += f"\nstderr:\n{stderr.decode('utf-8', errors='replace')}"

            return output.strip()

        except Exception as e:
            error_msg = f"Error executing command '{command}': {str(e)}"
            logger.error(error_msg)
            return ToolResult.error("run_command", command, error_msg)
