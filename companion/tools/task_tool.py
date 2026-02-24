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
        Generate tasks for the current step. NO PARAMETERS NEEDED.
        アクティブなステップの説明をもとに、Sub-LLMがタスクリストを自動生成する。

        Returns:
            生成されたタスクのリスト（各タスクに title, description, action を含む dict）、
            またはエラーメッセージ
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
        # Sym-Ops v3.2: Task Generation Context
        Current Goal: {self.state.current_plan.goal}
        Current Step: {current_step.title}
        Step Description: {current_step.description}
        
        Please break this step down into small, actionable tasks.
        Use Sym-Ops v3.2 thinking: evaluate confidence (::c) and safety (::s) for each task.
        
        Return a JSON object with a list of tasks.
        Each task MUST have a 'title' and 'description'.
        
        [Explicit Action Binding]
        If a task involves a deterministic tool call, provide an 'action' object.
        Available Tools: write_file, run_command, read_file
        
        Action Schema: {{ "name": "tool_name", "parameters": {{ ... }} }}
        
        Example:
        {{
            "tasks": [
                {{
                    "title": "Setup main module", 
                    "description": "Create entrance script",
                    "action": {{
                        "name": "write_file",
                        "parameters": {{ "path": "main.py", "content": "print('init')" }}
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
            tasks_formatted = []
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
                
                tasks_formatted.append({
                    "title": task.title,
                    "description": task.description,
                    "action": action_data
                })
            
            return tasks_formatted
            
        except Exception as e:
            return f"Failed to generate tasks: {e}"

    async def mark_task_complete(self, task_index: int = 0) -> str:
        """
        Mark a specific task as complete.

        Args:
            task_index: 完了にするタスクの0始まりインデックス（デフォルト: 0）

        Returns:
            成功時: "Task '{title}' completed."
            プラン/ステップなし: エラーメッセージ
            範囲外のインデックス: "Invalid task index."
        """
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
