import json
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

from companion.state.agent_state import AgentState, Plan, Step, TaskStatus
from companion.base.llm_client import default_client, LLMClient

class PlanProposal(BaseModel):
    """Schema for LLM response when proposing a plan."""
    steps: List[Dict[str, str]] = Field(..., description="List of steps. Each step has 'title' and 'description'.")

class PlanTool:
    """
    Manages the high-level plan (Steps).
    """
    def __init__(self, state: AgentState, llm_client: LLMClient = default_client):
        self.state = state
        self.llm = llm_client

    async def propose_plan(self, goal: str) -> str:
        """
        Propose a new plan based on the goal.
        Uses LLM to break down the goal into steps.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        print(f"🦆 Planning: Analyzing goal '{goal}'...")
        logger.info(f"propose_plan called with goal: {goal}")
        
        prompt = f"""
        Goal: {goal}
        
        Please break this goal down into high-level implementation steps.
        Return a JSON object with a list of steps.
        Each step should have a 'title' and a 'description'.
        
        Example:
        {{
            "steps": [
                {{"title": "Setup Environment", "description": "Install dependencies"}},
                {{"title": "Implement Core", "description": "Write main logic"}}
            ]
        }}
        """
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            logger.info("Calling LLM for plan proposal...")
            # Call LLM to get steps
            proposal = await self.llm.chat(messages, response_model=PlanProposal)
            logger.info(f"LLM returned proposal with {len(proposal.steps)} steps")
            
            # Create Plan object
            new_plan = Plan(goal=goal)
            logger.info("Created new Plan object")
            
            for i, step_data in enumerate(proposal.steps):
                logger.info(f"Adding step {i+1}: {step_data.get('title', 'Untitled')}")
                new_plan.add_step(
                    title=step_data.get("title", "Untitled Step"),
                    description=step_data.get("description", "")
                )
            
            # Update State
            logger.info("Updating agent state with new plan")
            self.state.current_plan = new_plan
            
            result = f"Plan created with {len(new_plan.steps)} steps."
            logger.info(f"propose_plan completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in propose_plan: {e}", exc_info=True)
            return f"Failed to create plan: {e}"

    async def mark_step_complete(self) -> str:
        """Mark the current step as complete and advance to the next."""
        if not self.state.current_plan:
            return "No active plan."
        
        current_step = self.state.current_plan.get_current_step()
        if current_step:
            current_step.status = TaskStatus.COMPLETED
            self.state.current_plan.current_step_index += 1
            
            next_step = self.state.current_plan.get_current_step()
            if next_step:
                return f"Step '{current_step.title}' completed. Next step: '{next_step.title}'"
            else:
                self.state.current_plan.is_complete = True
                return f"Step '{current_step.title}' completed. All steps finished! 🎉"
        
        return "No current step."
