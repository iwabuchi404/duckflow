import asyncio
import logging
import json
from typing import Dict, Any, Callable, List

from companion.state.agent_state import AgentState, ActionList, Action, AgentPhase, TaskStatus, AgentMode, SyntaxErrorInfo
from companion.base.llm_client import default_client, LLMClient
from companion.prompts.builder import PromptBuilder
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
from companion.tools.results import ToolStatus, ToolResult, format_symops_response, serialize_to_text
from companion.tools.sub_llm_tools import SubLLMTools
from companion.modules.sub_llm_manager import SubLLMManager

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
        
        # Initialize Sub-LLMs
        self.sub_llm_manager = SubLLMManager(self.llm)
        self.sub_llm_tools = SubLLMTools(self.sub_llm_manager)
        
        # Initialize Pacemaker
        self.pacemaker = DuckPacemaker(self.state)
        
        # Initialize Memory Manager
        self.memory_manager = MemoryManager(
            llm_client=self.llm,
            max_tokens=8000
        )
        
        # Register basic actions
        self.register_tool("note", self.action_note_)
        self.register_tool("response", self.action_response)
        self.register_tool("report", self.action_report)
        self.register_tool("finish", self.action_finish)
        self.register_tool("exit", self.action_exit)
        self.register_tool("duck_call", self.approval_tool.duck_call)
        
        # Register File Ops
        self.register_tool("read_file", file_ops.read_file)
        self.register_tool("write_file", file_ops.write_file)
        self.register_tool("create_file", file_ops.write_file)  # Alias for Sym-Ops v2
        self.register_tool("list_directory", file_ops.list_files)
        # self.register_tool("mkdir", file_ops.mkdir)
        self.register_tool("replace_in_file", file_ops.replace_in_file)
        self.register_tool("edit_lines", file_ops.edit_lines)
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

        # Register Sub-LLM Tools
        self.register_tool("summarize_context", self.sub_llm_tools.summarize_context)
        self.register_tool("analyze_structure", self.sub_llm_tools.analyze_structure)
        self.register_tool("generate_code", self.sub_llm_tools.generate_code)

        # Register Investigation Tools (Sym-Ops v3.1)
        self.register_tool("investigate", self.action_investigate)
        self.register_tool("submit_hypothesis", self.action_submit_hypothesis)
        self.register_tool("finish_investigation", self.action_finish_investigation)

        # Register execute_batch (Sym-Ops v3.1 Fast Path)
        self.register_tool("execute_batch", self.action_execute_batch)

        # Register Project Tree Tool
        self.register_tool("get_project_tree", get_project_tree)

        # status: LLMが "::status ok" のようにプロトコル報告として出力するため、
        # 無害なno-opとして登録し、エラーやフィルタ警告を防ぐ
        self.register_tool("show_status", self.action_status)

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
            
            # Update MemoryManager（LLMクライアント + コンテキスト長を再計算）
            self.memory_manager.llm_client = self.llm
            try:
                ctx_len = await self.llm.get_context_length()
                self.memory_manager.configure_from_context_length(ctx_len)
            except Exception as e:
                logger.warning(f"Failed to update memory budget after model switch: {e}")

            # Persist to config file
            logger.info("Persisting configuration to duckflow.yaml...")
            config.update_config("llm.provider", provider)
            config.update_config(f"llm.{provider}.model", model)
            
            logger.info(f"✅ Successfully switched to {provider}/{model}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error switching model: {e}")
            return False

    # モード別ツールマッピング
    # カテゴリ別にツールを分類し、各モードで公開するツールを定義
    MODE_TOOL_MAPPING = {
        "planning": {
            # ファイル読み取り
            "read_file", "list_directory", "find_files", "get_project_tree",
            # 分析
            "analyze_structure",
            # 実行
            "run_command",
            # Sub-LLM
            "summarize_context", "generate_code",
            # 調査
            "investigate", "submit_hypothesis", "finish_investigation",
            # 出力（常時公開）
            "note", "response", "report", "finish", "exit", "duck_call", "show_status",
            # 記憶
            "search_archives", "recall",
        },
        "investigation": {
            # ファイル読み取り
            "read_file", "list_directory", "find_files", "get_project_tree",
            # 分析
            "analyze_structure",
            # 計画
            "propose_plan", "generate_tasks",
            # Sub-LLM
            "summarize_context",
            # 調査
            "investigate", "submit_hypothesis", "finish_investigation",
            # 出力（常時公開）
            "note", "response", "report", "finish", "exit", "duck_call", "show_status",
            # 記憶
            "search_archives", "recall",
        },
        "task": {
            # ファイル読み取り
            "read_file", "list_directory", "find_files", "get_project_tree",
            # ファイル編集
            "replace_in_file", "edit_lines", "edit_file", "write_file", "create_file", "delete_file",
            # 分析
            "analyze_structure",
            # 完了管理
            "mark_step_complete", "mark_task_complete",
            # 実行
            "run_command", "execute_tasks", "execute_batch",
            # 出力（常時公開）
            "note", "response", "report", "finish", "exit", "duck_call", "show_status",
            # 記憶
            "search_archives", "recall",
        },
    }

    def get_tool_descriptions(self, mode: str = None) -> str:
        """
        Generate compact tool descriptions for the system prompt (Sym-Ops v3.2).

        Args:
            mode: エージェントの現在のモード ("planning", "investigation", "task")
                  Noneの場合は全ツールを返す（後方互換性のため）

        Returns:
            ツールの説明テキスト（1行1ツール形式）
        """
        import inspect

        # モードに基づいてツールをフィルタリング
        if mode and mode in self.MODE_TOOL_MAPPING:
            allowed_tools = self.MODE_TOOL_MAPPING[mode]
        else:
            # モードが指定されていない場合は全ツールを公開
            allowed_tools = None

        descriptions = []
        for name, func in self.tools.items():
            # モードによるフィルタリング
            if allowed_tools is not None and name not in allowed_tools:
                continue

            # Docstringの最初の1段落（概要）のみを抽出
            full_doc = inspect.getdoc(func) or "No description."
            summary = full_doc.split('\n\n')[0].replace('\n', ' ')

            # シグネチャを取得
            try:
                sig = inspect.signature(func)
            except (ValueError, TypeError):
                sig = "(...)"

            descriptions.append(f"- {name}{sig}: {summary}")

        return "\n".join(descriptions)

    async def run(self):
        """Main execution loop."""
        self.running = True

        # モデルのコンテキスト長を取得して MemoryManager の max_tokens を動的設定
        try:
            context_length = await self.llm.get_context_length()
            configured = self.memory_manager.configure_from_context_length(context_length)
            logger.info(f"Dynamic memory budget: {configured:,} tokens (model context: {context_length:,})")
        except Exception as e:
            logger.warning(f"Failed to configure dynamic memory budget: {e}")

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
                    
                    # 2. Think & Decide Phase
                    self.state.phase = AgentPhase.THINKING

                    # system_promptを介入・通常両方で使うため先に生成
                    prompt_builder = PromptBuilder(self.state)
                    system_prompt = prompt_builder.build(self.get_tool_descriptions(self.state.current_mode.value))
                    # エラーフィードバックはプロンプトに注入済み。1ターン限りなのでクリア
                    self.state.last_syntax_errors = []

                    # --- Pacemaker Health Check (Before LLM Call) ---
                    intervention = self.pacemaker.check_health()
                    if intervention:
                        # ハイブリッド介入: 履歴サマリー + LLMによる状況説明
                        ui.print_warning(f"🦆 Pacemaker介入: {intervention.message}")
                        summary = self.pacemaker.build_intervention_summary()

                        try:
                            # LLMに状況説明を求める
                            intervention_prompt = (
                                "## Pacemaker Intervention\n"
                                f"Type: {intervention.type} | Severity: {intervention.severity}\n"
                                f"{intervention.message}\n\n"
                                f"## Recent Execution History\n{summary}\n\n"
                                "## Your Task\n"
                                "ユーザーに何が起きているか簡潔に説明してください:\n"
                                "1. 何をしようとしていたか\n"
                                "2. 何が問題だったか\n"
                                "3. 続行/中止/方針変更の選択肢を提示\n"
                                "::response で返答してください。"
                            )
                            messages = [
                                {"role": "system", "content": system_prompt}
                            ] + prompt_builder.get_few_shot_examples() + self.state.conversation_history + [
                                {"role": "user", "content": intervention_prompt}
                            ]
                            with ui.create_spinner("Analyzing intervention..."):
                                action_list = await self.llm.chat(messages, response_model=ActionList)
                        except Exception as e:
                            # フォールバック: LLM失敗時は履歴サマリー付きduck_call
                            logger.warning(f"Intervention LLM call failed: {e}, using fallback")
                            action_list = ActionList(
                                actions=[self.pacemaker.intervene(intervention, summary=summary)],
                                reasoning=f"Pacemaker intervention (fallback): {intervention.type}"
                            )
                    else:
                        # Normal LLM call
                        with ui.create_spinner("Thinking..."):
                            # Prepare messages
                            # Few-shot例をsystem直後、会話履歴前に注入
                            # LLMがSym-Ops構文を出力形式として学習するための会話ペア
                            messages = [
                                {"role": "system", "content": system_prompt}
                            ] + prompt_builder.get_few_shot_examples() + self.state.conversation_history

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


                        # Decide next action: Continue loop OR return to user
                        # LLM should decide based on what happened (results, current state, task progress)

                        # Check if we should return to user
                        # If 'response', 'report', 'exit', 'duck_call', or 'finish' action was executed, break the inner loop
                        # 'note' does NOT end the loop - it's for progress notifications while continuing execution
                        should_return_to_user = False
                        for action in action_list.actions:
                            if action.name in ["response", "report", "exit", "duck_call", "finish"]:
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

        # --- Unknown Tool Filter ---
        # LLMがハルシネーションで存在しないツールを呼ぶことがあるため、
        # 実行前にフィルタリングする（会話履歴を汚染しない）
        known_actions = []
        for action in action_list.actions:
            if action.name in self.tools:
                known_actions.append(action)
            else:
                logger.warning(f"Filtered out unknown tool: {action.name}")
                ui.print_warning(f"Unknown tool '{action.name}' was ignored.")
                available = ', '.join(self.tools.keys())
                self.state.last_syntax_errors.append(SyntaxErrorInfo(
                    error_type='unknown_tool',
                    raw_snippet=action.name,
                    correction_hint=f'Use only registered tools: {available}',
                ))
        action_list.actions = known_actions

        # --- Action Count Limiter ---
        # 1ターンあたりのアクション数を制限（LLMの投機的大量実行を防止）
        MAX_ACTIONS_PER_TURN = 6
        if len(action_list.actions) > MAX_ACTIONS_PER_TURN:
            dropped = len(action_list.actions) - MAX_ACTIONS_PER_TURN
            logger.warning(f"Action limit exceeded: {len(action_list.actions)} actions, dropping last {dropped}")
            ui.print_warning(f"アクション数が上限({MAX_ACTIONS_PER_TURN})を超えたため、末尾{dropped}件を切り捨てました。")
            action_list.actions = action_list.actions[:MAX_ACTIONS_PER_TURN]

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

        # --- Fail-fast: 連続エラーカウンター ---
        MAX_CONSECUTIVE_ERRORS = 2
        consecutive_errors = 0

        # ターミナルアクション（ループを終了するアクション）を末尾に並べ替え
        # 例: [report, replace_in_file] → [replace_in_file, report]
        # これにより実行系アクションが先に処理され、最後にユーザーへ報告される
        TERMINAL_ACTIONS = {"response", "report", "exit", "duck_call", "finish"}
        non_terminal = [a for a in action_list.actions if a.name not in TERMINAL_ACTIONS]
        terminal = [a for a in action_list.actions if a.name in TERMINAL_ACTIONS]
        action_list.actions = non_terminal + terminal

        for action in action_list.actions:
            ui.print_action(action.name, action.parameters, action.thought)

            # --- Approval Check ---
            requires_approval = False
            was_approved = False
            warning_msg = ""
            
            if action.name in ["delete_file", "replace_in_file", "edit_lines"]:
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
                    if action.name not in ("response", "report"):
                        # Prepare tool result for conversion
                        tool_status = ToolStatus.OK
                        # We could implement truncation check here if needed later
                        
                        tool_res = ToolResult(
                            status=tool_status,
                            tool_name=action.name,
                            target=action.parameters.get("path", action.parameters.get("command", "task")),
                            content=result
                        )
                        formatted_res = format_symops_response(tool_res)

                        # If this action required approval, add explicit completion message
                        if was_approved:
                            completion_msg = (
                                f"{formatted_res}\n\n"
                                f"[TASK COMPLETED] The user's request has been fulfilled. "
                                f"The file operation completed successfully. "
                                f"You should now respond to the user confirming completion."
                            )
                            self.state.add_message("assistant", completion_msg)
                        else:
                            self.state.add_message("assistant", formatted_res)
                        
                        if isinstance(result, str):
                            ui.print_result(result)
                        else:
                            ui.print_result(serialize_to_text(result))
                    
                    results.append(result)

                    # Update Pacemaker vitals (success)
                    self.pacemaker.update_vitals(action, result, is_error=False)
                    consecutive_errors = 0  # 成功したらリセット

                except Exception as e:
                    error_msg = f"Action '{action.name}' failed: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    self.state.last_action_result = error_msg
                    ui.print_result(str(e), is_error=True)

                    # 引数不足などの TypeError を構文エラーとして記録
                    if isinstance(e, TypeError):
                        self.state.last_syntax_errors.append(SyntaxErrorInfo(
                            error_type='missing_param',
                            raw_snippet=str(e)[:200],
                            correction_hint='Required parameter is missing. Check the tool signature.',
                        ))

                    # Add error to conversation history in Sym-Ops format
                    err_res = ToolResult(
                        status=ToolStatus.ERROR,
                        tool_name=action.name,
                        target=action.parameters.get("path", action.parameters.get("command", "task")),
                        content=e
                    )
                    self.state.add_message("assistant", format_symops_response(err_res))

                    results.append(error_msg)

                    # Update Pacemaker vitals (error)
                    self.pacemaker.update_vitals(action, error_msg, is_error=True)

                    # --- Fail-fast: 連続エラーで残りのアクションを中断 ---
                    consecutive_errors += 1
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        remaining = len(action_list.actions) - action_list.actions.index(action) - 1
                        if remaining > 0:
                            logger.warning(f"Fail-fast: {consecutive_errors} consecutive errors, aborting {remaining} remaining actions")
                            ui.print_warning(f"連続{consecutive_errors}回エラーのため、残り{remaining}件のアクションを中断しました。")
                            self.state.add_message(
                                "assistant",
                                f"[SYSTEM] 連続{consecutive_errors}回のエラーにより残り{remaining}件のアクションを中断しました。"
                                "原因を確認してから再試行してください。"
                            )
                        break
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

    # --- No-op (LLMのプロトコル的出力を吸収) ---

    async def _noop(self, **kwargs) -> str:
        """No-op: LLMが出力するプロトコル的なアクションを静かに吸収する。"""
        return "ok"

    # --- Basic Actions ---

    async def action_note_(self, message: str = "") -> str:
        """
        ユーザーに短文を通知するが、ループは継続する。
        進捗状況などを伝えるのに使用する。

        Args:
            message: ユーザーに通知するメッセージ

        Returns:
            通知完了メッセージ
        """
        # 小さくインフォとして表示
        ui.print_info(message)
        logger.info(f"Note: {message}")
        return f"Notified: {message}"

    async def action_response(self, message: str = "") -> str:
        """
        Short interactive response to the user (max 3-4 sentences).
        Use for questions, confirmations, or short acknowledgments.
        Do NOT use for long analysis or investigation results — use 'report' instead.

        Args:
            message: ユーザーに表示するメッセージ（Markdown対応）

        Returns:
            実行確認文字列 "Responded to user."
        """
        if not message:
            return "No message provided."

        self.state.add_message("assistant", message)

        from rich.panel import Panel
        from rich.markdown import Markdown
        ui.console.print(Panel(
            Markdown(message),
            title="[duck]🦆 Duckflow[/duck]",
            border_style="duck",
            expand=False
        ))
        return "Responded to user."

    async def action_report(self, message: str = "") -> str:
        """
        Structured report for investigation results, code analysis, or task completion.
        You MUST include these Markdown headers: ## 要約, ## 詳細, ## 結論.
        Do NOT use for simple questions — use 'response' instead.

        Args:
            message: レポート本文（Markdown形式、## 要約 / ## 詳細 / ## 結論 を含むこと）

        Returns:
            実行確認文字列 "Report delivered to user."
        """
        self.state.add_message("assistant", f"[REPORT]\n{message}")

        from rich.panel import Panel
        from rich.markdown import Markdown
        ui.console.print(Panel(
            Markdown(message),
            title="[duck]📋 Duckflow Report[/duck]",
            border_style="cyan",
            expand=False
        ))
        return "Report delivered to user."

    async def action_status(self) -> str:
        """
        User Display the current agent status including vitals, 
        """
        # Build status report
        status_lines = [
            "## 🦆 Duckflow Status Report",
            "",
            f"**Phase:** {self.state.phase.value}",
            f"**Mode:** {self.state.current_mode.value}",
            "",
            "### Vitals",
            f"  - Confidence: {self.state.vitals.confidence:.2f}",
            f"  - Safety: {self.state.vitals.safety:.2f}",
            f"  - Memory: {self.state.vitals.memory:.2f}",
            f"  - Focus: {self.state.vitals.focus:.2f}",
            "",
        ]

        # Add plan status if exists
        if self.state.current_plan:
            status_lines.append("### Current Plan")
            current_step = self.state.current_plan.get_current_step()
            if current_step:
                status_lines.append(f"  - Step: {current_step.title} ({current_step.status.value})")
                status_lines.append(f"  - Tasks: {len(current_step.tasks)} total")
                completed = sum(1 for t in current_step.tasks if t.status == TaskStatus.COMPLETED)
                pending = sum(1 for t in current_step.tasks if t.status == TaskStatus.PENDING)
                status_lines.append(f"    - Completed: {completed}")
                status_lines.append(f"    - Pending: {pending}")
            else:
                status_lines.append("  - No active step")
            status_lines.append("")

        # Add investigation status if active
        if self.state.investigation_state:
            inv = self.state.investigation_state
            status_lines.append("### Investigation Mode")
            status_lines.append(f"  - Hypotheses: {inv.hypothesis_attempts}/2")
            status_lines.append(f"  - OODA Cycles: {inv.ooda_cycle}")
            status_lines.append(f"  - Observations: {len(inv.observations)}")
            if inv.hypothesis:
                status_lines.append(f"  - Current Hypothesis: {inv.hypothesis}")
            status_lines.append("")

        # Add loop information
        status_lines.append(f"### Execution Loop")
        status_lines.append(f"  - Current Loop: {self.pacemaker.loop_count}/{self.pacemaker.max_loops}")
        status_lines.append(f"  - Session Created: {self.state.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

        status_report = "\n".join(status_lines)

        # Add to history and display
        self.state.add_message("assistant", f"[STATUS REPORT]\n{status_report}")

        from rich.panel import Panel
        from rich.markdown import Markdown
        ui.console.print(Panel(
            Markdown(status_report),
            title="[duck]🦆 Agent Status[/duck]",
            border_style="duck",
            expand=False
        ))

        return "Status report generated."

    async def action_run_command(self, command: str) -> str:
        """
        Execute a shell command with mandatory user approval.
        実行前に必ずユーザーに確認ダイアログを表示する。
        拒否された場合はエラーメッセージを返す。

        Args:
            command: 実行するシェルコマンド文字列

        Returns:
            コマンドの stdout/stderr 出力、またはユーザー拒否時のエラーメッセージ
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

    async def action_finish(self, result: str = "") -> str:
        """
        Mark the entire objective as accomplished.
        Provide a concise summary of the work done in the 'result' parameter.

        Args:
            result: 完了した作業の要約メッセージ

        Returns:
            実行確認文字列 "Task finished. Result reported to user."
        """
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

    async def action_exit(self) -> str:
        """
        Exit the application.
        メインループを終了し、セッションを閉じる。
        このアクションの実行後、エージェントはユーザー入力を受け付けなくなる。

        Returns:
            実行確認文字列 "Exiting."
        """
        ui.print_system("Goodbye! 🦆")
        self.running = False
        return "Exiting."

    async def action_execute_tasks(self) -> str:
        """
        Execute all tasks in the current step. NO PARAMETERS NEEDED.
        内部ツール: propose_plan → generate_tasks の後に自動的に使用される。
        アクティブなステップ内のタスクを順次バッチ実行する。

        Returns:
            実行サマリー（成功数・失敗数を含む）
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
        Switch to INVESTIGATION mode.
        Use this when you encounter an unknown error or need to explore
        to find a root cause before planning.

        Args:
            reason: 調査を開始する理由（エラー内容や不明点の説明）

        Returns:
            モード遷移の確認メッセージ
        """
        self.state.enter_investigation_mode()
        ui.print_system(f"🔍 Investigation Mode に切り替えました。理由: {reason}")
        logger.info(f"Entering Investigation Mode: {reason}")
        return f"Investigation Mode started. Reason: {reason}"

    async def action_submit_hypothesis(self, hypothesis: str) -> str:
        """
        Submit a testable hypothesis during an investigation.
        Describe what you think is wrong and what you will test next.

        Args:
            hypothesis: 検証可能な仮説の記述（原因の推測と検証方法）

        Returns:
            仮説の登録確認と残り試行回数を含むメッセージ
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
        LLMが直接呼ぶ必要はない。パーサーが ::execute_batch ブロックを
        個別アクションに自動展開するため、このメソッドはフォールバック用。

        Returns:
            パーサー未展開時のフォールバックメッセージ
        """
        return (
            "execute_batch is handled by the parser. "
            "If you see this message, the parser may have failed to expand the batch block."
        )
