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
        Execute a shell command and return output.
        
        Args:
            command: The command line string to execute
            
        Returns:
            Command output or error message
        """
        logger.info(f"Executing shell command: {command}")
        
        try:
            # Use asyncio.create_subprocess_shell for non-blocking execution
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
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
