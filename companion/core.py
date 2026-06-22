import asyncio
import logging
import json
from typing import Dict, Any, Callable, List

from companion.state.agent_state import (
    AgentState,
    ActionList,
    Action,
    AgentPhase,
    TaskStatus,
    AgentMode,
    SyntaxErrorInfo,
    MAX_HYPOTHESIS_ATTEMPTS,
)
from companion.base.llm_client import default_client, LLMClient
from companion.prompts.builder import PromptBuilder
from companion.tools.file_ops import file_ops
from companion.tools.plan_tool import PlanTool
from companion.tools.task_tool import TaskTool
from companion.tools.approval import ApprovalTool
from companion.execution.task_executor import TaskExecutor
from companion.execution.result_summarizer import ResultSummarizer
from companion.modules.pacemaker import DuckPacemaker
from companion.modules.memory import MemoryManager
from companion.modules.timeline import TimelineTracker
from companion.ui import ui
from companion.core_tools import (
    MODE_TOOL_MAPPING,
    UNIVERSAL_TOOLS,
    get_tool_descriptions,
    register_default_tools,
)
from companion.core_action_pipeline import (
    action_list_safety_score,
    build_fail_fast_history_message,
    build_fail_fast_warning,
    build_safety_cancel_message,
    build_investigation_edit_block,
    limit_actions_per_turn,
    filter_known_actions,
    move_terminal_actions_to_end,
    remaining_actions_after,
    requires_safety_confirmation,
    should_block_investigation_edit,
    should_fail_fast,
)
from companion.core_action_results import (
    build_action_summary,
    build_action_exception_syntax_error,
    build_denial_context,
    build_tool_result_message,
    get_approval_request,
)
from companion.core_action_invocation import invoke_tool

logger = logging.getLogger(__name__)

from companion.modules.command_handler import CommandHandler
from companion.modules.session_manager import SessionManager
from companion.tools.shell_tool import ShellTool
from companion.tools.results import (
    ToolStatus,
    serialize_to_text,
    is_tool_result_message,
)
from companion.tools.sub_llm_tools import SubLLMTools
from companion.modules.sub_llm_manager import SubLLMManager
from companion.core_action_executor import execute_actions as _execute_actions
from companion.core_loop_helpers import (
    update_vitals_from_response,
    build_intervention_prompt,
    check_and_prune_if_needed,
    should_return_to_user,
)


class DuckAgent:
    """
    Duckflow v4 Main Agent.
    Manages the Think-Decide-Execute loop.
    """

    def __init__(
        self,
        llm_client: LLMClient = default_client,
        session_manager: "SessionManager" = None,
        resume_state: "AgentState" = None,
    ):
        """
        Args:
            llm_client: 使用するLLMクライアント
            session_manager: セッション保存を担当するマネージャー（Noneなら保存しない）
            resume_state: 前回セッションから復元した AgentState（Noneなら新規）
        """
        self.state = resume_state if resume_state is not None else AgentState()
        self.session_manager = session_manager
        self.llm = llm_client
        self.tools: Dict[str, Callable] = {}
        self.running = False
        self.command_handler = CommandHandler(self)

        # Initialize Tools
        self.plan_tool = PlanTool(self.state)
        self.task_tool = TaskTool(self.state, self.llm)
        self.approval_tool = ApprovalTool(self.state)
        self.task_executor = TaskExecutor(self.state, self.tools)
        self.result_summarizer = ResultSummarizer(self.llm)

        # Initialize Sub-LLMs
        self.sub_llm_manager = SubLLMManager(self.llm)
        self.sub_llm_tools = SubLLMTools(self.sub_llm_manager)

        # Initialize Pacemaker
        self.pacemaker = DuckPacemaker(self.state)

        # Initialize Timeline Tracker (S3-11)
        self.timeline = TimelineTracker(max_entries=50)

        # Initialize Memory Manager
        self.memory_manager = MemoryManager(llm_client=self.llm, max_tokens=8000)

        # Initialize CoreActions (extracted action handlers)
        from companion.core_actions import CoreActions
        self._actions = CoreActions(self)

        register_default_tools(self)

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
            logger.info(f"\U0001f504 Attempting to switch model to {provider}/{model}")

            success = self.llm.reinitialize(provider=provider, model=model)

            if not success:
                logger.error("Failed to reinitialize LLM client")
                return False

            connection_ok = await self.llm.test_connection()
            if not connection_ok:
                logger.error("Connection test failed for new model")
                return False

            logger.info("Updating dependent components...")

            self.task_tool.llm = self.llm
            self.result_summarizer.llm = self.llm

            self.memory_manager.llm_client = self.llm
            try:
                ctx_len = await self.llm.get_context_length()
                self.memory_manager.configure_from_context_length(ctx_len)
            except Exception as e:
                logger.warning(
                    f"Failed to update memory budget after model switch: {e}"
                )

            logger.info("Persisting configuration to duckflow.yaml...")
            config.update_config("llm.provider", provider)
            config.update_config(f"llm.{provider}.model", model)

            logger.info(f"\u2705 Successfully switched to {provider}/{model}")
            return True

        except Exception as e:
            logger.error(f"\u274c Error switching model: {e}")
            return False

    UNIVERSAL_TOOLS = UNIVERSAL_TOOLS
    MODE_TOOL_MAPPING = MODE_TOOL_MAPPING

    def get_tool_descriptions(self, mode: str = None) -> str:
        """
        Generate tool descriptions in Sym-Ops syntax (::action @target param=val).

        Args:
            mode: Agent's current mode ("planning", "investigation", "task")
                  If None, returns all tools.

        Returns:
            Formatted tool descriptions in Sym-Ops style.
        """
        return get_tool_descriptions(self.tools, mode)

    async def run(self):
        """Main execution loop."""
        self.running = True

        # モデルのコンテキスト長を取得して MemoryManager の max_tokens を動的設定
        try:
            context_length = await self.llm.get_context_length()
            configured = self.memory_manager.configure_from_context_length(
                context_length
            )
            logger.info(
                f"Dynamic memory budget: {configured:,} tokens (model context: {context_length:,})"
            )
        except Exception as e:
            logger.warning(f"Failed to configure dynamic memory budget: {e}")

        # 復元セッションのサイズが大きい場合はLLM要約で圧縮する
        if (
            self.session_manager is not None
            and len(self.state.conversation_history) > 0
            and self.memory_manager.should_prune(self.state.conversation_history)
        ):
            logger.info("Session restore: applying restore_with_summary...")
            self.state.conversation_history = (
                await self.memory_manager.restore_with_summary(
                    self.state.conversation_history
                )
            )
            logger.info(
                f"Session restore complete: {len(self.state.conversation_history)} messages retained"
            )

        ui.print_welcome()

        # セッション復元時に過去の会話を表示（最新5回分）
        if self.state.conversation_history:
            history_to_show = self.state.conversation_history[-10:]
            if history_to_show:
                ui.print_info("\n\U0001f4dc 過去の会話履歴を復元します:")
                for msg in history_to_show:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    if role not in ["user", "assistant"]:
                        continue
                    if is_tool_result_message(content) or content.startswith(
                        ("[System", "[SYSTEM", "[Error]", "[User denied")
                    ):
                        continue
                    ui.print_conversation_message(content, speaker=role)
                ui.print_separator()

        while self.running:
            try:
                # 1. Input Phase
                if self.state.phase == AgentPhase.AWAITING_USER:
                    pass

                user_input = await ui.get_user_input()
                if not user_input.strip():
                    continue

                # Check for internal commands
                if self.command_handler.is_command(user_input):
                    await self.command_handler.execute(user_input)
                    continue

                if user_input.lower() in ["exit", "quit"]:
                    await self._actions.action_exit()
                    break

                ui.print_user(user_input)
                await self.state.add_message_with_pruning(
                    "user", user_input, memory_manager=self.memory_manager
                )
                self.state.phase = AgentPhase.THINKING

                # Calculate max loops for this session
                self.pacemaker.max_loops = self.pacemaker.calculate_max_loops()
                self.pacemaker.loop_count = 0

                ui.print_vitals(
                    self.state.vitals,
                    self.pacemaker.loop_count,
                    self.pacemaker.max_loops,
                )

                # --- Autonomous Execution Loop ---
                ui.start_live()
                try:
                    while True:
                        self.pacemaker.loop_count += 1
                        logger.debug(
                            f"Autonomous loop iteration: {self.pacemaker.loop_count}/{self.pacemaker.max_loops}"
                        )

                        ui.print_vitals(
                            self.state.vitals,
                            self.pacemaker.loop_count,
                            self.pacemaker.max_loops,
                        )

                        # 2. Think & Decide Phase
                        self.state.phase = AgentPhase.THINKING

                        prompt_builder = PromptBuilder(self.state)
                        base_messages = prompt_builder.build_messages(
                            self.get_tool_descriptions(self.state.current_mode.value)
                        )
                        self.state.last_syntax_errors = []

                        # --- Pacemaker Health Check ---
                        intervention = self.pacemaker.check_health()
                        if intervention:
                            ui.print_warning(
                                f"\U0001f986 Pacemaker介入: {intervention.message}"
                            )
                            summary = self.pacemaker.build_intervention_summary()

                            try:
                                intervention_prompt = build_intervention_prompt(
                                    intervention, summary
                                )
                                messages = (
                                    base_messages
                                    + self.state.conversation_history
                                    + [{"role": "user", "content": intervention_prompt}]
                                )
                                with ui.create_spinner("Analyzing intervention..."):
                                    action_list = await self.llm.chat(
                                        messages, response_model=ActionList
                                    )
                            except Exception as e:
                                logger.warning(
                                    f"Intervention LLM call failed: {e}, using fallback"
                                )
                                action_list = ActionList(
                                    actions=[
                                        self.pacemaker.intervene(
                                            intervention, summary=summary
                                        )
                                    ],
                                    reasoning=f"Pacemaker intervention (fallback): {intervention.type}",
                                )
                        else:
                            await check_and_prune_if_needed(self)

                            # Normal LLM call
                            with ui.create_spinner("Thinking..."):
                                messages = (
                                    base_messages + self.state.conversation_history
                                )
                                action_list = await self.llm.chat(
                                    messages, response_model=ActionList
                                )

                            logger.info(
                                f"Agent proposed actions: {[a.name for a in action_list.actions]}"
                            )

                            update_vitals_from_response(self.state, action_list)

                            ui.print_thinking(action_list.reasoning)

                        # 3. Execute Actions
                        self.state.phase = AgentPhase.EXECUTING
                        if action_list.actions:
                            await self.execute_actions(action_list)

                            if should_return_to_user(action_list, self.state):
                                logger.info(
                                    "Autonomous loop ending: response/exit/duck_call action executed"
                                )
                                self.pacemaker.reset()
                                break
                        else:
                            logger.info("Autonomous loop ending: no actions proposed")
                            self.pacemaker.reset()
                            break
                except KeyboardInterrupt:
                    ui.print_warning(
                        "\n\u26a0\ufe0f  Interrupted by user. Returning to manual input."
                    )
                    self.pacemaker.reset()
                    self.state.phase = AgentPhase.AWAITING_USER
                finally:
                    ui.stop_live()

                # ターン完了: セッションを保存する
                if self.session_manager is not None and self.running:
                    self.state.touch()
                    self.session_manager.save(self.state)

                ui.print_token_usage(self.llm.usage_stats)

            except KeyboardInterrupt:
                await self._actions.action_exit()
                break
            except Exception as e:
                logger.error("Error in main loop", exc_info=True)
                ui.print_error(str(e))

    async def execute_actions(self, action_list: ActionList):
        """Dispatch and execute a list of actions."""
        return await _execute_actions(self, action_list)
