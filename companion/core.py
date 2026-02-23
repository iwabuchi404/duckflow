import asyncio
import logging
import json
from typing import Dict, Any, Callable, List

from companion.state.agent_state import AgentState, ActionList, Action, AgentPhase, TaskStatus, AgentMode
from companion.base.llm_client import default_client, LLMClient
from companion.prompts.system import get_system_prompt
from companion.tools.file_ops import file_ops
from companion.tools.plan_tool import PlanTool
from companion.tools.task_tool import TaskTool
from companion.tools.approval import ApprovalTool
from companion.tools.memory_tool import MemoryTool
from companion.execution.task_executor import TaskExecutor
from companion.execution.result_summarizer import ResultSummarizer
from companion.modules.pacemaker import DuckPacemaker
from companion.modules.memory import MemoryManager
from companion.ui import ui

logger = logging.getLogger(__name__)

from companion.modules.command_handler import CommandHandler
from companion.modules.session_manager import SessionManager
from companion.tools.shell_tool import ShellTool
from companion.tools import get_project_tree

class DuckAgent:
    """
    Duckflow v4 Main Agent.
    Manages the Think-Decide-Execute loop.
    """
    def __init__(
        self,
        llm_client: LLMClient = default_client,
        debug_context_mode: str = None,
        session_manager: 'SessionManager' = None,
        resume_state: 'AgentState' = None,
    ):
        """
        Args:
            llm_client: 使用するLLMクライアント
            debug_context_mode: デバッグ用コンテキスト出力モード（"console" | "file"）
            session_manager: セッション保存を担当するマネージャー（Noneなら保存しない）
            resume_state: 前回セッションから復元した AgentState（Noneなら新規）
        """
        self.state = resume_state if resume_state is not None else AgentState()
        self.session_manager = session_manager
        self.llm = llm_client
        self.tools: Dict[str, Callable] = {}
        self.running = False
        self.debug_context_mode = debug_context_mode
        self.command_handler = CommandHandler(self)
        
        # Initialize Tools
        self.plan_tool = PlanTool(self.state)
        self.task_tool = TaskTool(self.state, self.llm)
        self.approval_tool = ApprovalTool(self.state)
        self.task_executor = TaskExecutor(self.state, self.tools)
        self.result_summarizer = ResultSummarizer(self.llm)
        
        # Initialize Pacemaker
        self.pacemaker = DuckPacemaker(self.state)
        
        # Initialize Memory Manager
        self.memory_manager = MemoryManager(
            llm_client=self.llm,
            max_tokens=8000
        )
        
        # Register basic actions
        self.register_tool("response", self.action_response)
        self.register_tool("finish", self.action_finish)
        self.register_tool("exit", self.action_exit)
        self.register_tool("duck_call", self.approval_tool.duck_call)
        
        # Register File Ops
        self.register_tool("read_file", file_ops.read_file)
        self.register_tool("write_file", file_ops.write_file)
        self.register_tool("create_file", file_ops.write_file)  # Alias for Sym-Ops v2
        self.register_tool("list_directory", file_ops.list_files)
        self.register_tool("mkdir", file_ops.mkdir)
        self.register_tool("replace_in_file", file_ops.replace_in_file)
        self.register_tool("edit_file", file_ops.write_file)  # Alias - Changed to write_file (overwrite) as agent uses it for full content
        self.register_tool("find_files", file_ops.find_files)
        self.register_tool("delete_file", file_ops.delete_file)

        # Register Planning Tools
        self.register_tool("propose_plan", self.plan_tool.propose_plan)
        self.register_tool("mark_step_complete", self.plan_tool.mark_step_complete)
        self.register_tool("generate_tasks", self.task_tool.generate_tasks)
        self.register_tool("mark_task_complete", self.task_tool.mark_task_complete)
        
        # Register Task Execution
        self.register_tool("execute_tasks", self.action_execute_tasks)
        self.register_tool("run_command", self.action_run_command)

        # Register Memory Tools
        self.memory_tool = MemoryTool()
        self.register_tool("search_archives", self.memory_tool.search_archives)
        self.register_tool("recall", self.memory_tool.search_archives)  # Alias

        # Register Investigation Tools (Sym-Ops v3.1)
        self.register_tool("investigate", self.action_investigate)
        self.register_tool("submit_hypothesis", self.action_submit_hypothesis)
        self.register_tool("finish_investigation", self.action_finish_investigation)

        # Register execute_batch (Sym-Ops v3.1 Fast Path)
        self.register_tool("execute_batch", self.action_execute_batch)

        # Register Project Tree Tool
        self.register_tool("get_project_tree", get_project_tree)

    def register_tool(self, name: str, func: Callable):
        """Register a tool function available to the agent."""
        self.tools[name] = func
    
    async def switch_model(self, provider: str, model: str) -> bool:
        """
        Switch to a different LLM model and persist the change.
        
        Args:
            provider: Provider name (e.g., 'openai', 'groq', 'openrouter')
            model: Model name (e.g., 'gpt-4o', 'llama-3.3-70b-versatile')
            
        Returns:
            True if switch was successful, False otherwise
        """
        from companion.config.config_loader import config
        
        try:
            logger.info(f"🔄 Attempting to switch model to {provider}/{model}")
            
            # Test if the new model configuration is valid by reinitializing
            success = self.llm.reinitialize(provider=provider, model=model)
            
            if not success:
                logger.error("Failed to reinitialize LLM client")
                return False
            
            # Test the connection
            connection_ok = await self.llm.test_connection()
            if not connection_ok:
                logger.error("Connection test failed for new model")
                return False
            
            # Update components that depend on LLM
            logger.info("Updating dependent components...")
            
            # Update TaskTool
            self.task_tool.llm = self.llm
            
            # Update ResultSummarizer
            self.result_summarizer.llm = self.llm
            
            # Update MemoryManager
            self.memory_manager.llm_client = self.llm
            
            # Persist to config file
            logger.info("Persisting configuration to duckflow.yaml...")
            config.update_config("llm.provider", provider)
            config.update_config(f"llm.{provider}.model", model)
            
            logger.info(f"✅ Successfully switched to {provider}/{model}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error switching model: {e}")
            return False

    def get_tool_descriptions(self) -> str:
        """Generate tool descriptions for the system prompt."""
        descriptions = []
        for name, func in self.tools.items():
            # Get docstring
            doc = func.__doc__ or "No description available."
            doc = doc.strip().split("\n")[0]  # First line only
            
            # Get signature (simplified)
            import inspect
            sig = inspect.signature(func)
            
            descriptions.append(f"- {name}{sig}: {doc}")
        
        return "\n".join(descriptions)

    async def run(self):
        """Main execution loop."""
        self.running = True

        # 復元セッションのサイズが大きい場合はLLM要約で圧縮する
        if (
            self.session_manager is not None
            and len(self.state.conversation_history) > 0
            and self.memory_manager.should_prune(self.state.conversation_history)
        ):
            logger.info("Session restore: applying restore_with_summary...")
            self.state.conversation_history = await self.memory_manager.restore_with_summary(
                self.state.conversation_history
            )
            logger.info(
                f"Session restore complete: {len(self.state.conversation_history)} messages retained"
            )

        ui.print_welcome()
        
        # セッション復元時に過去の会話を表示（最新5回分）
        if self.state.conversation_history:
            history_to_show = self.state.conversation_history[-10:]  # 5ターン = User/AI ペアで10件程度
            if history_to_show:
                ui.print_info("\n📜 過去の会話履歴を復元します:")
                for msg in history_to_show:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    if role in ["user", "assistant"]:
                        ui.print_conversation_message(content, speaker=role)
                ui.print_separator()
        
        while self.running:
            try:
                # 1. Input Phase
                if self.state.phase == AgentPhase.AWAITING_USER:
                    # Resume from user input (handled by tools usually, but here for safety)
                    pass
                
                user_input = await ui.get_user_input()
                if not user_input.strip():
                    continue
                
                # Check for internal commands
                if self.command_handler.is_command(user_input):
                    await self.command_handler.execute(user_input)
                    continue
                    
                if user_input.lower() in ["exit", "quit"]:
                    await self.action_exit()
                    break
                
                ui.print_user(user_input)
                # Add user input to state with memory pruning
                await self.state.add_message_with_pruning(
                    "user", 
                    user_input,
                    memory_manager=self.memory_manager
                )
                self.state.phase = AgentPhase.THINKING
                
                # Calculate max loops for this session
                self.pacemaker.max_loops = self.pacemaker.calculate_max_loops()
                self.pacemaker.loop_count = 0
                
                ui.print_vitals(
                    self.state.vitals, 
                    self.pacemaker.loop_count, 
                    self.pacemaker.max_loops
                )
                
                # --- Autonomous Execution Loop ---
                # Continue thinking and executing until we produce a response to the user
                while True:
                    # Increment loop counter
                    self.pacemaker.loop_count += 1
                    logger.debug(f"Autonomous loop iteration: {self.pacemaker.loop_count}/{self.pacemaker.max_loops}")
                    
                    # Display vitals at the start of each loop iteration
                    ui.print_vitals(
                        self.state.vitals,
                        self.pacemaker.loop_count,
                        self.pacemaker.max_loops
                    )
                    
                    # --- Pacemaker Health Check (Before LLM Call) ---
                    intervention = self.pacemaker.check_health()
                    if intervention:
                        # Force intervention via duck_call
                        ui.print_warning(f"🦆 Pacemaker介入: {intervention.message}")
                        action_list = ActionList(
                            actions=[self.pacemaker.intervene(intervention)],
                            reasoning=f"Pacemaker intervention: {intervention.type}"
                        )
                        # Skip normal LLM call and execute intervention action
                    else:
                        # 2. Think & Decide Phase (Normal)
                        self.state.phase = AgentPhase.THINKING
                        with ui.create_spinner("Thinking..."):
                            # Determine context mode
                            context_mode = self.state.get_context_mode()
                            
                            # Generate system prompt
                            system_prompt = get_system_prompt(
                                tool_descriptions=self.get_tool_descriptions(),
                                state_context=self.state.to_prompt_context(),
                                mode=context_mode
                            )
                            
                            # Prepare messages
                            messages = [
                                {"role": "system", "content": system_prompt}
                            ] + self.state.conversation_history
                            
                            # Debug output
                            if self.debug_context_mode:
                                ui.print_debug_context(messages, mode=self.debug_context_mode)
                            
                            # Call LLM
                            action_list = await self.llm.chat(messages, response_model=ActionList)
                        
                        logger.info(f"Agent proposed actions: {[a.name for a in action_list.actions]}")
                        
                        # Sym-Ops v3.1: バイタルを更新 (c=confidence, s=safety, m=memory, f=focus)
                        if action_list.vitals:
                            logger.info(f"Updating vitals from response: {action_list.vitals}")
                            if "confidence" in action_list.vitals:
                                self.state.vitals.confidence = action_list.vitals["confidence"]
                            if "safety" in action_list.vitals:
                                self.state.vitals.safety = action_list.vitals["safety"]
                            if "memory" in action_list.vitals:
                                self.state.vitals.memory = action_list.vitals["memory"]
                            if "focus" in action_list.vitals:
                                self.state.vitals.focus = action_list.vitals["focus"]
                        
                        # Display reasoning
                        ui.print_thinking(action_list.reasoning)
                    
                    # 3. Execute Actions
                    self.state.phase = AgentPhase.EXECUTING
                    if action_list.actions:
                        await self.execute_actions(action_list)
                        
                        # Check if we should return to user
                        # If 'response', 'exit', or 'duck_call' action was executed, break the inner loop
                        should_return_to_user = False
                        for action in action_list.actions:
                            if action.name in ["response", "exit", "duck_call"]:
                                should_return_to_user = True
                                break
                        
                        if should_return_to_user:
                            logger.info("Autonomous loop ending: response/exit/duck_call action executed")
                            # Reset pacemaker for next session
                            self.pacemaker.reset()
                            break
                    else:
                        # No actions proposed, break the inner loop
                        logger.info("Autonomous loop ending: no actions proposed")
                        self.pacemaker.reset()
                        break
                # ---------------------------------

                # ターン完了: セッションを保存する
                if self.session_manager is not None and self.running:
                    self.state.touch()
                    self.session_manager.save(self.state)

                # Display Token Usage
                ui.print_token_usage(self.llm.usage_stats)
                
            except KeyboardInterrupt:
                await self.action_exit()
                break
            except Exception as e:
                logger.error("Error in main loop", exc_info=True)
                ui.print_error(str(e))

    async def execute_actions(self, action_list: ActionList):
        """Dispatch and execute a list of actions."""
        logger.info(f"Executing actions: {[a.name for a in action_list.actions]}")
        results = []

        # --- Safety Score Interceptor (Sym-Ops v3.1) ---
        # safety スコアが 0.5 未満の場合、実行前にユーザー確認を求める
        safety_score = 1.0
        if action_list.vitals:
            safety_score = action_list.vitals.get("safety", 1.0)
        if safety_score < 0.5:
            ui.print_safety_warning(safety_score)
            if not ui.request_confirmation("低い Safety Score で実行を続けますか？"):
                cancel_msg = (
                    f"Safety Score が低いため ({safety_score:.2f})、"
                    "ユーザーがすべてのアクションをキャンセルしました。"
                    "安全な代替手段を検討してください。"
                )
                self.state.add_message("assistant", cancel_msg)
                return results
        # ------------------------------------------------

        for action in action_list.actions:
            ui.print_action(action.name, action.parameters, action.thought)
            
            # --- Approval Check ---
            requires_approval = False
            was_approved = False
            warning_msg = ""
            
            if action.name in ["delete_file", "replace_in_file"]:
                requires_approval = True
                warning_msg = f"This action will modify/delete '{action.parameters.get('path', 'unknown')}'. Are you sure?"
            
            elif action.name == "write_file":
                path = action.parameters.get("path")
                if path and file_ops.file_exists(path):
                    requires_approval = True
                    warning_msg = f"File '{path}' already exists. Overwrite?"
            
            if requires_approval:
                if not ui.request_confirmation(warning_msg):
                    msg = f"Action '{action.name}' denied by user."
                    ui.print_result(msg, is_error=True)
                    self.state.last_action_result = msg
                    
                    # Add denial to conversation history so LLM knows what happened
                    denial_context = (
                        f"[User denied approval for action '{action.name}'] "
                        f"Reason: {warning_msg}. "
                        f"The user refused to proceed with this operation. "
                        f"Please either: 1) Ask the user what to do instead, "
                        f"2) Try a different approach, or 3) Explain the situation."
                    )
                    self.state.add_message("assistant", denial_context)
                    
                    # Update Pacemaker vitals (denial is treated as an error)
                    self.pacemaker.update_vitals(action, msg, is_error=True)
                    
                    results.append(msg)
                    continue
                else:
                    # User approved - mark this action as approved
                    was_approved = True
                    params_str = ", ".join([f"{k}={v}" for k, v in action.parameters.items()])
                    approval_msg = (
                        f"[SYSTEM: User approved action '{action.name}'] "
                        f"The user explicitly authorized the overwrite/modification. "
                        f"The tool is executing now. "
                        f"ASSUME SUCCESS. Do not retry this action. Move to the next step (e.g., responding to the user)."
                    )
                    self.state.add_message("assistant", approval_msg)
                    logger.info(f"User approved action: {action.name}")
            # ----------------------
            
            if action.name in self.tools:
                try:
                    # Execute tool
                    func = self.tools[action.name]
                    logger.info(f"Calling tool: {action.name}")
                    
                    # Check if function is async
                    if asyncio.iscoroutinefunction(func):
                        result = await func(**action.parameters)
                    else:
                        result = func(**action.parameters)
                    
                    logger.info(f"Tool {action.name} returned. Result length: {len(str(result))}")
                    
                    # Record result
                    self.state.last_action_result = f"Action '{action.name}' succeeded: {result}"
                    
                    # Add result to conversation history (for LLM context in next cycle)
                    # For most tools, add a summary. For response, it's already added.
                    if action.name != "response":
                        # Truncate very long results for conversation history
                        result_str = str(result)
                        max_history_length = 4000  # Limit context size
                        if len(result_str) > max_history_length:
                            result_summary = result_str[:max_history_length] + f"\n... (truncated {len(result_str) - max_history_length} characters)"
                        else:
                            result_summary = result_str
                        
                        # If this action required approval, add explicit completion message
                        if was_approved:
                            completion_msg = (
                                f"[Tool: {action.name}] {result_summary}\n\n"
                                f"[TASK COMPLETED] The user's request has been fulfilled. "
                                f"The file operation completed successfully. "
                                f"You should now respond to the user confirming completion."
                            )
                            self.state.add_message("assistant", completion_msg)
                        else:
                            self.state.add_message("assistant", f"[Tool: {action.name}] {result_summary}")
                        
                        ui.print_result(result_str)
                    
                    results.append(result)
                    
                    # Update Pacemaker vitals (success)
                    self.pacemaker.update_vitals(action, result, is_error=False)

                except Exception as e:
                    error_msg = f"Action '{action.name}' failed: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    self.state.last_action_result = error_msg
                    ui.print_result(str(e), is_error=True)
                    
                    # Add error to conversation history
                    self.state.add_message("assistant", f"[Tool Error: {action.name}] {error_msg}")
                    
                    results.append(error_msg)
                    
                    # Update Pacemaker vitals (error)
                    self.pacemaker.update_vitals(action, error_msg, is_error=True)
            else:
                msg = f"Unknown tool: {action.name}"
                logger.warning(msg)
                self.state.last_action_result = msg
                ui.print_result(msg, is_error=True)
                
                # Add unknown tool error to conversation history
                available_tools = ", ".join(self.tools.keys())
                self.state.add_message(
                    "assistant", 
                    f"[Error] Tool '{action.name}' does not exist. "
                    f"Available tools: {available_tools}. "
                    f"Please use one of the available tools."
                )
                
                results.append(msg)
                
                # Update Pacemaker vitals (error - unknown tool)
                self.pacemaker.update_vitals(action, msg, is_error=True)
        
        # Update token usage display
        if ui:
            ui.print_token_usage(self.llm.usage_stats)
            
        logger.info("Finished executing actions")
        return results

    # --- Basic Actions ---

    async def action_response(self, message: str) -> str:
        """Send a message to the user."""
        # Add to history
        self.state.add_message("assistant", message)
        
        # Print nicely
        from rich.panel import Panel
        from rich.markdown import Markdown
        ui.console.print(Panel(
            Markdown(message),
            title="[duck]🦆 Duckflow[/duck]",
            border_style="duck",
            expand=False
        ))
        return "Responded to user."

    async def action_run_command(self, command: str) -> str:
        """
        Execute a shell command with mandatory user approval.
        """
        ui.print_warning(f"⚠️  Permission requested to run: [bold]{command}[/bold]")
        
        confirmed = ui.request_confirmation(f"Execute this command?")
        
        if confirmed:
            return await ShellTool.run_command(command)
        else:
            ui.print_error("Command execution denied by user.")
            return (
                f"Execution denied by user. "
                f"The user refused to run the command: '{command}'. "
                f"Do not retry the same command without modification or explanation."
            )

    async def action_finish(self, result: str):
        """Complete the task and report result."""
        # Add to history
        self.state.add_message("assistant", f"[FINISHED] {result}")
        
        # Print nicely
        from rich.panel import Panel
        from rich.markdown import Markdown
        ui.console.print(Panel(
            Markdown(result),
            title="[duck]🦆 Task Completed[/duck]",
            border_style="green",
            expand=False
        ))
        return "Task finished. Result reported to user."

    async def action_exit(self):
        """Exit the application."""
        ui.print_system("Goodbye! 🦆")
        self.running = False
        return "Exiting."

    async def action_execute_tasks(self) -> str:
        """
        Execute all tasks in the current step. NO PARAMETERS NEEDED - operates on the active step automatically.
        This is a batch execution that runs multiple tasks sequentially.
        """
        if not self.state.current_plan:
            return "No active plan. Create a plan first with 'propose_plan'."
        
        current_step = self.state.current_plan.get_current_step()
        if not current_step:
            return "No active step in the plan."
        
        if not current_step.tasks:
            return f"No tasks found for step '{current_step.title}'. Generate tasks first with 'generate_tasks'."
        
        ui.print_system(f"Executing {len(current_step.tasks)} tasks for step: '{current_step.title}'")
        
        # Execute tasks using TaskExecutor
        summary = await self.task_executor.execute_task_list(current_step.tasks)
        
        final_summary = ""
        # Generate AI-powered summary
        try:
            ai_summary = await self.result_summarizer.summarize_execution(summary)
            ui.print_result(ai_summary)
            final_summary = ai_summary
        except Exception as e:
            logger.error(f"Failed to generate AI summary: {e}")
            # Fallback to simple summary
            summary_text = self.task_executor.get_summary_text(summary)
            ui.print_result(summary_text)
            final_summary = summary_text
        
        # Update step status if all tasks completed
        if summary["failed"] == 0:
            current_step.status = TaskStatus.COMPLETED
            return f"All tasks completed successfully! Step '{current_step.title}' is now complete.\n\nExecution Summary:\n{final_summary}"
        else:
            return f"Task execution finished with {summary['failed']} failures. Please review and retry failed tasks.\n\nExecution Summary:\n{final_summary}"

    # --- Investigation Tools (Sym-Ops v3.1) ---

    async def action_investigate(self, reason: str = "") -> str:
        """
        Investigationモードに遷移する。原因不明の問題をOODAループで調査するときに使う。

        Args:
            reason: 調査を開始する理由・背景

        Returns:
            モード遷移の確認メッセージ
        """
        self.state.enter_investigation_mode()
        ui.print_system(f"🔍 Investigation Mode に切り替えました。理由: {reason}")
        logger.info(f"Entering Investigation Mode: {reason}")
        return f"Investigation Mode started. Reason: {reason}"

    async def action_submit_hypothesis(self, hypothesis: str) -> str:
        """
        Investigationモード中に仮説を提出して検証サイクルを進める。
        2回失敗するとPacemakerがduck_callを強制する。

        Args:
            hypothesis: 検証する仮説の内容

        Returns:
            仮説受領の確認メッセージ（次のステップはツール呼び出しで検証を行うこと）
        """
        if self.state.investigation_state is None:
            # Investigationモードでなければ自動的に遷移
            self.state.enter_investigation_mode()

        inv = self.state.investigation_state
        inv.hypothesis = hypothesis
        inv.hypothesis_attempts += 1
        inv.ooda_cycle += 1
        inv.observations.append(f"[Hypothesis #{inv.hypothesis_attempts}] {hypothesis}")

        ui.print_system(
            f"🔍 仮説 #{inv.hypothesis_attempts}/2 を受け付けました: {hypothesis}"
        )
        logger.info(f"Hypothesis #{inv.hypothesis_attempts} submitted: {hypothesis}")
        return (
            f"Hypothesis #{inv.hypothesis_attempts} registered: '{hypothesis}'. "
            "Now verify this hypothesis using read_file / run_command / list_directory. "
            f"Remaining attempts before duck_call: {max(0, 2 - inv.hypothesis_attempts)}"
        )

    async def action_finish_investigation(self, conclusion: str = "") -> str:
        """
        調査を完了してPlanningモードに戻る。根本原因が特定されたときに呼ぶ。

        Args:
            conclusion: 調査で得られた結論・根本原因

        Returns:
            モード遷移の確認メッセージ
        """
        inv_state = self.state.investigation_state
        obs_count = len(inv_state.observations) if inv_state else 0

        self.state.enter_planning_mode()
        ui.print_system(f"✅ Investigation 完了。Planning Mode に切り替えました。結論: {conclusion}")
        logger.info(f"Finishing Investigation Mode. Conclusion: {conclusion}")
        return (
            f"Investigation complete after {obs_count} observations. "
            f"Conclusion: {conclusion}. "
            "Now switched to Planning Mode. Use propose_plan to plan the fix."
        )

    async def action_execute_batch(self, **kwargs) -> str:
        """
        Sym-Ops v3.1 Fast Path: 複数の独立したアクションをバッチ実行する。
        パーサーが execute_batch ブロックを個別アクションに展開するため、
        このツールが直接呼ばれることは通常なく、フォールバック用。

        Returns:
            バッチ実行の結果サマリー
        """
        return (
            "execute_batch is handled by the parser. "
            "If you see this message, the parser may have failed to expand the batch block."
        )
