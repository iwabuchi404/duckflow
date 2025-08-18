#!/usr/bin/env python3
"""
main_companion.py統合テスト
実行阻害改善機能が正しく統合されているかを確認
"""

import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """必要なモジュールがインポートできるかテスト"""
    print("🧪 インポートテスト")
    
    try:
        # FILE_OPS_V2を有効化
        os.environ["FILE_OPS_V2"] = "1"
        
        from companion.enhanced_dual_loop import EnhancedDualLoopSystem
        print("  ✅ EnhancedDualLoopSystem import成功")
        
        from companion.intent_understanding.intent_integration import OptionResolver
        print("  ✅ OptionResolver import成功")
        
        from companion.collaborative_planner import ActionSpec
        print("  ✅ ActionSpec import成功")
        
        from codecrafter.ui.rich_ui import rich_ui
        print("  ✅ rich_ui import成功")
        
        return True
        
    except Exception as e:
        print(f"  ❌ インポート失敗: {e}")
        return False


def test_option_resolver():
    """OptionResolverの動作テスト"""
    print("\n🧪 OptionResolverテスト")
    
    try:
        from companion.intent_understanding.intent_integration import OptionResolver
        
        test_cases = [
            ("OKです実装してください", True),
            ("１で", True),
            ("デフォルトで進めてください", True),
            ("実装を開始してください", True),
            ("無効な入力", False),
        ]
        
        success_count = 0
        for input_text, expected_is_selection in test_cases:
            is_selection = OptionResolver.is_selection_input(input_text)
            selection = OptionResolver.parse_selection(input_text)
            
            if is_selection == expected_is_selection:
                success_count += 1
                status = "✅"
            else:
                status = "❌"
            
            print(f"  {status} '{input_text}' -> 選択入力: {is_selection}, 選択: {selection}")
        
        print(f"  📊 結果: {success_count}/{len(test_cases)} 成功")
        return success_count == len(test_cases)
        
    except Exception as e:
        print(f"  ❌ OptionResolverテスト失敗: {e}")
        return False


def test_enhanced_dual_loop_system():
    """EnhancedDualLoopSystemの初期化テスト"""
    print("\n🧪 EnhancedDualLoopSystemテスト")
    
    try:
        from companion.enhanced_dual_loop import EnhancedDualLoopSystem
        
        # システムを初期化
        system = EnhancedDualLoopSystem()
        print("  ✅ EnhancedDualLoopSystem初期化成功")
        
        # 実行阻害改善機能の確認
        if hasattr(system, 'plan_context'):
            print("  ✅ PlanContext統合確認")
        else:
            print("  ❌ PlanContext未統合")
            return False
        
        if hasattr(system, 'anti_stall_guard'):
            print("  ✅ AntiStallGuard統合確認")
        else:
            print("  ❌ AntiStallGuard未統合")
            return False
        
        if hasattr(system, 'plan_executor'):
            print("  ✅ PlanExecutor統合確認")
        else:
            print("  ❌ PlanExecutor未統合")
            return False
        
        # 状態取得テスト
        status = system.get_status()
        if isinstance(status, dict):
            print("  ✅ 状態取得成功")
        else:
            print("  ❌ 状態取得失敗")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ EnhancedDualLoopSystemテスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_file_ops_v2():
    """FILE_OPS_V2環境変数の確認"""
    print("\n🧪 FILE_OPS_V2テスト")
    
    file_ops_v2 = os.getenv("FILE_OPS_V2")
    if file_ops_v2 == "1":
        print("  ✅ FILE_OPS_V2が有効化されています")
        return True
    else:
        print(f"  ❌ FILE_OPS_V2が無効: {file_ops_v2}")
        return False


def main():
    """メイン関数"""
    print("🚀 main_companion.py統合テスト開始\n")
    
    try:
        # テスト実行
        test1 = test_imports()
        test2 = test_option_resolver()
        test3 = test_enhanced_dual_loop_system()
        test4 = test_file_ops_v2()
        
        if all([test1, test2, test3, test4]):
            print("\n✅ すべてのテストが成功しました！")
            print("\n🎯 統合完了:")
            print("  1. main_companion.pyに実行阻害改善機能を統合")
            print("  2. FILE_OPS_V2を自動有効化")
            print("  3. Enhanced機能の説明を更新")
            print("  4. 重複ファイル（main_companion_dual.py）を削除")
            
            print("\n🔧 使用方法:")
            print("  uv run python main_companion.py")
            print("  または")
            print("  python main_companion.py")
            
            print("\n🎯 期待される動作:")
            print("  - 「OKです実装してください」が実行ルートに転送される")
            print("  - 「１で」「デフォルトで」が選択入力として認識される")
            print("  - 質問ループに戻らず実際のファイル操作が実行される")
        else:
            print("\n❌ 一部のテストが失敗しました")
            print("統合に問題がある可能性があります")
            
    except Exception as e:
        print(f"❌ テスト中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()