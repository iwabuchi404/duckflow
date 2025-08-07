# tests/test_main_integration.py
"""
メインアプリケーションの統合テスト
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from codecrafter.main import DuckflowAgent
from codecrafter.state.agent_state import AgentState


class TestDuckflowAgentIntegration:
    """DuckflowAgentの統合テスト"""
    
    def setup_method(self):
        """各テストメソッド実行前の初期化"""
        self.mock_config = Mock()
        self.mock_config.security.require_approval = {"file_write": False}
        self.mock_config.llm.provider = "test"
    
    @patch('codecrafter.main.config_manager')
    @patch('codecrafter.main.rich_ui')
    def test_agent_initialization(self, mock_ui, mock_config_manager):
        """エージェント初期化のテスト"""
        mock_config_manager.load_config.return_value = self.mock_config
        mock_config_manager.is_debug_mode.return_value = False
        
        agent = DuckflowAgent()
        
        assert agent.config == self.mock_config
        assert isinstance(agent.state, AgentState)
        assert agent.running is True
        assert agent.debug_mode is False
    
    @patch('codecrafter.main.config_manager')
    @patch('codecrafter.main.rich_ui')
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
    
    @patch('codecrafter.main.config_manager')
    @patch('codecrafter.main.rich_ui')
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
    
    @patch('codecrafter.main.config_manager')
    @patch('codecrafter.main.rich_ui')
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
    
    @patch('codecrafter.main.config_manager')
    @patch('codecrafter.main.rich_ui')
    @patch('codecrafter.main.file_tools')
    def test_file_operations_read(self, mock_file_tools, mock_ui, mock_config_manager):
        """ファイル読み込みコマンドのテスト"""
        mock_config_manager.load_config.return_value = self.mock_config
        mock_config_manager.is_debug_mode.return_value = False
        mock_file_tools.read_file.return_value = "テストファイルの内容"
        
        agent = DuckflowAgent()
        agent._process_command("read test.txt")
        
        mock_file_tools.read_file.assert_called_once_with("test.txt")
        mock_ui.print_file_content.assert_called_once()
        mock_ui.print_success.assert_called_once()
    
    @patch('codecrafter.main.config_manager')
    @patch('codecrafter.main.rich_ui')
    @patch('codecrafter.main.file_tools')
    def test_file_operations_list(self, mock_file_tools, mock_ui, mock_config_manager):
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
    
    @patch('codecrafter.main.config_manager')
    @patch('codecrafter.main.rich_ui')
    @patch('codecrafter.main.llm_manager')
    def test_ai_conversation_handling(self, mock_llm_manager, mock_ui, mock_config_manager):
        """AI対話の処理テスト"""
        mock_config_manager.load_config.return_value = self.mock_config
        mock_config_manager.is_debug_mode.return_value = False
        mock_llm_manager.chat.return_value = "AIからの応答です"
        mock_llm_manager.get_provider_name.return_value = "test_provider"
        
        agent = DuckflowAgent()
        agent._process_command("Hello, AI!")
        
        # LLMが呼び出される
        mock_llm_manager.chat.assert_called_once()
        
        # 対話履歴に追加される
        assert len(agent.state.conversation_history) == 2  # user + assistant
        assert agent.state.conversation_history[0].role == "user"
        assert agent.state.conversation_history[0].content == "Hello, AI!"
        assert agent.state.conversation_history[1].role == "assistant"
        assert agent.state.conversation_history[1].content == "AIからの応答です"
    
    @patch('codecrafter.main.config_manager')
    @patch('codecrafter.main.rich_ui')
    @patch('codecrafter.main.file_tools')
    def test_file_operation_instruction_parsing(self, mock_file_tools, mock_ui, mock_config_manager):
        """ファイル操作指示の解析テスト"""
        mock_config_manager.load_config.return_value = self.mock_config
        mock_config_manager.is_debug_mode.return_value = False
        mock_file_tools.write_file.return_value = {"size": 100, "backup_created": False}
        
        agent = DuckflowAgent()
        
        # ファイル作成指示を含むAI応答をシミュレート
        ai_response = """
        ファイルを作成します。

        FILE_OPERATION:CREATE:hello.py
        ```python
        print("Hello, World!")
        ```
        """
        
        agent._execute_ai_instructions(ai_response, "Python script to print hello")
        
        # ファイル作成が実行される
        mock_file_tools.write_file.assert_called_once_with("hello.py", 'print("Hello, World!")')
    
    @patch('codecrafter.main.config_manager')
    @patch('codecrafter.main.rich_ui')
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
    
    @patch('codecrafter.main.config_manager')
    @patch('codecrafter.main.rich_ui')
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
    """エンドツーエンドワークフローのテスト"""
    
    @patch('codecrafter.main.config_manager')
    @patch('codecrafter.main.rich_ui')
    @patch('codecrafter.main.file_tools')
    @patch('codecrafter.main.llm_manager')
    def test_complete_file_creation_workflow(self, mock_llm_manager, mock_file_tools, mock_ui, mock_config_manager):
        """完全なファイル作成ワークフローのテスト"""
        # モックの設定
        mock_config = Mock()
        mock_config.security.require_approval = {"file_write": False}
        mock_config.llm.provider = "test"
        mock_config_manager.load_config.return_value = mock_config
        mock_config_manager.is_debug_mode.return_value = False
        
        mock_llm_manager.chat.return_value = """
        Pythonスクリプトを作成します。

        FILE_OPERATION:CREATE:hello.py
        ```python
        def main():
            print("Hello, CodeCrafter!")

        if __name__ == "__main__":
            main()
        ```
        """
        mock_llm_manager.get_provider_name.return_value = "test"
        mock_file_tools.write_file.return_value = {"size": 100, "backup_created": False}
        
        # エージェントの作成と実行
        agent = DuckflowAgent()
        
        # ユーザー入力をシミュレート
        user_input = "Create a Python script that prints Hello, CodeCrafter!"
        agent._handle_ai_conversation(user_input)
        
        # 検証
        # 1. LLMが呼び出された
        mock_llm_manager.chat.assert_called_once()
        
        # 2. ファイルが作成された
        mock_file_tools.write_file.assert_called_once()
        call_args = mock_file_tools.write_file.call_args[0]
        assert call_args[0] == "hello.py"
        assert "Hello, CodeCrafter!" in call_args[1]
        
        # 3. 対話履歴に記録された
        assert len(agent.state.conversation_history) == 2
        assert agent.state.conversation_history[0].content == user_input
        assert agent.state.conversation_history[0].role == "user"
        assert agent.state.conversation_history[1].role == "assistant"