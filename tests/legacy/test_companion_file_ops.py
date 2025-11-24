#!/usr/bin/env python3
"""
Duckflow Companion Phase 1.5 テスト
ファイル操作機能のテスト
"""

import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from companion.core import CompanionCore
from codecrafter.ui.rich_ui import rich_ui


def test_file_operations():
    """ファイル操作のテスト"""
    
    rich_ui.print_header("🧪 Duckflow Companion Phase 1.5 テスト", "ファイル操作機能のテスト")
    
    # CompanionCoreの初期化
    try:
        companion = CompanionCore()
        rich_ui.print_success("✅ CompanionCore初期化完了")
    except Exception as e:
        rich_ui.print_error(f"❌ 初期化失敗: {e}")
        return
    
    # テストケース
    test_cases = [
        {
            "name": "ファイル作成テスト",
            "message": "hello.py ファイルを作成して、Hello World を出力するコードを書いて",
            "expected": "ファイル作成"
        },
        {
            "name": "ファイル読み取りテスト", 
            "message": "hello.py ファイルの内容を読んで",
            "expected": "ファイル読み取り"
        },
        {
            "name": "ファイル一覧テスト",
            "message": "現在のディレクトリのファイル一覧を見せて",
            "expected": "ファイル一覧"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        rich_ui.print_separator()
        rich_ui.print_message(f"🧪 テスト {i}: {test_case['name']}", "info")
        rich_ui.print_message(f"入力: {test_case['message']}", "muted")
        
        try:
            # テスト実行
            response = companion.process_message(test_case['message'])
            
            # 結果表示
            rich_ui.print_message("📤 応答:", "info")
            rich_ui.print_conversation_message("Duckflow", response)
            
            rich_ui.print_success(f"✅ テスト {i} 完了")
            
        except Exception as e:
            rich_ui.print_error(f"❌ テスト {i} 失敗: {e}")
            import traceback
            rich_ui.print_error(traceback.format_exc())
    
    # セッションサマリー
    rich_ui.print_separator()
    summary = companion.get_session_summary()
    rich_ui.print_message(f"📊 テスト完了: {summary['total_messages']}回の対話", "success")


if __name__ == "__main__":
    test_file_operations()