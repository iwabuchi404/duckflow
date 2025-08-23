# companion/enhanced/task_loop.py (v7)
"""
Duckflow v7アーキテクチャに基づくTaskLoop。

ChatLoopから委譲された重いTaskListの非同期実行と、LLMによる結果報告を担当する
「非同期ワーカー兼報告者」として機能する。
"""
import queue
import asyncio
import logging
from typing import List, Dict, Any

# v7の新しいツールとデータモデルをインポート
from companion.state.agent_state import AgentState, Task
from companion.file_ops import SimpleFileOps
from companion.code_runner import SimpleCodeRunner
from companion.llm_call_manager import LLMCallManager
from companion.prompts.prompt_compiler import PromptCompiler

class TaskLoopV7:
    def __init__(self, task_queue: queue.Queue, status_queue: queue.Queue, agent_state: AgentState):
        self.task_queue = task_queue
        self.status_queue = status_queue
        self.agent_state = agent_state
        self.file_ops = SimpleFileOps()
        self.code_runner = SimpleCodeRunner()
        self.llm_manager = LLMCallManager()
        self.prompt_compiler = PromptCompiler()
        self.running = False
        self.logger = logging.getLogger(__name__)

    def run(self):
        """タスクループのメイン処理"""
        self.running = True
        self.logger.info("TaskLoop (v7) を開始しました")
        while self.running:
            try:
                # ChatLoopからの指令を待つ
                # 指令の形式: {"type": "execute_task_list", "task_list": List[Task]}
                command = self.task_queue.get(timeout=1)
                if command is None:
                    continue

                if command.get("type") == "execute_task_list":
                    task_list = command.get("task_list", [])
                    self._execute_task_list(task_list)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"TaskLoopで予期せぬエラー: {e}", exc_info=True)
                self.status_queue.put({"type": "loop_error", "error": str(e)})

    def _execute_task_list(self, task_list: List[Task]):
        """渡されたTaskListを順番に実行する"""
        self.logger.info(f"{len(task_list)}件のタスクリストの実行を開始します。")
        execution_log = []
        overall_success = True

        for task in task_list:
            task.status = "in_progress"
            try:
                # TaskLoopが直接ツールを呼び出す
                op_parts = task.operation.split('.')
                if len(op_parts) != 2:
                    raise ValueError(f"無効な操作形式: {task.operation}")
                
                tool_name, method_name = op_parts
                
                if tool_name == "file_ops":
                    tool = self.file_ops
                elif tool_name == "code_runner":
                    tool = self.code_runner
                else:
                    raise ValueError(f"不明なツール: {tool_name}")
                    
                method = getattr(tool, method_name)
                result = method(**task.args)

                task.result = result
                task.status = "completed"
                execution_log.append(f"  - SUCCESS: {task.operation} with args {task.args} -> {result}")
            except Exception as e:
                task.status = "failed"
                task.result = str(e)
                overall_success = False
                execution_log.append(f"  - FAILED: {task.operation} with args {task.args} -> {str(e)}")
                break # 失敗した時点でループを中断

        self.logger.info("タスクリストの実行が完了しました。")
        self._report_summary(task_list, overall_success, execution_log)

    def _report_summary(self, task_list: List[Task], success: bool, log_lines: List[str]):
        """実行結果をLLMで要約して報告する"""
        self.logger.info("実行結果の要約報告を生成します。")
        
        # プロンプトコンパイラーでSpecializedプロンプトを生成
        specialized_context = self._build_summary_specialized_context(task_list, success, log_lines)
        system_prompt = self.prompt_compiler.compile_with_memory(
            pattern="base_specialized",
            base_context="あなたはタスク実行結果の要約専門家です。実行ログを分析して報告書を作成してください。",
            specialized_context=specialized_context,
            agent_state=self.agent_state
        )
        
        # LLMに問い合わせてサマリー生成（実装待ち）
        # llm_summary = await self.llm_manager.call(system_prompt, "実行結果をまとめてください")

        # ダミーのサマリーを生成
        status_str = "成功" if success else "失敗"
        summary = {
            "status": status_str,
            "message": f"タスクリストの実行が{status_str}しました。",
            "details": "\n".join(log_lines)
        }

        self.status_queue.put({
            "type": "task_list_completed",
            "summary": summary
        })
        self.logger.info("実行結果をChatLoopに報告しました。")

    def stop(self):
        self.running = False
        self.logger.info("TaskLoop (v7) を停止しました")
    
    def _build_summary_specialized_context(self, task_list: List[Task], success: bool, log_lines: List[str]) -> str:
        """実行結果要約用のSpecializedコンテキストを構築"""
        from companion.prompts.specialized_prompt_generator import SpecializedPromptGenerator
        
        task_count = len(task_list)
        completed_count = len([t for t in task_list if t.status == "completed"])
        failed_count = len([t for t in task_list if t.status == "failed"])
        
        # SpecializedPromptGeneratorを使用してTool専用プロンプトを生成
        prompt_generator = SpecializedPromptGenerator()
        operation_args = {
            "task_count": task_count,
            "completed_count": completed_count,
            "failed_count": failed_count,
            "success": success,
            "execution_log": "\n".join(log_lines),
            "task_details": [
                {
                    "operation": task.operation,
                    "status": task.status,
                    "result": str(task.result) if task.result else None
                } for task in task_list
            ]
        }
        
        return prompt_generator.generate_tool_specialized_context(
            tool_name="response_echo",
            agent_state=self.agent_state,
            operation_args=operation_args
        )