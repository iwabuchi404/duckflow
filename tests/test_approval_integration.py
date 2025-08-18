import pytest
from pathlib import Path
from unittest.mock import MagicMock
from companion.core import CompanionCore
from companion.simple_approval import ApprovalResult, SimpleApprovalGate, ApprovalMode

@pytest.fixture
def core_instance(tmp_path):
    """CompanionCoreのインスタンスをセットアップし、作業ディレクトリを変更する"""
    import os
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    core = CompanionCore()
    yield core
    os.chdir(original_cwd)

def test_write_file_with_approval_approved(core_instance: CompanionCore, monkeypatch):
    """ユーザーがファイル書き込みを承認するケースをテスト"""
    mock_approval_result = ApprovalResult(approved=True, reason="Test approval", timestamp=MagicMock())
    monkeypatch.setattr(SimpleApprovalGate, "request_approval", lambda self, request: mock_approval_result)
    test_file = "test_approved.txt"
    test_content = "This file should be written."
    result = core_instance.file_ops.write_file(test_file, test_content)
    assert result["success"] is True
    assert Path(test_file).exists()
    assert Path(test_file).read_text(encoding="utf-8") == test_content

def test_write_file_with_approval_denied(core_instance: CompanionCore, monkeypatch):
    """ユーザーがファイル書き込みを拒否するケースをテスト"""
    mock_approval_result = ApprovalResult(approved=False, reason="Test denial", timestamp=MagicMock())
    monkeypatch.setattr(SimpleApprovalGate, "request_approval", lambda self, request: mock_approval_result)
    test_file = "test_denied.txt"
    test_content = "This file should NOT be written."
    result = core_instance.file_ops.write_file(test_file, test_content)
    assert result["success"] is False
    assert not Path(test_file).exists()

def test_approval_with_trusted_mode(monkeypatch, tmp_path):
    """trustedモードで低リスク操作が自動承認されることをテスト"""
    trusted_config = {"mode": "trusted", "ui": {"auto_approve_low": True}}
    monkeypatch.setattr(SimpleApprovalGate, "_load_config", lambda self: trusted_config)
    manual_approval_spy = MagicMock()
    monkeypatch.setattr(SimpleApprovalGate, "_manual_approval", manual_approval_spy)
    
    import os
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    core = CompanionCore()
    test_file = "low_risk_auto_approved.txt"
    test_content = "This should be auto-approved."
    result = core.file_ops.write_file(test_file, test_content)
    os.chdir(original_cwd)

    assert result["success"] is True
    assert Path(tmp_path / test_file).exists()
    manual_approval_spy.assert_not_called()

def test_approval_with_mode_override(monkeypatch, tmp_path):
    """引数で渡したSTRICTモードがconfig.yamlより優先されることをテスト"""
    standard_config = {"mode": "standard", "ui": {}}
    monkeypatch.setattr(SimpleApprovalGate, "_load_config", lambda self: standard_config)
    strict_approval_spy = MagicMock(return_value=ApprovalResult(approved=True, reason="Strict mode test", timestamp=MagicMock()))
    monkeypatch.setattr(SimpleApprovalGate, "_strict_approval", strict_approval_spy)

    import os
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    core = CompanionCore(approval_mode=ApprovalMode.STRICT)
    test_file = "strict_mode_test.txt"
    test_content = "This should trigger strict approval."
    result = core.file_ops.write_file(test_file, test_content)
    os.chdir(original_cwd)

    assert result["success"] is True
    assert Path(tmp_path / test_file).exists()
    strict_approval_spy.assert_called_once()
