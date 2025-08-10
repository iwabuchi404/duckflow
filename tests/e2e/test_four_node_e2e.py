"""
4ノードオーケストレーターのエンドツーエンドテスト
実際のユーザーシナリオを模擬したテスト
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from codecrafter.orchestration.four_node_orchestrator import FourNodeOrchestrator
from codecrafter.state.agent_state import AgentState, ConversationMessage, WorkspaceInfo, GraphState
from codecrafter.prompts.four_node_context import (
    UnderstandingResult, ExecutionPlan, GatheredInfo, ProjectContext, 
    FileContent, NodeType, NextAction
)


class TestFourNodeE2EScenarios:
    """実際のユーザーシナリオに基づくE2Eテスト"""
    
    @pytest.fixture
    def e2e_workspace(self):
        """E2Eテスト用のワークスペース"""
        temp_dir = tempfile.mkdtemp()
        workspace = Path(temp_dir)
        
        # Pythonプロジェクトのサンプル構造を作成
        (workspace / "src").mkdir()
        (workspace / "tests").mkdir()
        (workspace / "docs").mkdir()
        
        # メインファイル
        (workspace / "src" / "__init__.py").write_text("")
        (workspace / "src" / "main.py").write_text("""
# メインアプリケーション
def main():
    print("Hello, World!")
    
if __name__ == "__main__":
    main()
""")
        
        # ユーティリティファイル
        (workspace / "src" / "utils.py").write_text("""
# ユーティリティ関数
def calculate(a, b):
    return a + b
    
def format_string(text):
    return text.strip().lower()
""")
        
        # 設定ファイル
        (workspace / "config.json").write_text('{"debug": true, "version": "1.0.0"}')
        
        # README
        (workspace / "README.md").write_text("# Sample Project\\n\\nThis is a sample project.")
        
        yield workspace
        shutil.rmtree(temp_dir)
    
    def create_agent_state(self, workspace: Path, user_message: str) -> AgentState:
        """テスト用のAgentStateを作成"""
        files = [str(p.relative_to(workspace)) for p in workspace.rglob("*") if p.is_file()]
        
        state = AgentState(session_id="e2e_test")
        state.conversation_history = [
            ConversationMessage(
                role="user",
                content=user_message,
                timestamp=datetime.now()
            )
        ]
        state.graph_state = GraphState()
        state.workspace = WorkspaceInfo(
            path=str(workspace),
            files=files
        )
        return state
    
    def test_scenario_1_simple_file_creation(self, e2e_workspace):
        """シナリオ1: シンプルなファイル作成要求"""
        user_message = "src/database.pyファイルを作成して、基本的なデータベース接続クラスを実装してください"
        state = self.create_agent_state(e2e_workspace, user_message)
        orchestrator = FourNodeOrchestrator(state)
        
        # 1. 理解・計画フェーズの動作確認
        context = orchestrator.four_node_context
        assert context.current_node == NodeType.UNDERSTANDING
        
        # 理解結果を模擬
        understanding_result = UnderstandingResult(
            requirement_analysis="新しいファイル作成: データベース接続クラス",
            execution_plan=ExecutionPlan(
                summary="database.pyにDBConnectionクラスを実装",
                steps=["ファイル作成", "クラス定義", "接続メソッド実装"],
                required_tools=["write_file"],
                expected_files=["src/database.py"],
                estimated_complexity="medium",
                success_criteria="データベース接続クラスが正常に実装される"
            ),
            identified_risks=["新規ファイル作成"],
            information_needs=["プロジェクト構造の確認"],
            confidence=0.8,
            complexity_assessment="中程度"
        )
        context.understanding = understanding_result
        
        # 2. 分岐判定の確認
        next_step = orchestrator._after_understanding_planning(state)
        assert next_step in ["gather_info", "execute_directly"]
        
        # 3. 情報収集フェーズ（必要時）
        if next_step == "gather_info":
            context.current_node = NodeType.GATHERING
            
            # 情報収集結果を模擬
            gathered_info = GatheredInfo(
                collected_files={
                    "src/__init__.py": FileContent(
                        path="src/__init__.py",
                        content="",
                        encoding="utf-8",
                        size=0,
                        last_modified=datetime.now()
                    )
                },
                rag_results=[],
                project_context=ProjectContext(
                    project_type="Python Application",
                    main_languages=["Python"],
                    frameworks=[],
                    architecture_pattern="Simple",
                    key_directories=["src", "tests", "docs"],
                    recent_changes=[]
                ),
                confidence_scores={"file_coverage": 0.8},
                information_gaps=[],
                collection_strategy="focused"
            )
            context.gathered_info = gathered_info
            
            # 情報収集後の分岐確認
            next_step = orchestrator._after_information_gathering(state)
            assert next_step == "execute"
    
    def test_scenario_2_code_modification(self, e2e_workspace):
        """シナリオ2: 既存コードの修正要求"""
        user_message = "src/utils.pyのcalculate関数に乗算機能を追加してください"
        state = self.create_agent_state(e2e_workspace, user_message)
        orchestrator = FourNodeOrchestrator(state)
        
        context = orchestrator.four_node_context
        
        # 既存ファイルの修正要求なので情報収集が必要
        understanding_result = UnderstandingResult(
            requirement_analysis="既存ファイル修正: calculate関数の拡張",
            execution_plan=ExecutionPlan(
                summary="utils.pyのcalculate関数に乗算オプションを追加",
                steps=["既存ファイル読み取り", "関数修正", "ファイル更新"],
                required_tools=["read_file", "write_file"],
                expected_files=["src/utils.py"],
                estimated_complexity="low",
                success_criteria="calculate関数が乗算にも対応する"
            ),
            identified_risks=["既存ファイル変更", "関数の互換性"],
            information_needs=["現在の関数実装", "使用箇所の確認"],
            confidence=0.9,
            complexity_assessment="低複雑度"
        )
        context.understanding = understanding_result
        
        # 既存ファイルの修正なので情報収集が必要
        next_step = orchestrator._after_understanding_planning(state)
        assert next_step == "gather_info"
        
        # リスク評価の確認
        risk_assessment = orchestrator.helpers.assess_execution_risks(
            understanding_result, None, state
        )
        assert risk_assessment.approval_required  # ファイル変更なので承認必要
    
    def test_scenario_3_complex_multi_file_task(self, e2e_workspace):
        """シナリオ3: 複数ファイルにまたがる複雑なタスク"""
        user_message = "テスト用のファイルを作成して、src/utils.pyの全関数をテストしてください"
        state = self.create_agent_state(e2e_workspace, user_message)
        orchestrator = FourNodeOrchestrator(state)
        
        context = orchestrator.four_node_context
        
        # 複雑なタスクの理解結果
        understanding_result = UnderstandingResult(
            requirement_analysis="複数ファイル作成: テストファイルとテストケース",
            execution_plan=ExecutionPlan(
                summary="utils.py用のテストファイル作成と全関数テスト実装",
                steps=[
                    "src/utils.pyの解析", 
                    "tests/test_utils.pyの作成",
                    "各関数のテストケース実装",
                    "テスト実行確認"
                ],
                required_tools=["read_file", "write_file", "create_directory"],
                expected_files=["src/utils.py", "tests/test_utils.py"],
                estimated_complexity="high",
                success_criteria="全関数が適切にテストされる"
            ),
            identified_risks=["複数ファイル操作", "テストファイル作成"],
            information_needs=["utils.pyの関数一覧", "テスト構造の理解"],
            confidence=0.7,
            complexity_assessment="高複雑度"
        )
        context.understanding = understanding_result
        
        # 高複雑度タスクなので情報収集が必要
        next_step = orchestrator._after_understanding_planning(state)
        assert next_step == "gather_info"
        
        # リスク評価で高リスクが検出される
        risk_assessment = orchestrator.helpers.assess_execution_risks(
            understanding_result, None, state
        )
        assert risk_assessment.overall_risk.value == "high"
        assert risk_assessment.approval_required
    
    def test_scenario_4_error_recovery_workflow(self, e2e_workspace):
        """シナリオ4: エラー回復ワークフロー"""
        user_message = "存在しないファイルを編集してください"
        state = self.create_agent_state(e2e_workspace, user_message)
        
        # エラー履歴を追加してリトライ状況を模擬
        from codecrafter.state.agent_state import ToolExecution
        state.tool_executions = [
            ToolExecution(
                tool_name="read_file",
                arguments={"path": "nonexistent.py"},
                result=None,
                error="FileNotFoundError: File not found",
                execution_time=0.1,
                timestamp=datetime.now()
            )
        ]
        
        orchestrator = FourNodeOrchestrator(state)
        
        # リトライコンテキストが検出される
        is_retry = orchestrator.helpers.is_retry_context(state)
        assert is_retry == True
        
        # エラー回復の理解結果
        understanding_result = UnderstandingResult(
            requirement_analysis="エラー回復: ファイルが見つからない問題",
            execution_plan=ExecutionPlan(
                summary="存在しないファイルの確認と作成または代替案提示",
                steps=["ファイル存在確認", "代替ファイル検索", "新規作成または提案"],
                required_tools=["list_files", "create_directory", "write_file"],
                expected_files=[],
                estimated_complexity="medium",
                success_criteria="適切な解決策の提示"
            ),
            identified_risks=["ファイル不存在", "ユーザー意図の不明確性"],
            information_needs=["ユーザーの真の意図", "関連ファイルの確認"],
            confidence=0.6,
            complexity_assessment="エラー回復"
        )
        
        orchestrator.four_node_context.understanding = understanding_result
        
        # エラー回復時は情報収集が重要
        next_step = orchestrator._after_understanding_planning(state)
        assert next_step == "gather_info"
    
    def test_workflow_completion_cycle(self, e2e_workspace):
        """完全なワークフローサイクルのテスト"""
        user_message = "README.mdを読んで、プロジェクトの概要をコンソールに出力してください"
        state = self.create_agent_state(e2e_workspace, user_message)
        orchestrator = FourNodeOrchestrator(state)
        
        # 1. 理解・計画
        context = orchestrator.four_node_context
        understanding_result = UnderstandingResult(
            requirement_analysis="ファイル読み取りと内容出力",
            execution_plan=ExecutionPlan(
                summary="README.md読み取りとコンソール出力",
                steps=["README.md読み取り", "内容表示"],
                required_tools=["read_file"],
                expected_files=["README.md"],
                estimated_complexity="low",
                success_criteria="README内容がコンソールに表示される"
            ),
            identified_risks=[],
            information_needs=[],
            confidence=0.95,
            complexity_assessment="簡単"
        )
        context.understanding = understanding_result
        
        # 2. 実行（情報収集をスキップして直接実行）
        next_step = orchestrator._after_understanding_planning(state)
        # 低複雑度で expected_files が空でないので情報収集へ
        assert next_step == "gather_info"
        
        # 3. 情報収集
        context.current_node = NodeType.GATHERING
        gathered_info = GatheredInfo(
            collected_files={
                "README.md": FileContent(
                    path="README.md",
                    content="# Sample Project\n\nThis is a sample project.",
                    encoding="utf-8",
                    size=45,
                    last_modified=datetime.now()
                )
            },
            rag_results=[],
            project_context=ProjectContext(
                project_type="Python Application", 
                main_languages=["Python"],
                frameworks=[],
                architecture_pattern="Simple",
                key_directories=["src", "tests", "docs"],
                recent_changes=[]
            ),
            confidence_scores={"file_coverage": 1.0},
            information_gaps=[],
            collection_strategy="minimal"
        )
        context.gathered_info = gathered_info
        
        # 4. 実行フェーズへ
        next_step = orchestrator._after_information_gathering(state)
        assert next_step == "execute"
        
        # 5. 評価・継続フェーズ
        context.current_node = NodeType.EVALUATION
        from codecrafter.prompts.four_node_context import EvaluationResult
        evaluation_result = EvaluationResult(
            success_status=True,
            completion_percentage=1.0,
            next_action=NextAction.COMPLETE,
            quality_assessment="良好",
            user_satisfaction_prediction=0.95
        )
        context.evaluation = evaluation_result
        
        # 6. 完了判定
        final_step = orchestrator._after_evaluation_continuation(state)
        assert final_step == "complete"


class TestFourNodeEdgeCases:
    """エッジケースとエラーハンドリングのテスト"""
    
    def test_empty_workspace_handling(self):
        """空のワークスペースの処理"""
        state = AgentState(session_id="empty_test")
        state.conversation_history = [
            ConversationMessage(
                role="user",
                content="プロジェクトを作成してください",
                timestamp=datetime.now()
            )
        ]
        state.graph_state = GraphState()
        # workspaceを設定しない状態
        
        orchestrator = FourNodeOrchestrator(state)
        
        # 基本的なワークスペース情報が作成される
        assert orchestrator.four_node_context is not None
        assert orchestrator.four_node_context.workspace_path is not None
    
    def test_malformed_conversation_history(self):
        """不正な対話履歴の処理"""
        state = AgentState(session_id="malformed_test")
        # conversation_historyを設定しない
        state.graph_state = GraphState()
        state.workspace = WorkspaceInfo(path=str(Path.cwd()), files=[])
        
        orchestrator = FourNodeOrchestrator(state)
        
        # エラーなく初期化される
        assert orchestrator.four_node_context is not None
        assert len(orchestrator.four_node_context.task_chain) == 0
    
    def test_invalid_node_transitions(self):
        """無効なノード遷移の処理"""
        state = AgentState(session_id="invalid_test")
        state.conversation_history = [
            ConversationMessage(
                role="user",
                content="テスト",
                timestamp=datetime.now()
            )
        ]
        state.graph_state = GraphState()
        state.workspace = WorkspaceInfo(path=str(Path.cwd()), files=[])
        
        orchestrator = FourNodeOrchestrator(state)
        
        # 無効な状態でも安全に "complete" を返す
        result = orchestrator._after_understanding_planning(None)
        assert result == "complete"
        
        result = orchestrator._after_information_gathering(None)
        assert result == "complete"
        
        result = orchestrator._after_evaluation_continuation(None)
        assert result == "complete"