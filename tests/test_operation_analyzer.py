"""
Test suite for OperationAnalyzer class
OperationAnalyzerクラスのテスト
"""

import pytest
from companion.approval_system import (
    OperationAnalyzer, OperationInfo, RiskLevel, OperationType
)


class TestOperationAnalyzer:
    """OperationAnalyzerクラスのテスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化"""
        self.analyzer = OperationAnalyzer()
    
    def test_initialization(self):
        """初期化のテスト"""
        analyzer = OperationAnalyzer()
        assert analyzer.risk_mapping is not None
        assert len(analyzer.risk_mapping) > 0
    
    def test_analyze_operation_create_file(self):
        """ファイル作成操作の分析テスト"""
        params = {
            'target': 'test.py',
            'content': 'print("Hello World")'
        }
        
        result = self.analyzer.analyze_operation(OperationType.CREATE_FILE, params)
        
        assert isinstance(result, OperationInfo)
        assert result.operation_type == OperationType.CREATE_FILE
        assert result.target == 'test.py'
        assert result.risk_level == RiskLevel.HIGH_RISK
        assert 'test.py' in result.description
        assert result.preview == 'print("Hello World")'
        assert result.details == params
    
    def test_analyze_operation_read_file(self):
        """ファイル読み取り操作の分析テスト"""
        params = {
            'target': 'readme.txt'
        }
        
        result = self.analyzer.analyze_operation(OperationType.READ_FILE, params)
        
        assert result.operation_type == OperationType.READ_FILE
        assert result.target == 'readme.txt'
        assert result.risk_level == RiskLevel.LOW_RISK
        assert 'readme.txt' in result.description
        assert result.preview is None
    
    def test_analyze_operation_execute_python(self):
        """Python実行操作の分析テスト"""
        params = {
            'target': 'script.py',
            'command': 'python script.py'
        }
        
        result = self.analyzer.analyze_operation(OperationType.EXECUTE_PYTHON, params)
        
        assert result.operation_type == OperationType.EXECUTE_PYTHON
        assert result.target == 'script.py'
        assert result.risk_level == RiskLevel.HIGH_RISK
        assert 'script.py' in result.description
        assert 'python script.py' in result.preview
    
    def test_analyze_operation_invalid_operation_type(self):
        """無効な操作タイプのテスト"""
        params = {'target': 'test.py'}
        
        with pytest.raises(ValueError, match="operation_type は必須です"):
            self.analyzer.analyze_operation("", params)
    
    def test_analyze_operation_invalid_params_type(self):
        """無効なパラメータタイプのテスト"""
        with pytest.raises(ValueError, match="params は辞書である必要があります"):
            self.analyzer.analyze_operation(OperationType.CREATE_FILE, "invalid")
    
    def test_analyze_operation_missing_target(self):
        """ターゲットが欠けている場合のテスト"""
        params = {'content': 'test'}
        
        with pytest.raises(ValueError, match="params に 'target' は必須です"):
            self.analyzer.analyze_operation(OperationType.CREATE_FILE, params)
    
    def test_classify_risk_basic_mapping(self):
        """基本的なリスク分類のテスト"""
        # 低リスク操作
        assert self.analyzer.classify_risk(OperationType.READ_FILE, 'test.txt') == RiskLevel.LOW_RISK
        assert self.analyzer.classify_risk(OperationType.LIST_FILES, '.') == RiskLevel.LOW_RISK
        
        # 高リスク操作
        assert self.analyzer.classify_risk(OperationType.CREATE_FILE, 'test.py') == RiskLevel.HIGH_RISK
        assert self.analyzer.classify_risk(OperationType.WRITE_FILE, 'test.py') == RiskLevel.HIGH_RISK
        assert self.analyzer.classify_risk(OperationType.EXECUTE_PYTHON, 'script.py') == RiskLevel.HIGH_RISK
        
        # 重要リスク操作
        assert self.analyzer.classify_risk(OperationType.INSTALL_PACKAGE, 'numpy') == RiskLevel.CRITICAL_RISK
        assert self.analyzer.classify_risk(OperationType.MODIFY_SYSTEM, 'config') == RiskLevel.CRITICAL_RISK
    
    def test_classify_risk_dangerous_paths(self):
        """危険なパスに対するリスク上昇のテスト"""
        # システムディレクトリ
        assert self.analyzer.classify_risk(OperationType.CREATE_FILE, '/etc/passwd') == RiskLevel.CRITICAL_RISK
        assert self.analyzer.classify_risk(OperationType.WRITE_FILE, 'C:\\Windows\\system32\\test.dll') == RiskLevel.CRITICAL_RISK
        
        # 低リスク操作でも危険なパスなら高リスクに
        assert self.analyzer.classify_risk(OperationType.READ_FILE, '/etc/shadow') == RiskLevel.HIGH_RISK
        assert self.analyzer.classify_risk(OperationType.LIST_FILES, '.ssh/') == RiskLevel.HIGH_RISK
    
    def test_classify_risk_unknown_operation(self):
        """未知の操作タイプのリスク分類テスト"""
        # 未知の操作はデフォルトでHIGH_RISKになる
        assert self.analyzer.classify_risk('unknown_operation', 'test.txt') == RiskLevel.HIGH_RISK
    
    def test_generate_description_file_operations(self):
        """ファイル操作の説明生成テスト"""
        params = {'target': 'test.py'}
        
        desc = self.analyzer.generate_description(OperationType.CREATE_FILE, params)
        assert "ファイル 'test.py' を作成" in desc
        
        desc = self.analyzer.generate_description(OperationType.READ_FILE, params)
        assert "ファイル 'test.py' を読み取り" in desc
        
        desc = self.analyzer.generate_description(OperationType.DELETE_FILE, params)
        assert "ファイル 'test.py' を削除" in desc
    
    def test_generate_description_with_content(self):
        """内容付きの説明生成テスト"""
        params = {
            'target': 'test.py',
            'content': 'print("Hello World")'
        }
        
        desc = self.analyzer.generate_description(OperationType.CREATE_FILE, params)
        assert "ファイル 'test.py' を作成" in desc
        assert 'print("Hello World")' in desc
    
    def test_generate_description_long_content(self):
        """長い内容の説明生成テスト"""
        long_content = "a" * 100  # 100文字の長い内容
        params = {
            'target': 'test.py',
            'content': long_content
        }
        
        desc = self.analyzer.generate_description(OperationType.CREATE_FILE, params)
        assert "ファイル 'test.py' を作成" in desc
        assert "..." in desc  # 省略記号が含まれる
        assert len(desc) < len(long_content) + 50  # 説明が短縮されている
    
    def test_generate_description_directory_operations(self):
        """ディレクトリ操作の説明生成テスト"""
        params = {'target': 'test_dir'}
        
        desc = self.analyzer.generate_description(OperationType.CREATE_DIRECTORY, params)
        assert "ディレクトリ 'test_dir' を作成" in desc
        
        desc = self.analyzer.generate_description(OperationType.DELETE_DIRECTORY, params)
        assert "ディレクトリ 'test_dir' を削除" in desc
    
    def test_generate_description_execution_operations(self):
        """実行操作の説明生成テスト"""
        params = {'target': 'script.py'}
        
        desc = self.analyzer.generate_description(OperationType.EXECUTE_PYTHON, params)
        assert "Pythonファイル 'script.py' を実行" in desc
        
        params = {'target': 'ls -la'}
        desc = self.analyzer.generate_description(OperationType.EXECUTE_COMMAND, params)
        assert "コマンド 'ls -la' を実行" in desc
    
    def test_generate_description_unknown_operation(self):
        """未知の操作の説明生成テスト"""
        params = {'target': 'test'}
        
        desc = self.analyzer.generate_description('unknown_operation', params)
        assert "操作 'unknown_operation' を実行" in desc
    
    def test_generate_preview_file_operations(self):
        """ファイル操作のプレビュー生成テスト"""
        params = {
            'target': 'test.py',
            'content': 'print("Hello World")'
        }
        
        # ファイル作成のプレビュー
        preview = self.analyzer._generate_preview(OperationType.CREATE_FILE, params)
        assert preview == 'print("Hello World")'
        
        # ファイル書き込みのプレビュー
        preview = self.analyzer._generate_preview(OperationType.WRITE_FILE, params)
        assert preview == 'print("Hello World")'
    
    def test_generate_preview_long_content(self):
        """長い内容のプレビュー生成テスト"""
        long_content = "a" * 250  # 250文字の長い内容
        params = {
            'target': 'test.py',
            'content': long_content
        }
        
        preview = self.analyzer._generate_preview(OperationType.CREATE_FILE, params)
        assert len(preview) <= 220  # 200文字 + "... (続きがあります)"
        assert "... (続きがあります)" in preview
    
    def test_generate_preview_command_execution(self):
        """コマンド実行のプレビュー生成テスト"""
        params = {
            'target': 'script.py',
            'command': 'python script.py --verbose'
        }
        
        preview = self.analyzer._generate_preview(OperationType.EXECUTE_PYTHON, params)
        assert "実行コマンド: python script.py --verbose" in preview
        
        params = {'target': 'ls -la'}
        preview = self.analyzer._generate_preview(OperationType.EXECUTE_COMMAND, params)
        assert "実行コマンド: ls -la" in preview
    
    def test_generate_preview_no_preview_operations(self):
        """プレビューが生成されない操作のテスト"""
        params = {'target': 'test.txt'}
        
        # 読み取り操作はプレビューなし
        preview = self.analyzer._generate_preview(OperationType.READ_FILE, params)
        assert preview is None
        
        # ファイル一覧操作はプレビューなし
        preview = self.analyzer._generate_preview(OperationType.LIST_FILES, params)
        assert preview is None
    
    def test_get_risk_explanation(self):
        """リスクレベル説明の取得テスト"""
        low_risk_explanation = self.analyzer.get_risk_explanation(RiskLevel.LOW_RISK)
        assert "安全" in low_risk_explanation
        
        high_risk_explanation = self.analyzer.get_risk_explanation(RiskLevel.HIGH_RISK)
        assert "変更を加える可能性" in high_risk_explanation
        
        critical_risk_explanation = self.analyzer.get_risk_explanation(RiskLevel.CRITICAL_RISK)
        assert "重大な影響" in critical_risk_explanation
    
    def test_add_custom_risk_mapping(self):
        """カスタムリスクマッピング追加のテスト"""
        custom_operation = "custom_operation"
        
        # カスタム操作を追加
        self.analyzer.add_custom_risk_mapping(custom_operation, RiskLevel.CRITICAL_RISK)
        
        # 追加されたマッピングが機能することを確認
        risk = self.analyzer.classify_risk(custom_operation, 'test')
        assert risk == RiskLevel.CRITICAL_RISK
    
    def test_analyze_operation_comprehensive(self):
        """包括的な操作分析テスト"""
        params = {
            'target': 'complex_script.py',
            'content': 'import os\nprint("System info:", os.uname())',
            'command': 'python complex_script.py',
            'additional_info': 'test script'
        }
        
        result = self.analyzer.analyze_operation(OperationType.CREATE_FILE, params)
        
        # 全ての情報が正しく設定されていることを確認
        assert result.operation_type == OperationType.CREATE_FILE
        assert result.target == 'complex_script.py'
        assert result.risk_level == RiskLevel.HIGH_RISK
        assert 'complex_script.py' in result.description
        assert 'import os' in result.preview
        assert result.details == params
        assert 'additional_info' in result.details