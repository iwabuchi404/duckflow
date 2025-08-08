#!/usr/bin/env python3
"""
シェルツールとツール拡充機能のテスト
安全性チェックとコマンド実行の動作確認
"""

import sys
import os
import io

# Windows環境でのUTF-8出力設定
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from codecrafter.tools.shell_tools import shell_tools
from codecrafter.base.config import ConfigManager


def test_command_safety_check():
    """コマンド安全性チェックのテスト"""
    print("=== コマンド安全性チェック テスト ===")
    
    test_commands = [
        {
            "name": "安全なコマンド",
            "command": "python --version",
            "expected_safe": True
        },
        {
            "name": "許可されていないコマンド",
            "command": "curl https://example.com",
            "expected_safe": False
        },
        {
            "name": "危険なパターン",
            "command": "rm -rf /",
            "expected_safe": False
        },
        {
            "name": "パイプ付きコマンド（安全）",
            "command": "ls | grep test",
            "expected_safe": True
        },
        {
            "name": "パイプ付きコマンド（危険）",
            "command": "ls | sh",
            "expected_safe": False
        },
        {
            "name": "システムパスアクセス",
            "command": "cat /etc/passwd",
            "expected_safe": False
        }
    ]
    
    all_passed = True
    
    for test_case in test_commands:
        print(f"\n--- {test_case['name']} ---")
        
        try:
            result = shell_tools.is_command_safe(test_case['command'])
            
            is_safe = result['is_safe']
            risks = result['risks']
            reason = result['reason']
            
            print(f"コマンド: {test_case['command']}")
            print(f"安全性: {is_safe}")
            print(f"検出リスク: {risks}")
            print(f"理由: {reason}")
            
            if is_safe == test_case['expected_safe']:
                print(f"✅ {test_case['name']} - 正しい判定")
            else:
                print(f"❌ {test_case['name']} - 判定ミス (期待: {test_case['expected_safe']}, 実際: {is_safe})")
                all_passed = False
                
        except Exception as e:
            print(f"❌ {test_case['name']} - テストエラー: {e}")
            all_passed = False
    
    return all_passed


def test_safe_command_execution():
    """安全なコマンド実行のテスト"""
    print("\n=== 安全なコマンド実行 テスト ===")
    
    # 設定の初期化
    os.environ['GROQ_API_KEY'] = 'dummy_key_for_test'
    
    test_commands = [
        {
            "name": "Pythonバージョン確認",
            "command": "python --version",
            "should_succeed": True
        },
        {
            "name": "pip バージョン確認", 
            "command": "pip --version",
            "should_succeed": True
        },
        {
            "name": "現在のディレクトリ",
            "command": "pwd" if os.name != 'nt' else "cd",
            "should_succeed": True
        }
    ]
    
    all_passed = True
    
    for test_case in test_commands:
        print(f"\n--- {test_case['name']} ---")
        
        try:
            result = shell_tools.execute_command(
                command=test_case['command'],
                capture_output=True,
                require_approval=False  # テストでは自動実行
            )
            
            success = result['success']
            stdout = result.get('stdout', '')
            stderr = result.get('stderr', '')
            execution_time = result.get('execution_time', 0)
            
            print(f"コマンド: {test_case['command']}")
            print(f"実行成功: {success}")
            print(f"実行時間: {execution_time:.3f}s")
            
            if stdout:
                print(f"標準出力: {stdout.strip()}")
            if stderr:
                print(f"標準エラー: {stderr.strip()}")
            
            if success == test_case['should_succeed']:
                print(f"✅ {test_case['name']} - 期待通りの結果")
            else:
                print(f"❌ {test_case['name']} - 予期しない結果")
                all_passed = False
                
        except Exception as e:
            print(f"❌ {test_case['name']} - 実行エラー: {e}")
            all_passed = False
    
    return all_passed


def test_system_info():
    """システム情報取得のテスト"""
    print("\n=== システム情報取得 テスト ===")
    
    try:
        result = shell_tools.get_system_info()
        
        if result['success']:
            print("✅ システム情報取得成功")
            
            system_info = result['system_info']
            for info_type, value in system_info.items():
                print(f"  {info_type}: {value}")
            
            print(f"  取得時刻: {result['timestamp']}")
            
            # 基本的な情報が取得できているかチェック
            expected_keys = ['python_version', 'current_directory']
            missing_keys = [key for key in expected_keys if key not in system_info]
            
            if not missing_keys:
                print("✅ 必要な情報がすべて取得されました")
                return True
            else:
                print(f"❌ 不足している情報: {missing_keys}")
                return False
        else:
            print("❌ システム情報取得失敗")
            return False
            
    except Exception as e:
        print(f"❌ システム情報取得エラー: {e}")
        return False


def test_shell_tools_integration():
    """シェルツール統合テスト"""
    print("\n=== シェルツール統合 テスト ===")
    
    try:
        # 設定の初期化
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # ツール設定の確認
        shell_config = config.tools.shell
        allowed_commands = shell_config.get('allowed_commands', [])
        timeout_seconds = shell_config.get('timeout_seconds', 30)
        
        print(f"許可コマンド数: {len(allowed_commands)}")
        print(f"タイムアウト設定: {timeout_seconds}秒")
        print(f"主要な許可コマンド: {allowed_commands[:5]}...")
        
        # セキュリティ設定の確認
        security_config = config.security
        forbidden_patterns = security_config.forbidden_patterns
        
        print(f"禁止パターン数: {len(forbidden_patterns)}")
        print(f"禁止パターン例: {forbidden_patterns[:3]}...")
        
        print("✅ シェルツール統合確認完了")
        return True
        
    except Exception as e:
        print(f"❌ 統合テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メインテスト実行"""
    print("シェルツール機能テストを開始します\n")
    
    tests = [
        ("コマンド安全性チェック", test_command_safety_check),
        ("安全なコマンド実行", test_safe_command_execution),
        ("システム情報取得", test_system_info),
        ("シェルツール統合", test_shell_tools_integration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"テスト実行: {test_name}")
        print('='*60)
        
        try:
            success = test_func()
            if success:
                passed += 1
                print(f"✅ {test_name} - PASSED")
            else:
                print(f"❌ {test_name} - FAILED")
        except Exception as e:
            print(f"❌ {test_name} - ERROR: {e}")
    
    print(f"\n{'='*60}")
    print(f"テスト結果: {passed}/{total} 成功")
    print('='*60)
    
    if passed == total:
        print("🎉 すべてのシェルツールテストが成功しました！")
        return True
    else:
        print(f"⚠️  {total - passed}個のテストが失敗しました")
        return False


if __name__ == "__main__":
    main()