"""
Action handlers extracted from DuckAgent for modularity.

Each method corresponds to a Sym-Ops action that the LLM can invoke.
"""

import logging

from companion.state.agent_state import (
    TaskStatus,
    MAX_HYPOTHESIS_ATTEMPTS,
)
from companion.tools.shell_tool import ShellTool
from companion.ui import ui

logger = logging.getLogger(__name__)


class CoreActions:
    """Action handlers extracted from DuckAgent for modularity."""

    def __init__(self, agent):
        self.agent = agent
        self.state = agent.state

    def _action_noop_symops_marker(self, **_) -> str:
        """
        ::status and ::result are output markers, NOT callable actions.
        They appear inside tool results and error messages, but cannot be invoked directly.
        Use ::note for progress logging. Use ::response to deliver results.
        """
        return (
            "::status / ::result are output markers, not callable actions.\n"
            "Correct usage:\n"
            "  ::note @<progress message>      — internal log, loop continues\n"
            "  ::response @<short message>     — deliver result to user\n"
            "Do NOT call ::status or ::result as actions."
        )

    async def _noop(self, **kwargs) -> str:
        """No-op: LLMが出力するプロトコル的なアクションを静かに吸収する。"""
        return "ok"

    async def action_note(self, message: str = "") -> str:
        """
        ユーザーに短文を通知するが、ループは継続する。
        進捗状況などを伝えるのに使用する。

        Args:
            message: ユーザーに通知するメッセージ

        Returns:
            通知完了メッセージ
        """
        ui.print_info(message)
        logger.info(f"Note: {message}")
        return f"Notified: {message}"

    async def action_response(self, message: str = "") -> str:
        """
        Short interactive response to the user.
        Use for questions, confirmations, short acknowledgments, or detailed investigation results.

        Args:
            message: ユーザーに表示するメッセージ（Markdown対応）

        Returns:
            実行確認文字列 "Responded to user."
        """
        if not message:
            return "No message provided."

        self.state.add_message("assistant", message)

        ui.print_conversation_message(message, speaker="assistant")
        return "Responded to user."

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
        ui.print_warning(f"Permission requested to run: {command}")

        confirmed = ui.request_confirmation(f"Execute this command?")

        if confirmed:
            return await ShellTool.run_command(command)
        else:
            ui.print_error("Command execution denied by user.")
            return (
                f"::status error\n"
                f"Reason: Execution denied by user. "
                f"The user refused to run the command: '{command}'. "
                f"Do not retry the same command without modification or explanation."
            )

    async def action_exit(self) -> str:
        """
        Exit the application.
        メインループを終了し、セッションを閉じる。
        このアクションの実行後、エージェントはユーザー入力を受け付けなくなる。

        Returns:
            実行確認文字列 "Exiting."
        """
        ui.print_system("Goodbye! 🦆")
        self.agent.running = False
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

        ui.print_system(
            f"Executing {len(current_step.tasks)} tasks for step: '{current_step.title}'"
        )

        summary = await self.agent.task_executor.execute_task_list(current_step.tasks)

        final_summary = ""
        try:
            ai_summary = await self.agent.result_summarizer.summarize_execution(summary)
            ui.print_result(ai_summary)
            final_summary = ai_summary
        except Exception as e:
            logger.error(f"Failed to generate AI summary: {e}")
            summary_text = self.agent.task_executor.get_summary_text(summary)
            ui.print_result(summary_text)
            final_summary = summary_text

        if summary["failed"] == 0:
            current_step.status = TaskStatus.COMPLETED
            return f"All tasks completed successfully! Step '{current_step.title}' is now complete.\n\nExecution Summary:\n{final_summary}"
        else:
            return f"Task execution finished with {summary['failed']} failures. Please review and retry failed tasks.\n\nExecution Summary:\n{final_summary}"

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
        # Already in investigation mode — don't re-enter, guide to observe
        if self.state.get_context_mode() == "investigation":
            return (
                "You are ALREADY in Investigation Mode. "
                "Do NOT call ::investigate again. "
                "Observe first: ::read_file, ::grep_files, ::list_directory, or ::run_command. "
                "Then ::submit_hypothesis."
            )
        self.state.enter_investigation_mode()
        ui.print_system(f"🔍 Investigation Mode に切り替えました。理由: {reason}")
        logger.info(f"Entering Investigation Mode: {reason}")
        return (
            f"Investigation Mode started. Reason: {reason}\n"
            "━━━ NEXT ACTION REQUIRED ━━━\n"
            "Do NOT call ::response or ::duck_call yet.\n"
            "You must observe first. Call ONE of:\n"
            "  ::read_file @<path>      — read a relevant file\n"
            "  ::grep_files pattern=... — search code/logs\n"
            "  ::run_command @<cmd>     — check system state\n"
            "  ::list_directory @<dir>  — explore structure\n"
            "Gather evidence, then ::submit_hypothesis."
        )

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
            self.state.enter_investigation_mode()

        inv = self.state.investigation_state
        inv.hypothesis = hypothesis
        inv.hypothesis_attempts += 1
        inv.ooda_cycle += 1
        inv.observations.append(f"[Hypothesis #{inv.hypothesis_attempts}] {hypothesis}")

        remaining = max(0, MAX_HYPOTHESIS_ATTEMPTS - inv.hypothesis_attempts)
        ui.print_system(
            f"🔍 仮説 #{inv.hypothesis_attempts}/{MAX_HYPOTHESIS_ATTEMPTS} を受け付けました: {hypothesis}"
        )
        logger.info(f"Hypothesis #{inv.hypothesis_attempts} submitted: {hypothesis}")

        if inv.hypothesis_attempts >= MAX_HYPOTHESIS_ATTEMPTS:
            logger.warning(
                f"Hypothesis limit reached ({MAX_HYPOTHESIS_ATTEMPTS}), forcing duck_call"
            )
            return (
                f"Hypothesis #{inv.hypothesis_attempts} registered: '{hypothesis}'.\n"
                f"⚠️ HYPOTHESIS LIMIT REACHED ({MAX_HYPOTHESIS_ATTEMPTS}/{MAX_HYPOTHESIS_ATTEMPTS}). "
                "You have exhausted the allowed hypothesis attempts without confirming a root cause. "
                "You MUST call ::duck_call now to ask the user for guidance."
            )

        return (
            f"Hypothesis #{inv.hypothesis_attempts} registered: '{hypothesis}'.\n"
            "━━━ NEXT ACTION REQUIRED ━━━\n"
            "Choose ONE of the following:\n"
            "  [Not confirmed yet] Verify with: read_file / grep_files / run_command\n"
            "  [Confirmed]         Close with:  ::finish_investigation @<conclusion>\n"
            "Do NOT call ::edit_file, ::write_file, or ::response until investigation is closed.\n"
            f"Remaining hypothesis attempts before duck_call: {remaining}"
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
        ui.print_system(
            f"✅ Investigation 完了。Planning Mode に切り替えました。結論: {conclusion}"
        )
        logger.info(f"Finishing Investigation Mode. Conclusion: {conclusion}")
        return (
            f"Investigation complete after {obs_count} observations. "
            f"Conclusion: {conclusion}. "
            "Now switched to Planning Mode. "
            "You can now directly apply fixes with ::edit_file / ::write_file, "
            "or create a structured plan with ::propose_plan if the fix requires multiple steps."
        )

    async def action_execute_batch(self, **kwargs) -> str:
        """
        Sym-Ops v3.1 Fast Path: 複数の独立したアクションをバッチ実行する。
        パーサーが ::execute_batch ブロックを個別アクションに展開するため、
        このメソッドは展開失敗時のフォールバックとして機能する。

        LLM向け説明: 独立したタスクを並列的に実行したい場合に使用する。
        各アクションを %%% で区切り、content ブロック内に記述する。

        Returns:
            パーサー未展開時のフォールバックメッセージ
        """
        return (
            "execute_batch is handled by the parser. "
            "If you see this message, the parser may have failed to expand the batch block."
        )
