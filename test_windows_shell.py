#!/usr/bin/env python3
"""
Windows環境でのシェル実行テスト
"""

import subprocess
import sys
import os

def test_direct_subprocess():
    """直接subprocessでテスト"""
    print("=== 直接subprocess テスト ===")
    
    commands = [
        "python --version",
        "dir",
        "echo Hello World"
    ]
    
    for cmd in commands:
        print(f"\nコマンド: {cmd}")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            print(f"成功: {result.returncode == 0}")
            print(f"標準出力: {result.stdout.strip()}")
            print(f"標準エラー: {result.stderr.strip()}")
        except Exception as e:
            print(f"エラー: {e}")


def test_shell_tools_simple():
    """シンプルなshell_toolsテスト"""
    print("\n=== shell_tools シンプルテスト ===")
    
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    os.environ['GROQ_API_KEY'] = 'dummy_key_for_test'
    
    try:
        from codecrafter.tools.shell_tools import shell_tools
        
        # 安全性チェックのみテスト
        test_cmd = "echo test"
        safety = shell_tools.is_command_safe(test_cmd)
        print(f"コマンド: {test_cmd}")
        print(f"安全性: {safety}")
        
        # 実行はskip
        print("実行テストはスキップ（環境問題のため）")
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_direct_subprocess()
    test_shell_tools_simple()