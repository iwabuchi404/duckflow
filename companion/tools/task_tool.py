import json
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from companion.state.agent_state import AgentState, Task, TaskStatus
from companion.base.llm_client import default_client, LLMClient

class TaskListProposal(BaseModel):
    """Schema for LLM response when proposing tasks."""
    tasks: List[Dict[str, Any]] = Field(..., description="List of tasks. Each task has 'title', 'description', and optional 'action'.")

from companion.ui.console import ui
from companion.state.agent_state import Action

class TaskTool:
    """
    Manages specific tasks within a Step.
    """
    def __init__(self, state: AgentState, llm_client: LLMClient = default_client):
        self.state = state
        self.llm = llm_client

    async def generate_tasks(self) -> str:
        """
        Generate tasks for the current step. NO PARAMETERS NEEDED - operates on the active step automatically.
        """
        if not self.state.current_plan:
            return "No active plan."
        
        current_step = self.state.current_plan.get_current_step()
        if not current_step:
            return "No active step."
        
        if current_step.tasks:
            return f"Step '{current_step.title}' already has {len(current_step.tasks)} tasks."

        ui.print_thinking(f"Planning: Generating tasks for step '{current_step.title}'...")

        prompt = f"""
        Current Goal: {self.state.current_plan.goal}
        Current Step: {current_step.title}
        Step Description: {current_step.description}
        
        Please break this step down into small, actionable tasks.
        Return a JSON object with a list of tasks.
        Each task MUST have a 'title' and 'description'.
        
        [IMPORTANT: Explicit Action Binding]
        If a task involves a simple, deterministic tool call (e.g., creating a file, running a specific command), you MUST provide an 'action' object.
        This allows the system to execute it automatically without asking you again.
        
        Action Schema: {{ "name": "tool_name", "parameters": {{ ... }} }}
        Available Tools for Actions: write_file, run_command, read_file
        
        Example:
        {{
            "tasks": [
                {{
                    "title": "Create main.py", 
                    "description": "Write basic script",
                    "action": {{
                        "name": "write_file",
                        "parameters": {{ "path": "main.py", "content": "print('hello')" }}
                    }}
                }},
                {{
                    "title": "Run tests", 
                    "description": "Verify implementation",
                    "action": {{
                        "name": "run_command",
                        "parameters": {{ "command": "pytest" }}
                    }}
                }}
            ]
        }}
        """
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            # Call LLM
            proposal = await self.llm.chat(messages, response_model=TaskListProposal)
            
            # Add tasks to step
            count = 0
            for task_data in proposal.tasks:
                task = current_step.add_task(
                    title=task_data.get("title", "Untitled Task"),
                    description=task_data.get("description", "")
                )
                
                # Hydrate Action if present
                action_data = task_data.get("action")
                if action_data:
                    try:
                        task.action = Action(**action_data)
                    except Exception as e:
                        print(f"Warning: Failed to parse action for task '{task.title}': {e}")
                
                count += 1
            
            return f"Generated {count} tasks for step '{current_step.title}'."
            
        except Exception as e:
            return f"Failed to generate tasks: {e}"

    async def mark_task_complete(self, task_index: int = 0) -> str:
        """Mark a specific task as complete."""
        if not self.state.current_plan:
            return "No active plan."
        
        current_step = self.state.current_plan.get_current_step()
        if not current_step:
            return "No active step."
            
        if 0 <= task_index < len(current_step.tasks):
            task = current_step.tasks[task_index]
            task.status = TaskStatus.COMPLETED
            return f"Task '{task.title}' completed."
        
        return "Invalid task index."
