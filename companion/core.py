import asyncio
import logging
import json
from typing import Dict, Any, Callable, List

from companion.state.agent_state import AgentState, ActionList, Action, AgentPhase, TaskStatus
from companion.base.llm_client import default_client, LLMClient
from companion.prompts.system import get_system_prompt
from companion.tools.file_ops import file_ops
from companion.tools.plan_tool import PlanTool
from companion.tools.task_tool import TaskTool
from companion.tools.approval import ApprovalTool
from companion.execution.task_executor import TaskExecutor
from companion.execution.result_summarizer import ResultSummarizer

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
        self.task_executor = TaskExecutor(self.state, self.tools)
        self.result_summarizer = ResultSummarizer(self.llm)
        
        # Register basic actions
        self.register_tool("response", self.action_response)
        self.register_tool("exit", self.action_exit)
        self.register_tool("duck_call", self.approval_tool.duck_call)
        
        # Register File Ops
        self.register_tool("read_file", file_ops.read_file)
        self.register_tool("write_file", file_ops.write_file)
        self.register_tool("list_files", file_ops.list_files)
        self.register_tool("mkdir", file_ops.mkdir)
        self.register_tool("replace_in_file", file_ops.replace_in_file)
        self.register_tool("find_files", file_ops.find_files)
        self.register_tool("delete_file", file_ops.delete_file)

        # Register Planning Tools
        self.register_tool("propose_plan", self.plan_tool.propose_plan)
        self.register_tool("mark_step_complete", self.plan_tool.mark_step_complete)
        self.register_tool("generate_tasks", self.task_tool.generate_tasks)
        self.register_tool("mark_task_complete", self.task_tool.mark_task_complete)
        
        # Register Task Execution
        self.register_tool("execute_tasks", self.action_execute_tasks)

    def register_tool(self, name: str, func: Callable):
        """Register a tool function available to the agent."""
        self.tools[name] = func

    def get_tool_descriptions(self) -> str:
        """Generate descriptions for all registered tools."""
        import inspect
        descriptions = []
        
        for name, func in self.tools.items():
            doc = func.__doc__ or "No description."
            
            # Get function signature
            try:
                sig = inspect.signature(func)
                params = []
                for param_name, param in sig.parameters.items():
                    if param_name not in ['self', 'cls']:
                        # Get type annotation if available
                        param_type = param.annotation if param.annotation != inspect.Parameter.empty else "any"
                        param_str = f"{param_name}: {param_type}" if isinstance(param_type, type) else f"{param_name}"
                        params.append(param_str)
                
                param_list = ", ".join(params) if params else "no parameters"
                descriptions.append(f"- {name}({param_list}): {doc.strip()}")
            except:
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
                    
                    # Determine context mode based on current state
                    context_mode = self.state.get_context_mode()
                    
                    system_prompt = get_system_prompt(
                        tool_descriptions=self.get_tool_descriptions(),
                        state_context=self.state.to_prompt_context(),
                        mode=context_mode
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
                    
                    # Display Token Usage
                    stats = self.llm.usage_stats
                    print(f"   📊 Tokens: {stats['total_tokens']} (In: {stats['input_tokens']}, Out: {stats['output_tokens']})")
                    
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
                    
                    # Check if function is async
                    if asyncio.iscoroutinefunction(func):
                        result = await func(**action.parameters)
                    else:
                        result = func(**action.parameters)
                    
                    # Record result
                    self.state.last_action_result = f"Action '{action.name}' succeeded: {result}"
                    
                    # Auto-report result to user (except for 'response' action which already prints)
                    if action.name != "response" and result:
                        print(f"   ✅ Result: {result}")
                    
                except Exception as e:
                    error_msg = f"Action '{action.name}' failed: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    self.state.last_action_result = error_msg
                    print(f"   ❌ Error: {str(e)}")
            else:
                msg = f"Unknown tool: {action.name}"
                logger.warning(msg)
                self.state.last_action_result = msg
                print(f"   ⚠️  {msg}")

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

    async def action_execute_tasks(self) -> str:
        """
        Execute all tasks in the current step.
        This is a batch execution that runs multiple tasks sequentially.
        """
        if not self.state.current_plan:
            return "No active plan. Create a plan first with 'propose_plan'."
        
        current_step = self.state.current_plan.get_current_step()
        if not current_step:
            return "No active step in the plan."
        
        if not current_step.tasks:
            return f"No tasks found for step '{current_step.title}'. Generate tasks first with 'generate_tasks'."
        
        print(f"\n🚀 Executing {len(current_step.tasks)} tasks for step: '{current_step.title}'")
        
        # Execute tasks using TaskExecutor
        summary = await self.task_executor.execute_task_list(current_step.tasks)
        
        # Generate AI-powered summary
        try:
            ai_summary = await self.result_summarizer.summarize_execution(summary)
            print(ai_summary)
        except Exception as e:
            logger.error(f"Failed to generate AI summary: {e}")
            # Fallback to simple summary
            summary_text = self.task_executor.get_summary_text(summary)
            print(summary_text)
        
        # Update step status if all tasks completed
        if summary["failed"] == 0:
            current_step.status = TaskStatus.COMPLETED
            return f"All tasks completed successfully! Step '{current_step.title}' is now complete."
        else:
            return f"Task execution finished with {summary['failed']} failures. Please review and retry failed tasks."
