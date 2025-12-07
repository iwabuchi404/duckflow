import logging
from typing import List, Dict, Any
from companion.state.agent_state import AgentState, Task, TaskStatus

logger = logging.getLogger(__name__)

class ReplanRequiredError(Exception):
    """Exception raised when a task requires dynamic planning (Yield)."""
    def __init__(self, task: Task):
        self.task = task
        super().__init__(f"Task '{task.title}' requires dynamic planning.")

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
        yielded = False
        yield_reason = ""
        
        self.execution_log.clear()
        
        for i, task in enumerate(tasks):
            # Skip if already completed (re-entrance check)
            if task.status == TaskStatus.COMPLETED:
                completed += 1
                continue
                
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
                
            except ReplanRequiredError as e:
                # YIELD: Stop execution and return control to LLM
                task.status = TaskStatus.PENDING # Reset status so it can be replanned
                yielded = True
                yield_reason = f"Yielded at task '{task.title}': Dynamic planning required."
                print(f"   ⚠️  Yielding: {yield_reason}")
                logger.info(yield_reason)
                break
                
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
                
                # Stop on failure? For now, yes, to allow replanning
                break
        
        # Generate summary
        summary = {
            "total": total_tasks,
            "completed": completed,
            "failed": failed,
            "yielded": yielded,
            "yield_reason": yield_reason,
            "success_rate": completed / total_tasks if total_tasks > 0 else 0,
            "execution_log": self.execution_log
        }
        
        logger.info(f"Task execution finished: {completed}/{total_tasks} completed")
        
        return summary
    
    async def _execute_single_task(self, task: Task) -> Any:
        """
        Execute a single task.
        Priority:
        1. Explicit Action (Fast Path)
        2. Heuristics (Legacy)
        3. Yield (Dynamic)
        """
        # 1. Explicit Action (Fast Path)
        if task.action:
            if task.action.name in self.tools:
                tool_func = self.tools[task.action.name]
                print(f"   🚀 Fast Path: Executing tool '{task.action.name}'")
                
                # Handle async tools
                import asyncio
                if asyncio.iscoroutinefunction(tool_func):
                    return await tool_func(**task.action.parameters)
                else:
                    return tool_func(**task.action.parameters)
            else:
                raise ValueError(f"Unknown tool in action: {task.action.name}")
        
        # 2. Heuristics (Legacy Fallback)
        if task.command:
            return await self._execute_command(task.command)
        
        if task.file_path:
            return await self._execute_file_operation(task)
            
        # 3. Yield (Dynamic Planning Required)
        # If no explicit action and no obvious heuristic, we must yield to the LLM.
        # This allows the LLM to see the state after previous tasks and decide what to do.
        raise ReplanRequiredError(task)
    
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
        yielded = summary.get("yielded", False)
        rate = summary["success_rate"] * 100
        
        lines = [
            f"\n{'='*60}",
            f"📊 Task Execution Summary",
            f"{'='*60}",
            f"Total Tasks: {total}",
            f"✅ Completed: {completed}",
            f"❌ Failed: {failed}",
        ]
        
        if yielded:
             lines.append(f"⚠️  Yielded: {summary.get('yield_reason')}")
             lines.append(f"   (Returning control to agent for dynamic planning)")
        
        lines.append(f"Success Rate: {rate:.1f}%")
        lines.append(f"{'='*60}")
        
        return "\n".join(lines)
