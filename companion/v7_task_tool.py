# companion/v7_task_tool.py
"""
Duckflow v7アーキテクチャに基づくTaskTool。
特定のStepを達成するための、具体的な作業リスト(TaskList)の生成を担当する。
プロンプトコンパイラーのSpecializedプロンプトシステムを使用。
"""
import logging
from typing import List
from .state.agent_state import AgentState, Step, Task
from .prompts.prompt_compiler import PromptCompiler
from .llm_call_manager import LLMCallManager

class TaskTool:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.prompt_compiler = PromptCompiler()
        self.llm_manager = LLMCallManager()

    def generate_list(self, agent_state: AgentState, step: Step) -> List[Task]:
        """
        特定のStepを達成するための具体的なTaskListを生成する。
        （注意: このバージョンではダミーデータを返します。LLM連携は将来実装します）
        """
        self.logger.info(f"ステップ '{step.name}' のタスクリスト生成を開始")

        # プロンプトコンパイラーでSpecializedプロンプトを生成
        specialized_context = self._build_task_specialized_context(step, agent_state)
        system_prompt = self.prompt_compiler.compile_with_memory(
            pattern="base_specialized",
            base_context="あなたはタスク分解の専門家です。Stepを具体的なTaskに分解してください。",
            specialized_context=specialized_context,
            agent_state=agent_state
        )
        
        # LLMに問い合わせてTaskList生成（実装待ち）
        # response_json = await self.llm_manager.call(system_prompt, f"Step: {step.name}")
        # task_list = [Task.model_validate(t) for t in response_json]

        # ダミーのTaskListを生成
        task_list = [
            Task(
                operation="file_ops.write", 
                args={"file_path": "./hello.py", "content": "print('Hello, Duckflow!')"},
                reasoning=f"'{step.name}' を達成するための最初のタスクとして、サンプルファイルを作成します。"
            ),
            Task(
                operation="code_runner.run", 
                args={"command": "python ./hello.py"},
                reasoning="作成したファイルが正しく実行できるか確認します。"
            )
        ]

        # 生成したTaskListをAgentStateの該当Stepに保存
        step.task_list = task_list
        self.logger.info(f"ステップ '{step.name}' のために {len(task_list)} 件のタスクを生成しました。")

        return task_list
    
    def _build_task_specialized_context(self, step: Step, agent_state: AgentState) -> str:
        """TaskList生成用のSpecializedコンテキストを構築"""
        from .prompts.specialized_prompt_generator import SpecializedPromptGenerator
        
        # SpecializedPromptGeneratorを使用してTool専用プロンプトを生成
        prompt_generator = SpecializedPromptGenerator()
        operation_args = {
            "step_name": step.name,
            "step_description": step.description,
            "depends_on": step.depends_on
        }
        
        return prompt_generator.generate_tool_specialized_context(
            tool_name="task_tool",
            agent_state=agent_state,
            operation_args=operation_args
        )
