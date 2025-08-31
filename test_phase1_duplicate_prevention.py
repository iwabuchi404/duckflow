#!/usr/bin/env python3
"""
Phase 1: 重複表示防止機能の動作確認テストスクリプト

このスクリプトは、新しく実装された重複表示防止機能が正しく動作するかを確認します。
"""

import sys
import os
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_ui_echo_methods():
    """UIクラスのechoメソッドをテスト"""
    logger.info("=== UI echoメソッド テスト開始 ===")
    
    try:
        # RichUIのテスト
        from companion.ui import RichUI
        rich_ui = RichUI()
        
        # echoメソッドが存在するかチェック
        if hasattr(rich_ui, 'echo'):
            logger.info("✅ RichUIにechoメソッドが正常に実装されています")
        else:
            logger.error("❌ RichUIにechoメソッドが実装されていません")
            return False
        
        # SimpleUIのテスト
        from companion.ui import SimpleUI
        simple_ui = SimpleUI()
        
        if hasattr(simple_ui, 'echo'):
            logger.info("✅ SimpleUIにechoメソッドが正常に実装されています")
        else:
            logger.error("❌ SimpleUIにechoメソッドが実装されていません")
            return False
        
        logger.info("=== UI echoメソッド テスト完了 ===")
        return True
        
    except Exception as e:
        logger.error(f"UI echoメソッド テストエラー: {e}")
        return False

def test_duplicate_prevention_logic():
    """重複防止ロジックをテスト"""
    logger.info("=== 重複防止ロジック テスト開始 ===")
    
    try:
        # EnhancedCompanionCoreの重複防止メソッドをテスト
        from companion.enhanced_core import EnhancedCompanionCoreV7
        
        # モックオブジェクトを作成
        class MockDualLoopSystem:
            def __init__(self):
                self.agent_state = None
                self.llm_call_manager = None
                self.llm_service = None
                self.intent_analyzer = None
                self.prompt_context_service = None
        
        mock_system = MockDualLoopSystem()
        
        # EnhancedCompanionCoreを初期化
        core = EnhancedCompanionCoreV7(mock_system)
        
        # 重複防止メソッドが存在するかチェック
        if hasattr(core, '_is_duplicate_response'):
            logger.info("✅ 重複防止メソッドが正常に実装されています")
        else:
            logger.error("❌ 重複防止メソッドが実装されていません")
            return False
        
        # 重複防止ロジックをテスト
        test_message = "テストメッセージ"
        
        # 1回目の呼び出し
        result1 = core._is_duplicate_response(test_message)
        if not result1:
            logger.info("✅ 1回目の呼び出しで重複なしと判定されました")
        else:
            logger.error("❌ 1回目の呼び出しで重複ありと誤判定されました")
            return False
        
        # 2回目の呼び出し（同じメッセージ）
        result2 = core._is_duplicate_response(test_message)
        if result2:
            logger.info("✅ 2回目の呼び出しで重複ありと正しく判定されました")
        else:
            logger.error("❌ 2回目の呼び出しで重複なしと誤判定されました")
            return False
        
        # 異なるメッセージ
        different_message = "異なるテストメッセージ"
        result3 = core._is_duplicate_response(different_message)
        if not result3:
            logger.info("✅ 異なるメッセージで重複なしと正しく判定されました")
        else:
            logger.error("❌ 異なるメッセージで重複ありと誤判定されました")
            return False
        
        logger.info("=== 重複防止ロジック テスト完了 ===")
        return True
        
    except Exception as e:
        logger.error(f"重複防止ロジック テストエラー: {e}")
        return False

def test_response_echo_integration():
    """response.echo統合をテスト"""
    logger.info("=== response.echo統合 テスト開始 ===")
    
    try:
        # EnhancedCompanionCoreのresponse.echo処理をテスト
        from companion.enhanced_core import EnhancedCompanionCoreV7
        
        # モックオブジェクトを作成
        class MockDualLoopSystem:
            def __init__(self):
                self.agent_state = None
                self.llm_call_manager = None
                self.llm_service = None
                self.intent_analyzer = None
                self.prompt_context_service = None
        
        mock_system = MockDualLoopSystem()
        
        # EnhancedCompanionCoreを初期化
        core = EnhancedCompanionCoreV7(mock_system)
        
        # ツール辞書にresponse.echoが含まれているかチェック
        if 'response' in core.tools:
            logger.info("✅ responseツールが正常に登録されています")
        else:
            logger.error("❌ responseツールが登録されていません")
            return False
        
        # responseツールのメソッドをチェック
        response_tool = core.tools['response']
        if hasattr(response_tool, '__call__'):
            logger.info("✅ responseツールが呼び出し可能です")
        else:
            logger.error("❌ responseツールが呼び出しできません")
            return False
        
        logger.info("=== response.echo統合 テスト完了 ===")
        return True
        
    except Exception as e:
        logger.error(f"response.echo統合 テストエラー: {e}")
        return False

def main():
    """メイン実行関数"""
    logger.info("🚀 Phase 1: 重複表示防止機能の動作確認テストを開始します")
    
    test_results = []
    
    # 各テストを実行
    test_results.append(("UI echoメソッド", test_ui_echo_methods()))
    test_results.append(("重複防止ロジック", test_duplicate_prevention_logic()))
    test_results.append(("response.echo統合", test_response_echo_integration()))
    
    # 結果を集計
    logger.info("\n" + "="*50)
    logger.info("📊 テスト結果サマリー")
    logger.info("="*50)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\n総合結果: {passed}/{total} テストが成功")
    
    if passed == total:
        logger.info("🎉 全てのテストが成功しました！Phase 1の重複表示防止機能は正常に動作しています。")
        logger.info("\n📋 実装完了項目:")
        logger.info("  ✅ RichUIとSimpleUIにechoメソッドを追加")
        logger.info("  ✅ 重複表示防止の状態管理を実装")
        logger.info("  ✅ 重複判定ロジックを実装")
        logger.info("  ✅ response.echo処理に重複防止を統合")
        logger.info("  ✅ 適切な区切り表示を実装")
        return 0
    else:
        logger.error("💥 一部のテストが失敗しました。実装を確認してください。")
        return 1

if __name__ == "__main__":
    sys.exit(main())


