"""
Test suite for CompanionCore approval system integration
CompanionCoreの承認システム統合テスト
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from companion.core import CompanionCore
from companion.approval_system import (
    ApprovalGate, ApprovalConfig, ApprovalMode, ApprovalResponse
)


class TestCompanionCoreApprovalIntegration:
    """CompanionCoreの承認システム統合テスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.py")
        
        # rich_uiとllm_managerをモック化
        self.rich_ui_patcher = patch('companion.core.rich_ui')
        self.mock_rich_ui = self.rich_ui_patcher.start()
        
        self.llm_manager_patcher = patch('companion.core.llm_manager')
        self.mock_llm_manager = self.llm_manager_patcher.start()
        
        # timeをモック化（テスト高速化）
        self.time_patcher = patch('companion.core.time')
        self.mock_time = self.time_patcher.start()
        
        # CompanionCoreインスタンス
        self.companion = CompanionCore()
        
        # 承認ゲートをモック化
        self.mock_approval_gate = Mock(spec=ApprovalGate)
        self.companion.approval_gate = self.mock_approval_gate
        self.companion.file_ops.approval_gate = self.mock_approval_gate
    
    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        self.rich_ui_patcher.stop()
        self.llm_manager_patcher.stop()
        self.time_patcher.stop()
        
        # テンポラリファイルをクリーンアップ
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        os.rmdir(self.temp_dir)
    
    def test_file_creation_with_approval_granted(self):
        """ファイル作成（承認あり）のエンドツーエンドテスト"""
        # LLMの応答をモック
        self.mock_llm_manager.chat.return_value = """操作: create
ファイル名: test.py
内容: print("Hello, World!")"""
        
        # 承認ゲートが承認を返すようにモック
        self.mock_approval_gate.is_approval_required.return_value = True
        self.mock_approval_gate.request_approval.return_value = ApprovalResponse(approved=True)
        
        # ファイル操作を実行
        result = self.companion._handle_file_operation("test.pyファイルを作成して")
        
        # 結果を確認
        assert "✅" in result
        assert "test.py" in result
        assert "作成しました" in result
        assert "Hello, World!" in result
        
        # 承認が要求されたことを確認
        self.mock_approval_gate.request_approval.assert_called_once()
        
        # ファイルが実際に作成されたことを確認（現在のディレクトリまたはテンポラリディレクトリ）
        test_py_exists = os.path.exists("test.py") or os.path.exists(self.test_file)
        assert test_py_exists
        
        # ファイル内容を確認
        if os.path.exists("test.py"):
            with open("test.py", 'r') as f:
                assert f.read() == 'print("Hello, World!")'
            os.remove("test.py")  # クリーンアップ
        elif os.path.exists(self.test_file):
            with open(self.test_file, 'r') as f:
                assert f.read() == 'print("Hello, World!")'
    
    def test_file_creation_with_approval_denied(self):
        """ファイル作成（承認拒否）のエンドツーエンドテスト"""
        # LLMの応答をモック
        self.mock_llm_manager.chat.return_value = """操作: create
ファイル名: test.py
内容: print("Hello, World!")"""
        
        # 承認ゲートが拒否を返すようにモック
        self.mock_approval_gate.is_approval_required.return_value = True
        self.mock_approval_gate.request_approval.return_value = ApprovalResponse(
            approved=False, reason="ユーザー拒否"
        )
        
        # ファイル操作を実行
        result = self.companion._handle_file_operation("test.pyファイルを作成して")
        
        # 結果を確認
        assert "分かりました" in result
        assert "作成は行いません" in result
        assert "代わりに" in result
        assert "プレビュー" in result or "安全な場所" in result
        
        # 承認が要求されたことを確認
        self.mock_approval_gate.request_approval.assert_called_once()
        
        # ファイルが作成されていないことを確認
        assert not os.path.exists(self.test_file)
    
    def test_file_write_with_approval_granted(self):
        """ファイル書き込み（承認あり）のエンドツーエンドテスト"""
        # 既存ファイルを作成
        with open(self.test_file, 'w') as f:
            f.write("original content")
        
        # LLMの応答をモック
        self.mock_llm_manager.chat.return_value = """操作: write
ファイル名: test.py
内容: print("Updated content")"""
        
        # 承認ゲートが承認を返すようにモック
        self.mock_approval_gate.is_approval_required.return_value = True
        self.mock_approval_gate.request_approval.return_value = ApprovalResponse(approved=True)
        
        # ファイル操作を実行
        result = self.companion._handle_file_operation("test.pyを更新して")
        
        # 結果を確認
        assert "✅" in result
        assert "書き込みました" in result
        assert "Updated content" in result
        
        # ファイル内容が更新されたことを確認
        with open(self.test_file, 'r') as f:
            assert f.read() == 'print("Updated content")'
    
    def test_file_write_with_approval_denied(self):
        """ファイル書き込み（承認拒否）のエンドツーエンドテスト"""
        # 既存ファイルを作成
        original_content = "original content"
        with open(self.test_file, 'w') as f:
            f.write(original_content)
        
        # LLMの応答をモック
        self.mock_llm_manager.chat.return_value = """操作: write
ファイル名: test.py
内容: print("Updated content")"""
        
        # 承認ゲートが拒否を返すようにモック
        self.mock_approval_gate.is_approval_required.return_value = True
        self.mock_approval_gate.request_approval.return_value = ApprovalResponse(
            approved=False, reason="ユーザー拒否"
        )
        
        # ファイル操作を実行
        result = self.companion._handle_file_operation("test.pyを更新して")
        
        # 結果を確認
        assert "分かりました" in result
        assert "書き込みは行いません" in result
        assert "代わりに" in result
        
        # ファイル内容が変更されていないことを確認
        with open(self.test_file, 'r') as f:
            assert f.read() == original_content
    
    def test_file_read_bypasses_approval(self):
        """ファイル読み取りが承認をバイパスすることのエンドツーエンドテスト"""
        # テストファイルを作成
        test_content = "test file content"
        with open(self.test_file, 'w') as f:
            f.write(test_content)
        
        # LLMの応答をモック（フルパスを使用）
        self.mock_llm_manager.chat.return_value = f"""操作: read
ファイル名: {self.test_file}
内容: なし"""
        
        # ファイル操作を実行
        result = self.companion._handle_file_operation("test.pyを読んで")
        
        # 結果を確認
        assert "✅" in result
        assert "読み取りました" in result
        assert test_content in result
        
        # 承認は要求されない
        self.mock_approval_gate.request_approval.assert_not_called()
    
    def test_file_list_bypasses_approval(self):
        """ファイル一覧が承認をバイパスすることのエンドツーエンドテスト"""
        # テストファイルを作成
        with open(self.test_file, 'w') as f:
            f.write("test content")
        
        # LLMの応答をモック
        self.mock_llm_manager.chat.return_value = f"""操作: list
ファイル名: {self.temp_dir}
内容: なし"""
        
        # ファイル操作を実行
        result = self.companion._handle_file_operation("ファイル一覧を表示して")
        
        # 結果を確認
        assert "✅" in result
        assert "ファイル一覧" in result
        assert "test.py" in result
        
        # 承認は要求されない
        self.mock_approval_gate.request_approval.assert_not_called()
    
    def test_approval_failure_handling(self):
        """承認失敗時の自然な応答のテスト"""
        operation_info = {
            "operation": "create",
            "filename": "test.py",
            "content": "print('test')"
        }
        
        # 承認拒否の結果をシミュレート
        result = {
            "success": False,
            "reason": "approval_denied",
            "message": "ファイル作成が拒否されました"
        }
        
        response = self.companion._handle_file_operation_failure(result, "create", "test.py")
        
        assert "分かりました" in response
        assert "作成は行いません" in response
        assert "代わりに" in response
        assert "プレビュー" in response
    
    def test_approval_alternative_suggestions(self):
        """承認拒否時の代替案提案のテスト"""
        # ファイル作成の代替案
        create_suggestion = self.companion._suggest_approval_alternatives("create", "test.py")
        assert "プレビュー" in create_suggestion
        assert "安全な場所" in create_suggestion
        assert "手順を詳しく説明" in create_suggestion
        
        # ファイル書き込みの代替案
        write_suggestion = self.companion._suggest_approval_alternatives("write", "test.py")
        assert "プレビュー" in write_suggestion
        assert "バックアップ" in write_suggestion
        assert "手順を段階的に説明" in write_suggestion
    
    def test_alternative_selection_handling(self):
        """代替案選択処理のテスト"""
        # プレビュー選択（create操作）
        result1 = self.companion.handle_approval_alternative_selection(
            "1", "create", "test.py", "print('hello')"
        )
        assert "プレビュー" in result1 or "予定だった内容" in result1
        assert "print('hello')" in result1
        
        # 安全な場所選択（create操作）
        result2 = self.companion.handle_approval_alternative_selection(
            "2", "create", "test.py", "print('hello')"
        )
        assert "preview_test.py" in result2 or "安全な場所" in result2
        
        # 手順説明選択（create操作）
        result3 = self.companion.handle_approval_alternative_selection(
            "3", "create", "test.py", "print('hello')"
        )
        assert "手順" in result3
        assert "テキストエディタ" in result3
        
        # 無効な選択
        result4 = self.companion.handle_approval_alternative_selection(
            "invalid", "create", "test.py", "print('hello')"
        )
        assert "番号で教えてください" in result4


class TestCompanionCoreApprovalModes:
    """CompanionCoreの承認モード別テスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.py")
        
        # rich_uiとllm_managerをモック化
        self.rich_ui_patcher = patch('companion.core.rich_ui')
        self.mock_rich_ui = self.rich_ui_patcher.start()
        
        self.llm_manager_patcher = patch('companion.core.llm_manager')
        self.mock_llm_manager = self.llm_manager_patcher.start()
        
        # timeをモック化
        self.time_patcher = patch('companion.core.time')
        self.mock_time = self.time_patcher.start()
    
    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        self.rich_ui_patcher.stop()
        self.llm_manager_patcher.stop()
        self.time_patcher.stop()
        
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        os.rmdir(self.temp_dir)
    
    def test_trusted_mode_allows_file_operations(self):
        """TRUSTEDモードでファイル操作が許可されることのテスト"""
        # TRUSTEDモードの設定
        config = ApprovalConfig(mode=ApprovalMode.TRUSTED)
        companion = CompanionCore()
        companion.approval_gate.update_config(config)
        
        # LLMの応答をモック
        self.mock_llm_manager.chat.return_value = """操作: create
ファイル名: test.py
内容: print("Hello, World!")"""
        
        # ファイル操作を実行
        result = companion._handle_file_operation("test.pyファイルを作成して")
        
        # 結果を確認（承認なしで成功）
        assert "✅" in result
        assert "作成しました" in result
    
    def test_strict_mode_requires_approval_for_all_operations(self):
        """STRICTモードですべての操作で承認が必要なことのテスト"""
        # STRICTモードの設定
        config = ApprovalConfig(mode=ApprovalMode.STRICT)
        companion = CompanionCore()
        companion.approval_gate.update_config(config)
        
        # 承認UIをモック化して拒否
        with patch.object(companion.approval_gate, 'approval_ui') as mock_ui:
            mock_ui.show_approval_request.return_value = ApprovalResponse(approved=False)
            
            # LLMの応答をモック
            self.mock_llm_manager.chat.return_value = """操作: create
ファイル名: test.py
内容: print("Hello, World!")"""
            
            # ファイル操作を実行
            result = companion._handle_file_operation("test.pyファイルを作成して")
            
            # 結果を確認（拒否される）
            assert "分かりました" in result
            assert "作成は行いません" in result
    
    def test_excluded_path_bypasses_approval(self):
        """除外パスで承認がバイパスされることのテスト"""
        # 除外パス設定
        config = ApprovalConfig(
            mode=ApprovalMode.STRICT,
            excluded_paths=[self.temp_dir]
        )
        companion = CompanionCore()
        companion.approval_gate.update_config(config)
        
        # LLMの応答をモック
        self.mock_llm_manager.chat.return_value = f"""操作: create
ファイル名: {self.test_file}
内容: print("Hello, World!")"""
        
        # ファイル操作を実行
        result = companion._handle_file_operation("test.pyファイルを作成して")
        
        # 結果を確認（除外パスなので承認なしで成功）
        assert "✅" in result
        assert "作成しました" in result


class TestCompanionCoreApprovalConversationFlow:
    """CompanionCoreの承認システム会話フローテスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.temp_dir = tempfile.mkdtemp()
        
        # rich_uiとllm_managerをモック化
        self.rich_ui_patcher = patch('companion.core.rich_ui')
        self.mock_rich_ui = self.rich_ui_patcher.start()
        
        self.llm_manager_patcher = patch('companion.core.llm_manager')
        self.mock_llm_manager = self.llm_manager_patcher.start()
        
        # timeをモック化
        self.time_patcher = patch('companion.core.time')
        self.mock_time = self.time_patcher.start()
        
        self.companion = CompanionCore()
    
    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        self.rich_ui_patcher.stop()
        self.llm_manager_patcher.stop()
        self.time_patcher.stop()
        
        # テンポラリファイルをクリーンアップ
        for file in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, file))
        os.rmdir(self.temp_dir)
    
    def test_natural_conversation_flow_with_approval(self):
        """承認を含む自然な会話フローのテスト"""
        # 承認ゲートをモック化
        mock_gate = Mock()
        mock_gate.is_approval_required.return_value = True
        mock_gate.request_approval.return_value = ApprovalResponse(approved=True)
        self.companion.approval_gate = mock_gate
        self.companion.file_ops.approval_gate = mock_gate
        
        # LLMの応答をモック
        self.mock_llm_manager.chat.return_value = """操作: create
ファイル名: hello.py
内容: print("Hello, World!")"""
        
        # ユーザーメッセージを処理
        result = self.companion._handle_file_operation("Hello Worldを出力するPythonファイルを作ってください")
        
        # 自然な応答が生成されることを確認
        assert "✅" in result
        assert "hello.py" in result
        assert "作成しました" in result
        assert "Hello, World!" in result
        assert "何か他にお手伝い" in result
    
    def test_natural_conversation_flow_with_rejection(self):
        """拒否を含む自然な会話フローのテスト"""
        # 承認ゲートをモック化
        mock_gate = Mock()
        mock_gate.is_approval_required.return_value = True
        mock_gate.request_approval.return_value = ApprovalResponse(
            approved=False, reason="ユーザーが安全性を懸念"
        )
        self.companion.approval_gate = mock_gate
        self.companion.file_ops.approval_gate = mock_gate
        
        # LLMの応答をモック
        self.mock_llm_manager.chat.return_value = """操作: create
ファイル名: script.py
内容: import os; os.system('rm -rf /')"""
        
        # ユーザーメッセージを処理
        result = self.companion._handle_file_operation("危険なスクリプトを作って")
        
        # 自然な拒否応答が生成されることを確認
        assert "分かりました" in result
        assert "作成は行いません" in result
        assert "代わりに" in result
        assert "お手伝いできること" in result
    
    def test_conversation_continues_after_approval_decision(self):
        """承認決定後も会話が自然に続くことのテスト"""
        # 承認ゲートをモック化
        mock_gate = Mock()
        mock_gate.is_approval_required.return_value = True
        
        # 最初は拒否、次は承認
        mock_gate.request_approval.side_effect = [
            ApprovalResponse(approved=False, reason="初回拒否"),
            ApprovalResponse(approved=True)
        ]
        
        self.companion.approval_gate = mock_gate
        self.companion.file_ops.approval_gate = mock_gate
        
        # LLMの応答をモック
        self.mock_llm_manager.chat.return_value = """操作: create
ファイル名: test.py
内容: print("test")"""
        
        # 1回目：拒否
        result1 = self.companion._handle_file_operation("test.pyを作って")
        assert "分かりました" in result1
        assert "作成は行いません" in result1
        
        # 2回目：承認
        result2 = self.companion._handle_file_operation("test.pyを作って")
        assert "✅" in result2
        assert "作成しました" in result2
        
        # 両方とも自然な会話の継続を促す内容が含まれる
        assert "お手伝い" in result1 or "何か" in result1
        assert "お手伝い" in result2 or "何か" in result2