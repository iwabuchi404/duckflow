import subprocess
import logging
import asyncio
from typing import Tuple

logger = logging.getLogger(__name__)

class ShellTool:
    """
    Tool for executing shell commands safely.
    """
    
    @staticmethod
    async def run_command(command: str) -> str:
        """
        Execute a shell command.
        
        NOTE: For complex commands, pipes, or multi-line scripts, 
        provide the command in a Sym-Ops content block (<<< >>>).
        
        Args:
            command: The full command line to execute.
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
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return f"Error: Command timed out after 30 seconds: {command}"
            
            output = ""
            if stdout:
                output += stdout.decode('utf-8', errors='replace')
            if stderr:
                output += f"\nstderr:\n{stderr.decode('utf-8', errors='replace')}"
                
            return output.strip()
            
        except Exception as e:
            error_msg = f"Error executing command '{command}': {str(e)}"
            logger.error(error_msg)
            return error_msg
