import logging
from typing import List, Dict, Any
from companion.state.agent_state import AgentState, Task, TaskStatus

logger = logging.getLogger(__name__)

class TaskExecutor:
    """
    Task Execution Worker for Duckflow v4.
    Executes a list of tasks sequentially and records results.
    """
    
    def __init__(self, state: AgentState, tools: Dict[str, Any]):
        self.state = state
        self.tools = tools
        self.execution_log: List[Dict[str, Any]] = []
    
    async def execute_task_list(self, tasks: List[Task]) -> Dict[str, Any]:
        """
        Execute a list of tasks sequentially.
        
        Args:
            tasks: List of Task objects to execute
            
        Returns:
            Summary dictionary with execution results
        """
        logger.info(f"Starting execution of {len(tasks)} tasks")
        
        total_tasks = len(tasks)
        completed = 0
        failed = 0
        
        self.execution_log.clear()
        
        for i, task in enumerate(tasks):
            logger.info(f"Executing task {i+1}/{total_tasks}: {task.title}")
            print(f"\n📋 Task {i+1}/{total_tasks}: {task.title}")
            
            task.status = TaskStatus.IN_PROGRESS
            
            try:
                # Execute the task
                result = await self._execute_single_task(task)
                
                # Mark as completed
                task.status = TaskStatus.COMPLETED
                task.result = str(result)
                completed += 1
                
                # Log success
                self.execution_log.append({
                    "task_index": i,
                    "task_title": task.title,
                    "status": "completed",
                    "result": str(result)
                })
                
                print(f"   ✅ Completed: {result}")
                
            except Exception as e:
                # Mark as failed
                task.status = TaskStatus.FAILED
                task.result = f"Error: {str(e)}"
                failed += 1
                
                # Log failure
                self.execution_log.append({
                    "task_index": i,
                    "task_title": task.title,
                    "status": "failed",
                    "error": str(e)
                })
                
                print(f"   ❌ Failed: {str(e)}")
                logger.error(f"Task failed: {task.title} - {str(e)}")
                
                # Decide whether to continue or stop
                # For now, we'll continue with remaining tasks
                continue
        
        # Generate summary
        summary = {
            "total": total_tasks,
            "completed": completed,
            "failed": failed,
            "success_rate": completed / total_tasks if total_tasks > 0 else 0,
            "execution_log": self.execution_log
        }
        
        logger.info(f"Task execution completed: {completed}/{total_tasks} succeeded, {failed} failed")
        
        return summary
    
    async def _execute_single_task(self, task: Task) -> Any:
        """
        Execute a single task by interpreting its properties.
        
        This is a simplified version that uses task.command or task.file_path
        to determine what action to take.
        """
        # Strategy 1: If task has a specific command
        if task.command:
            return await self._execute_command(task.command)
        
        # Strategy 2: If task has a file_path (file operation)
        if task.file_path:
            return await self._execute_file_operation(task)
        
        # Strategy 3: Parse task description for actions
        # This is a fallback - in a real implementation, 
        # the Task object should have clear action specifications
        return f"Task '{task.title}' executed (mock)"
    
    async def _execute_command(self, command: str) -> str:
        """Execute a command-type task."""
        # For now, this is a placeholder
        # In a full implementation, this would use shell execution tools
        logger.info(f"Executing command: {command}")
        return f"Command executed: {command}"
    
    async def _execute_file_operation(self, task: Task) -> str:
        """Execute a file operation task."""
        # Determine operation from task description
        desc_lower = task.description.lower()
        
        if "create" in desc_lower or "write" in desc_lower:
            # Use write_file tool
            if "write_file" in self.tools:
                tool = self.tools["write_file"]
                result = await tool(path=task.file_path, content=task.description)
                return result
        
        elif "read" in desc_lower:
            # Use read_file tool
            if "read_file" in self.tools:
                tool = self.tools["read_file"]
                result = await tool(path=task.file_path)
                return f"Read {len(result)} characters"
        
        # Default
        return f"File operation on {task.file_path}"
    
    def get_summary_text(self, summary: Dict[str, Any]) -> str:
        """
        Generate a human-readable summary text.
        """
        total = summary["total"]
        completed = summary["completed"]
        failed = summary["failed"]
        rate = summary["success_rate"] * 100
        
        lines = [
            f"\n{'='*60}",
            f"📊 Task Execution Summary",
            f"{'='*60}",
            f"Total Tasks: {total}",
            f"✅ Completed: {completed}",
            f"❌ Failed: {failed}",
            f"Success Rate: {rate:.1f}%",
            f"{'='*60}"
        ]
        
        return "\n".join(lines)
