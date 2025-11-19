import json
from typing import List, Dict
from pydantic import BaseModel, Field

from companion.state.agent_state import AgentState, Task, TaskStatus
from companion.base.llm_client import default_client, LLMClient

class TaskListProposal(BaseModel):
    """Schema for LLM response when proposing tasks."""
    tasks: List[Dict[str, str]] = Field(..., description="List of tasks. Each task has 'title' and 'description'.")

class TaskTool:
    """
    Manages specific tasks within a Step.
    """
    def __init__(self, state: AgentState, llm_client: LLMClient = default_client):
        self.state = state
        self.llm = llm_client

    async def generate_tasks(self) -> str:
        """
        Generate tasks for the current step.
        """
        if not self.state.current_plan:
            return "No active plan."
        
        current_step = self.state.current_plan.get_current_step()
        if not current_step:
            return "No active step."
        
        if current_step.tasks:
            return f"Step '{current_step.title}' already has {len(current_step.tasks)} tasks."

        print(f"🦆 Planning: Generating tasks for step '{current_step.title}'...")

        prompt = f"""
        Current Goal: {self.state.current_plan.goal}
        Current Step: {current_step.title}
        Step Description: {current_step.description}
        
        Please break this step down into small, actionable tasks.
        Return a JSON object with a list of tasks.
        Each task should have a 'title' and a 'description'.
        
        Example:
        {{
            "tasks": [
                {{"title": "Create file.py", "description": "Write initial code"}},
                {{"title": "Run tests", "description": "Verify implementation"}}
            ]
        }}
        """
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            # Call LLM
            proposal = await self.llm.chat(messages, response_model=TaskListProposal)
            
            # Add tasks to step
            for task_data in proposal.tasks:
                current_step.add_task(
                    title=task_data.get("title", "Untitled Task"),
                    description=task_data.get("description", "")
                )
            
            return f"Generated {len(current_step.tasks)} tasks for step '{current_step.title}'."
            
        except Exception as e:
            return f"Failed to generate tasks: {e}"

    async def mark_task_complete(self, task_index: int) -> str:
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
