# tests/test_run_tests.py
"""
run_testsツールのテスト
"""
import pytest
from unittest.mock import patch, Mock
from codecrafter.tools.file_tools import file_tools, FileOperationError


class TestRunTestsTool:
    """run_testsツールのテスト"""
    
    @patch('codecrafter.tools.file_tools.subprocess.run')
    @patch('codecrafter.tools.file_tools.os.path.exists')
    def test_run_tests_success(self, mock_exists, mock_run):
        """成功したテスト実行のテスト"""
        mock_exists.return_value = True
        
        # 成功した pytest の出力をシミュレート
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "5 passed in 1.23s"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        result = file_tools.run_tests("tests/", verbose=False)
        
        assert result["success"] is True
        assert result["passed"] == 5
        assert result["failed"] == 0
        assert result["errors"] == 0
        assert result["total_tests"] == 5
        assert result["duration"] > 0
        assert "passed" in result["output"]
    
    @patch('codecrafter.tools.file_tools.subprocess.run')
    @patch('codecrafter.tools.file_tools.os.path.exists')
    def test_run_tests_with_failures(self, mock_exists, mock_run):
        """失敗を含むテスト実行のテスト"""
        mock_exists.return_value = True
        
        # 失敗を含む pytest の出力をシミュレート
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = """FAILED tests/test_example.py::test_failure - AssertionError
3 passed, 2 failed in 2.45s"""
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        result = file_tools.run_tests("tests/", verbose=False)
        
        assert result["success"] is False
        assert result["passed"] == 3
        assert result["failed"] == 2
        assert result["total_tests"] == 5
        assert len(result["failed_tests"]) > 0
    
    @patch('codecrafter.tools.file_tools.subprocess.run')
    @patch('codecrafter.tools.file_tools.os.path.exists')
    def test_run_tests_with_errors(self, mock_exists, mock_run):
        """エラーを含むテスト実行のテスト"""
        mock_exists.return_value = True
        
        # エラーを含む pytest の出力をシミュレート
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "2 passed, 1 failed, 1 error in 1.50s"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        result = file_tools.run_tests("tests/", verbose=False)
        
        assert result["success"] is False
        assert result["passed"] == 2
        assert result["failed"] == 1
        assert result["errors"] == 1
        assert result["total_tests"] == 4
    
    @patch('codecrafter.tools.file_tools.subprocess.run')
    @patch('codecrafter.tools.file_tools.os.path.exists')
    def test_run_tests_verbose(self, mock_exists, mock_run):
        """詳細モードでのテスト実行"""
        mock_exists.return_value = True
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "3 passed in 1.00s"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        file_tools.run_tests("tests/", verbose=True)
        
        # verbose フラグが適切に渡されることを確認
        called_args = mock_run.call_args[0][0]
        assert "-v" in called_args
    
    @patch('codecrafter.tools.file_tools.os.path.exists')
    def test_run_tests_no_test_directory(self, mock_exists):
        """テストディレクトリが存在しない場合のテスト"""
        mock_exists.return_value = False
        
        with pytest.raises(FileOperationError) as exc_info:
            file_tools.run_tests("nonexistent_tests/")
        
        assert "テストディレクトリが見つかりません" in str(exc_info.value)
    
    @patch('codecrafter.tools.file_tools.subprocess.run')
    @patch('codecrafter.tools.file_tools.os.path.exists')
    def test_run_tests_timeout(self, mock_exists, mock_run):
        """タイムアウト処理のテスト"""
        mock_exists.return_value = True
        
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("pytest", 300)
        
        with pytest.raises(FileOperationError) as exc_info:
            file_tools.run_tests("tests/")
        
        assert "タイムアウト" in str(exc_info.value)
    
    @patch('codecrafter.tools.file_tools.subprocess.run')
    @patch('codecrafter.tools.file_tools.os.path.exists')
    def test_run_tests_pytest_not_found(self, mock_exists, mock_run):
        """pytest が見つからない場合のテスト"""
        mock_exists.return_value = True
        mock_run.side_effect = FileNotFoundError()
        
        with pytest.raises(FileOperationError) as exc_info:
            file_tools.run_tests("tests/")
        
        assert "pytest" in str(exc_info.value)
    
    def test_parse_pytest_output_complex(self):
        """複雑なpytest出力の解析テスト"""
        output = """
====================== FAILURES ======================
FAILED tests/test_example.py::test_one - AssertionError: expected 1, got 2
FAILED tests/test_another.py::test_two - ValueError: invalid input
====================== ERRORS ======================
ERROR tests/test_error.py::test_broken - ImportError: module not found
======================== short test summary info ========================
FAILED tests/test_example.py::test_one - AssertionError
FAILED tests/test_another.py::test_two - ValueError
ERROR tests/test_error.py::test_broken - ImportError
==================== 3 passed, 2 failed, 1 error in 5.67s ====================
"""
        
        result = file_tools._parse_pytest_output(1, output, "", 5.67)
        
        assert result["success"] is False
        assert result["passed"] == 3
        assert result["failed"] == 2
        assert result["errors"] == 1
        assert result["total_tests"] == 6
        assert result["duration"] == 5.67
    
    def test_extract_failed_tests_details(self):
        """失敗したテストの詳細抽出テスト"""
        output = """
FAILED tests/test_example.py::test_failure - AssertionError: 1 != 2
        Expected: 1
        Actual: 2
        
FAILED tests/test_another.py::test_error - ValueError: Invalid value
        Value should be positive
        
3 passed, 2 failed in 2.34s
"""
        
        failed_tests = file_tools._extract_failed_tests(output)
        
        assert len(failed_tests) == 2
        assert failed_tests[0]["name"] == "tests/test_example.py::test_failure"
        assert "AssertionError" in failed_tests[0]["error"]
        assert failed_tests[1]["name"] == "tests/test_another.py::test_error"
        assert "ValueError" in failed_tests[1]["error"]
    
    def test_run_tests_default_path(self):
        """デフォルトパスでのテスト実行"""
        with patch('codecrafter.tools.file_tools.os.path.exists') as mock_exists:
            with patch('codecrafter.tools.file_tools.subprocess.run') as mock_run:
                mock_exists.return_value = True
                mock_result = Mock()
                mock_result.returncode = 0
                mock_result.stdout = "5 passed in 1.23s"
                mock_result.stderr = ""
                mock_run.return_value = mock_result
                
                file_tools.run_tests()  # パス指定なし
                
                # デフォルトで "tests/" が使用されることを確認
                mock_exists.assert_called_with("tests/")
    
    def test_run_tests_custom_path(self):
        """カスタムパスでのテスト実行"""
        with patch('codecrafter.tools.file_tools.os.path.exists') as mock_exists:
            with patch('codecrafter.tools.file_tools.subprocess.run') as mock_run:
                mock_exists.return_value = True
                mock_result = Mock()
                mock_result.returncode = 0
                mock_result.stdout = "3 passed in 0.89s"
                mock_result.stderr = ""
                mock_run.return_value = mock_result
                
                file_tools.run_tests("custom_tests/")
                
                # カスタムパスが使用されることを確認
                mock_exists.assert_called_with("custom_tests/")


class TestPytestOutputParsing:
    """pytest出力解析の詳細テスト"""
    
    def test_parse_empty_output(self):
        """空の出力の解析"""
        result = file_tools._parse_pytest_output(0, "", "", 0.1)
        
        assert result["success"] is True
        assert result["total_tests"] == 0
        assert result["passed"] == 0
        assert result["failed"] == 0
        assert result["errors"] == 0
        assert result["skipped"] == 0
    
    def test_parse_skipped_tests(self):
        """スキップされたテストを含む出力の解析"""
        output = "2 passed, 1 skipped in 1.23s"
        result = file_tools._parse_pytest_output(0, output, "", 1.23)
        
        assert result["success"] is True
        assert result["passed"] == 2
        assert result["skipped"] == 1
        assert result["total_tests"] == 3
    
    def test_parse_all_result_types(self):
        """全ての結果タイプを含む出力の解析"""
        output = "10 passed, 3 failed, 2 error, 1 skipped in 4.56s"
        result = file_tools._parse_pytest_output(1, output, "", 4.56)
        
        assert result["success"] is False
        assert result["passed"] == 10
        assert result["failed"] == 3
        assert result["errors"] == 2
        assert result["skipped"] == 1
        assert result["total_tests"] == 16
    
    def test_parse_no_summary_line(self):
        """サマリー行がない出力の解析"""
        output = "Some test output without summary"
        result = file_tools._parse_pytest_output(0, output, "", 1.0)
        
        assert result["success"] is True
        assert result["total_tests"] == 0
        assert all(result[key] == 0 for key in ["passed", "failed", "errors", "skipped"])