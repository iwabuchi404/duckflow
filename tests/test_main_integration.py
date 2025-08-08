# tests/test_main_integration.py
"""
メインアプリケーションの統合テスト（V2対応）
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from codecrafter.main_v2 import DuckflowAgentV2 as DuckflowAgent
from codecrafter.state.agent_state import AgentState


class TestDuckflowAgentIntegration:
    """DuckflowAgentの統合テスト (V2)"""
    
    def setup_method(self):
        """各テストメソッド実行前の初期化"""
        self.mock_config = Mock()
        self.mock_config.security.require_approval = {"file_write": False}
        self.mock_config.llm.provider = "test"
    
    @patch('codecrafter.main_v2.config_manager')
    @patch('codecrafter.main_v2.rich_ui')
    def test_agent_initialization(self, mock_ui, mock_config_manager):
        """エージェント初期化のテスト"""
        mock_config_manager.load_config.return_value = self.mock_config
        mock_config_manager.is_debug_mode.return_value = False
        
        agent = DuckflowAgent()
        
        assert agent.config == self.mock_config
        assert isinstance(agent.state, AgentState)
        assert agent.running is True
        assert agent.state.debug_mode is False
    
    @patch('codecrafter.main_v2.config_manager')
    @patch('codecrafter.main_v2.rich_ui')
    def test_command_processing_quit(self, mock_ui, mock_config_manager):
        """終了コマンドの処理テスト"""
        mock_config_manager.load_config.return_value = self.mock_config
        mock_config_manager.is_debug_mode.return_value = False
        
        agent = DuckflowAgent()
        
        # quit コマンドのテスト
        agent._process_command("quit")
        assert agent.running is False
        
        # exit コマンドのテスト
        agent.running = True
        agent._process_command("exit")
        assert agent.running is False
        
        # q コマンドのテスト
        agent.running = True
        agent._process_command("q")
        assert agent.running is False
    
    @patch('codecrafter.main_v2.config_manager')
    @patch('codecrafter.main_v2.rich_ui')
    def test_command_processing_help(self, mock_ui, mock_config_manager):
        """ヘルプコマンドの処理テスト"""
        mock_config_manager.load_config.return_value = self.mock_config
        mock_config_manager.is_debug_mode.return_value = False
        
        agent = DuckflowAgent()
        agent._process_command("help")
        
        # ヘルプパネルが表示される
        mock_ui.print_panel.assert_called_once()
        call_args = mock_ui.print_panel.call_args
        assert "利用可能なコマンド" in call_args[0][0]
    
    @patch('codecrafter.main_v2.config_manager')
    @patch('codecrafter.main_v2.rich_ui')
    def test_command_processing_status(self, mock_ui, mock_config_manager):
        """ステータスコマンドの処理テスト"""
        mock_config_manager.load_config.return_value = self.mock_config
        mock_config_manager.is_debug_mode.return_value = False
        
        agent = DuckflowAgent()
        agent._process_command("status")
        
        # ステータスパネルが表示される
        mock_ui.print_panel.assert_called_once()
        call_args = mock_ui.print_panel.call_args
        assert "セッション情報" in call_args[0][0]
    
    @patch('codecrafter.main_v2.file_tools')
    @patch('codecrafter.main_v2.config_manager')
    @patch('codecrafter.main_v2.rich_ui')
    def test_file_operations_read(self, mock_ui, mock_config_manager, mock_file_tools):
        """ファイル読み込みコマンドのテスト"""
        mock_config_manager.load_config.return_value = self.mock_config
        mock_config_manager.is_debug_mode.return_value = False
        mock_file_tools.read_file.return_value = "テストファイルの内容"
        
        agent = DuckflowAgent()
        agent._process_command("read test.txt")
        
        mock_file_tools.read_file.assert_called_once_with("test.txt")
        mock_ui.print_file_content.assert_called_once()
        mock_ui.print_success.assert_called_once()
    
    @patch('codecrafter.main_v2.file_tools')
    @patch('codecrafter.main_v2.config_manager')
    @patch('codecrafter.main_v2.rich_ui')
    def test_file_operations_list(self, mock_ui, mock_config_manager, mock_file_tools):
        """ファイル一覧コマンドのテスト"""
        mock_config_manager.load_config.return_value = self.mock_config
        mock_config_manager.is_debug_mode.return_value = False
        mock_file_tools.list_files.return_value = [
            {"name": "file1.txt", "type": "file"},
            {"name": "dir1", "type": "directory"}
        ]
        
        agent = DuckflowAgent()
        agent._process_command("ls")
        
        mock_file_tools.list_files.assert_called_once_with(".")
        mock_ui.print_file_list.assert_called_once()
    
    @patch('codecrafter.main_v2.GraphOrchestrator')
    @patch('codecrafter.main_v2.config_manager')
    @patch('codecrafter.main_v2.rich_ui')
    def test_ai_conversation_handling(self, mock_ui, mock_config_manager, mock_orchestrator):
        """AI対話の処理テスト（LangGraph経由）"""
        mock_config_manager.load_config.return_value = self.mock_config
        mock_config_manager.is_debug_mode.return_value = False
        
        # orchestratorのモック
        mock_instance = mock_orchestrator.return_value
        
        agent = DuckflowAgent()
        agent._process_command("Hello, AI!")
        
        # LangGraphのオーケストレーションが呼ばれる
        mock_instance.run_conversation.assert_called_once_with("Hello, AI!")
    
    @patch('codecrafter.main_v2.GraphOrchestrator')
    @patch('codecrafter.main_v2.config_manager')
    @patch('codecrafter.main_v2.rich_ui')
    def test_file_operation_instruction_parsing(self, mock_ui, mock_config_manager, mock_orchestrator):
        """ファイル操作指示の処理テスト（V2はオーケストレーション委譲を確認）"""
        mock_config_manager.load_config.return_value = self.mock_config
        mock_config_manager.is_debug_mode.return_value = False
        mock_instance = mock_orchestrator.return_value
        
        agent = DuckflowAgent()
        
        # FILE_OPERATION指示を含む入力を、そのままユーザー入力として渡す
        ai_like_input = (
            "ファイルを作成します。\n\n"
            "FILE_OPERATION:CREATE:hello.py\n"
            "```python\nprint(\"Hello, World!\")\n```\n"
        )
        agent._handle_orchestrated_conversation(ai_like_input)
        
        # オーケストレーションに委譲されていること
        mock_instance.run_conversation.assert_called_once_with(ai_like_input)
    
    @patch('codecrafter.main_v2.config_manager')
    @patch('codecrafter.main_v2.rich_ui')
    def test_language_guessing(self, mock_ui, mock_config_manager):
        """言語推測機能のテスト"""
        mock_config_manager.load_config.return_value = self.mock_config
        mock_config_manager.is_debug_mode.return_value = False
        
        agent = DuckflowAgent()
        
        # 各ファイル拡張子の言語推測テスト
        test_cases = [
            ("test.py", "python"),
            ("script.js", "javascript"),
            ("app.ts", "typescript"),
            ("config.yaml", "yaml"),
            ("README.md", "markdown"),
            ("unknown.xyz", "text"),
        ]
        
        for filename, expected_language in test_cases:
            result = agent._guess_language(filename)
            assert result == expected_language
    
    @patch('codecrafter.main_v2.config_manager')
    @patch('codecrafter.main_v2.rich_ui')
    def test_history_command(self, mock_ui, mock_config_manager):
        """履歴コマンドのテスト"""
        mock_config_manager.load_config.return_value = self.mock_config
        mock_config_manager.is_debug_mode.return_value = False
        
        agent = DuckflowAgent()
        
        # テスト用の対話履歴を追加
        for i in range(5):
            agent.state.add_message("user", f"メッセージ {i}")
        
        agent._process_command("history 3")
        
        # 履歴表示が実行される
        mock_ui.print_conversation_message.assert_called()
        assert mock_ui.print_conversation_message.call_count == 3  # 最新3件


@pytest.mark.integration
class TestEndToEndWorkflow:
    """エンドツーエンドワークフローのテスト（V2）"""
    
    @patch('codecrafter.main_v2.GraphOrchestrator')
    @patch('codecrafter.main_v2.config_manager')
    @patch('codecrafter.main_v2.rich_ui')
    def test_complete_file_creation_workflow(self, mock_ui, mock_config_manager, mock_orchestrator):
        """完全なファイル作成ワークフローのテスト（オーケストレーション呼び出し）"""
        # モックの設定
        mock_config = Mock()
        mock_config.security.require_approval = {"file_write": False}
        mock_config.llm.provider = "test"
        mock_config_manager.load_config.return_value = mock_config
        mock_config_manager.is_debug_mode.return_value = False
        
        mock_instance = mock_orchestrator.return_value
        
        # エージェントの作成と実行
        agent = DuckflowAgent()
        
        # ユーザー入力をシミュレート
        user_input = "Create a Python script that prints Hello, CodeCrafter!"
        agent._handle_orchestrated_conversation(user_input)
        
        # 1. LangGraphが呼び出された
        mock_instance.run_conversation.assert_called_once_with(user_input)