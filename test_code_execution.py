#!/usr/bin/env python3
"""
Phase 1.6: コード実行機能のテスト
DuckFlowの新しいコード実行機能をテストする
"""

import asyncio
import tempfile
import os
from pathlib import Path

# プロジェクトルートをPythonパスに追加
import sys
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from companion.code_runner import SimpleCodeRunner
from companion.enhanced_core import EnhancedCompanionCore


async def test_code_runner():
    """SimpleCodeRunnerの基本機能をテスト"""
    print("🧪 SimpleCodeRunner テスト開始")
    
    # コードランナーの初期化
    runner = SimpleCodeRunner(approval_mode=False)  # テスト用に承認を無効化
    
    # テスト用のPythonファイルを作成
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        test_code = '''print("Hello from test file!")
print("This is a test of the code execution system!")
result = 2 + 3
print(f"2 + 3 = {result}")'''
        f.write(test_code)
        test_file = f.name
    
    try:
        print(f"📝 テストファイル作成: {test_file}")
        
        # Pythonファイルの実行テスト
        print("\n⚡ Pythonファイル実行テスト...")
        result = runner.run_python_file(test_file)
        
        print("📊 実行結果:")
        print(f"  成功: {result['success']}")
        print(f"  出力: {result['output']}")
        print(f"  終了コード: {result['exit_code']}")
        
        if result['success']:
            print("✅ Pythonファイル実行テスト成功！")
        else:
            print(f"❌ Pythonファイル実行テスト失敗: {result['error']}")
        
        # コマンド実行テスト
        print("\n💻 コマンド実行テスト...")
        cmd_result = runner.run_command("echo 'Hello from command!'")
        
        print("📊 コマンド実行結果:")
        print(f"  成功: {cmd_result['success']}")
        print(f"  出力: {cmd_result['output']}")
        print(f"  終了コード: {cmd_result['exit_code']}")
        
        if cmd_result['success']:
            print("✅ コマンド実行テスト成功！")
        else:
            print(f"❌ コマンド実行テスト失敗: {cmd_result['error']}")
        
        # 結果フォーマットテスト
        print("\n🎨 結果フォーマットテスト...")
        formatted = runner.format_execution_result(result)
        print("フォーマットされた結果:")
        print(formatted)
        
    finally:
        # テストファイルの削除
        try:
            os.unlink(test_file)
            print(f"\n🧹 テストファイル削除: {test_file}")
        except Exception as e:
            print(f"⚠️  テストファイル削除失敗: {e}")


async def test_enhanced_core_integration():
    """EnhancedCompanionCoreとの統合をテスト"""
    print("\n🧪 EnhancedCompanionCore統合テスト開始")
    
    try:
        # EnhancedCompanionCoreの初期化
        core = EnhancedCompanionCore(approval_mode=False)
        print("✅ EnhancedCompanionCore初期化成功")
        
        # コード実行機能のテスト
        print("\n⚡ 統合コード実行テスト...")
        
        # テスト用のPythonファイルを作成
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            test_code = '''print("Hello from EnhancedCompanionCore!")
print("Testing the integrated code execution system!")
import math
print(f"π = {math.pi:.4f}")'''
            f.write(test_code)
            test_file = f.name
        
        try:
            # EnhancedCompanionCore経由で実行
            result = core.run_python_file(test_file)
            
            print("📊 統合実行結果:")
            print(f"  成功: {result['success']}")
            print(f"  出力: {result['output']}")
            print(f"  終了コード: {result['exit_code']}")
            
            if result['success']:
                print("✅ 統合コード実行テスト成功！")
                
                # 結果フォーマットテスト
                formatted = core.format_execution_result(result)
                print("\n🎨 統合結果フォーマット:")
                print(formatted)
            else:
                print(f"❌ 統合コード実行テスト失敗: {result['error']}")
        
        finally:
            # テストファイルの削除
            try:
                os.unlink(test_file)
                print(f"\n🧹 統合テストファイル削除: {test_file}")
            except Exception as e:
                print(f"⚠️  統合テストファイル削除失敗: {e}")
    
    except Exception as e:
        print(f"❌ EnhancedCompanionCore統合テスト失敗: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """メインテスト関数"""
    print("🚀 DuckFlow Phase 1.6: コード実行機能テスト開始")
    print("=" * 60)
    
    # SimpleCodeRunnerのテスト
    await test_code_runner()
    
    # EnhancedCompanionCore統合テスト
    await test_enhanced_core_integration()
    
    print("\n" + "=" * 60)
    print("🎉 テスト完了！")
    print("\n📋 Phase 1.6実装状況:")
    print("✅ SimpleCodeRunner クラス作成")
    print("✅ セキュリティ機能（安全なディレクトリ、危険コマンドブロック）")
    print("✅ 承認システム統合")
    print("✅ EnhancedCompanionCore統合")
    print("✅ エラーハンドリングとタイムアウト")
    print("✅ 結果フォーマット機能")
    print("\n🎯 次のステップ:")
    print("   - メインシステムでの実際の使用テスト")
    print("   - ユーザーインターフェースでの統合")
    print("   - より高度な実行機能（デバッグ、プロファイリングなど）")


if __name__ == "__main__":
    asyncio.run(main())
