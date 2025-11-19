import asyncio
import logging
import json
from typing import Dict, Any, Callable, List

from companion.state.agent_state import AgentState, ActionList, Action, AgentPhase
from companion.base.llm_client import default_client, LLMClient
from companion.prompts.system import get_system_prompt
from companion.tools.file_ops import file_ops
from companion.tools.plan_tool import PlanTool
from companion.tools.task_tool import TaskTool
from companion.tools.approval import ApprovalTool

logger = logging.getLogger(__name__)

class DuckAgent:
    """
    Duckflow v4 Main Agent.
    Manages the Think-Decide-Execute loop.
    """
    def __init__(self, llm_client: LLMClient = default_client):
        self.llm = llm_client
        self.state = AgentState()
        self.tools: Dict[str, Callable] = {}
        self.running = False
        
        # Initialize Tools
        self.plan_tool = PlanTool(self.state, self.llm)
        self.task_tool = TaskTool(self.state, self.llm)
        self.approval_tool = ApprovalTool(self.state)
        
        # Register basic actions
        self.register_tool("response", self.action_response)
        self.register_tool("exit", self.action_exit)
        self.register_tool("duck_call", self.approval_tool.duck_call)
        
        # Register File Ops
        self.register_tool("read_file", file_ops.read_file)
        self.register_tool("write_file", file_ops.write_file)
        self.register_tool("list_files", file_ops.list_files)
        self.register_tool("mkdir", file_ops.mkdir)

        # Register Planning Tools
        self.register_tool("propose_plan", self.plan_tool.propose_plan)
        self.register_tool("mark_step_complete", self.plan_tool.mark_step_complete)
        self.register_tool("generate_tasks", self.task_tool.generate_tasks)
        self.register_tool("mark_task_complete", self.task_tool.mark_task_complete)

    def register_tool(self, name: str, func: Callable):
        """Register a tool function available to the agent."""
        self.tools[name] = func

    def get_tool_descriptions(self) -> str:
        """Generate descriptions for all registered tools."""
        descriptions = []
        for name, func in self.tools.items():
            doc = func.__doc__ or "No description."
            descriptions.append(f"- {name}: {doc.strip()}")
        return "\n".join(descriptions)

    async def run(self):
        """Main execution loop."""
        self.running = True
        print("🦆 Duckflow v4 Started. Type 'exit' to quit.")
        
        while self.running:
            try:
                # 1. Get User Input if needed
                if self.state.phase == AgentPhase.IDLE or self.state.phase == AgentPhase.AWAITING_USER:
                    user_input = await asyncio.to_thread(input, "You: ")
                    if not user_input:
                        continue
                    
                    self.state.add_message("user", user_input)
                    self.state.phase = AgentPhase.THINKING

                # 2. Think & Decide (LLM Call)
                if self.state.phase == AgentPhase.THINKING:
                    print("🦆 Thinking...")
                    system_prompt = get_system_prompt(
                        tool_descriptions=self.get_tool_descriptions(),
                        state_context=self.state.to_prompt_context()
                    )
                    
                    messages = [
                        {"role": "system", "content": system_prompt}
                    ] + self.state.conversation_history

                    # Call LLM
                    action_list = await self.llm.chat(messages, response_model=ActionList)
                    
                    # Log reasoning
                    print(f"🦆 Thought: {action_list.reasoning}")
                    self.state.add_message("assistant", json.dumps(action_list.model_dump(), ensure_ascii=False))
                    
                    # 3. Execute
                    self.state.phase = AgentPhase.EXECUTING
                    await self.execute_actions(action_list)
                    
                    # Update Vitals
                    self.state.update_vitals()
                    self._check_pacemaker()
                    
                    # If no further actions needed, go back to waiting
                    if self.state.phase == AgentPhase.EXECUTING:
                         self.state.phase = AgentPhase.AWAITING_USER

            except KeyboardInterrupt:
                print("\n🦆 Interrupted by user.")
                break
            except Exception as e:
                logger.error(f"Critical Error: {e}", exc_info=True)
                print(f"🦆 Error: {e}")
                self.state.phase = AgentPhase.AWAITING_USER

    async def execute_actions(self, action_list: ActionList):
        """Dispatch and execute a list of actions."""
        for action in action_list.actions:
            print(f"🦆 Action: {action.name} ({action.thought})")
            
            if action.name in self.tools:
                try:
                    # Execute tool
                    func = self.tools[action.name]
                    # Simple argument unpacking, can be improved
                    result = await func(**action.parameters)
                    
                    # Record result
                    self.state.last_action_result = f"Action '{action.name}' succeeded: {result}"
                    
                except Exception as e:
                    error_msg = f"Action '{action.name}' failed: {str(e)}"
                    logger.error(error_msg)
                    self.state.last_action_result = error_msg
            else:
                msg = f"Unknown tool: {action.name}"
                logger.warning(msg)
                self.state.last_action_result = msg

    def _check_pacemaker(self):
        """Pacemaker: Check vitals and intervene if necessary."""
        vitals = self.state.vitals
        if vitals.stamina < 0.2:
            print("\n⚠️  PACEMAKER ALERT: Stamina is low!")
            print("   (The duck is tired. Suggesting a break.)")
            self.state.add_message("system", "Your stamina is low (below 0.2). You should consider using 'duck_call' to ask the user for a break or guidance.")
        
        if vitals.focus < 0.2:
            print("\n⚠️  PACEMAKER ALERT: Focus is low!")
            self.state.add_message("system", "Your focus is low. You might be stuck. Consider reviewing the plan or asking for help.")

    # --- Basic Actions ---

    async def action_response(self, message: str):
        """Send a message to the user."""
        print(f"🦆 Duck: {message}")
        return "Message sent."

    async def action_exit(self):
        """Exit the application."""
        print("🦆 Goodbye!")
        self.running = False
        return "Exiting."
