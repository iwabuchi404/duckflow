# companion/v7_plan_tool.py
"""
Duckflow v7アーキテクチャに基づくPlanTool。
長期計画(Plan)の生成と状態管理(CRUD)を担当する。
プロンプトコンパイラーのSpecializedプロンプトシステムを使用。
"""
import logging
from .state.agent_state import AgentState, Plan, Step, Task
from .prompts.prompt_compiler import PromptCompiler
from .llm_call_manager import LLMCallManager

class PlanTool:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.prompt_compiler = PromptCompiler()
        self.llm_manager = LLMCallManager()

    def propose(self, agent_state: AgentState, user_goal: str) -> Plan:
        """
        ユーザーの目標に基づき、抽象的なPlanとStepの構造を生成する。
        （注意: このバージョンではダミーデータを返します。LLM連携は将来実装します）
        """
        self.logger.info(f"長期計画の生成を開始: {user_goal}")
        
        # プロンプトコンパイラーでSpecializedプロンプトを生成
        specialized_context = self._build_plan_specialized_context(user_goal, agent_state)
        system_prompt = self.prompt_compiler.compile_with_memory(
            pattern="base_specialized",
            base_context="あなたは長期計画の専門家です。ユーザーの目標を複数のStepに分解してください。",
            specialized_context=specialized_context,
            agent_state=agent_state
        )
        
        # LLMに問い合わせてPlan生成（実装待ち）
        # response_json = await self.llm_manager.call(system_prompt, f"目標: {user_goal}")
        # plan = Plan.model_validate(response_json)

        # ダミーのPlanを生成
        plan = Plan(
            name=f"{user_goal} のための計画",
            goal=user_goal,
            steps=[
                Step(name="ステップ1: 環境構築", description="開発環境をセットアップし、必要なライブラリをインストールする。"),
                Step(name="ステップ2: コア機能の実装", description="主要なビジネスロジックとデータモデルを実装する。", depends_on=["step_001"]),
                Step(name="ステップ3: テストとデバッグ", description="単体テストと結合テストを作成し、バグを修正する。", depends_on=["step_002"])
            ]
        )
        # ダミーのstep_idを割り当て
        for i, step in enumerate(plan.steps):
            step.step_id = f"step_{i+1:03d}"

        agent_state.plans.append(plan)
        agent_state.active_plan_id = plan.plan_id
        self.logger.info(f"新しい計画 '{plan.name}' を作成し、アクティブにしました。")

        return plan

    def update_step_status(self, agent_state: AgentState, step_id: str, status: str) -> bool:
        """指定されたStepのステータスを更新する"""
        for plan in agent_state.plans:
            for step in plan.steps:
                if step.step_id == step_id:
                    step.status = status
                    self.logger.info(f"ステップ '{step.name}' のステータスを {status} に更新しました。")
                    return True
        self.logger.warning(f"更新対象のステップが見つかりません: {step_id}")
        return False

    def get_plan(self, agent_state: AgentState, plan_id: str) -> Plan | None:
        """指定されたplan_idのPlanオブジェクトを取得する"""
        for plan in agent_state.plans:
            if plan.plan_id == plan_id:
                return plan
        return None
    
    def _build_plan_specialized_context(self, user_goal: str, agent_state: AgentState) -> str:
        """Plan生成用のSpecializedコンテキストを構築"""
        from .prompts.specialized_prompt_generator import SpecializedPromptGenerator
        
        # SpecializedPromptGeneratorを使用してTool専用プロンプトを生成
        prompt_generator = SpecializedPromptGenerator()
        operation_args = {
            "user_goal": user_goal,
            "recent_files": agent_state.short_term_memory.get("recent_files", [])[-3:],  # 最新3ファイル
            "current_context": agent_state.short_term_memory.get("current_context", {}),
            "goal": agent_state.goal,
            "mentioned_files": agent_state.short_term_memory.get("mentioned_files", [])[-5:]  # 最新5ファイル
        }
        
        return prompt_generator.generate_tool_specialized_context(
            tool_name="plan_tool",
            agent_state=agent_state,
            operation_args=operation_args
        )
