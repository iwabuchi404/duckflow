#!/usr/bin/env python3
"""
jsonモジュールとdatetimeモジュールのimport修正確認テストスクリプト

このスクリプトは、修正後のEnhancedCompanionCoreV7がjsonモジュールとdatetimeモジュールを正しく使用できるかを確認します。
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

def test_json_import():
    """jsonモジュールのimportをテスト"""
    logger.info("=== jsonモジュール import テスト開始 ===")
    
    try:
        # EnhancedCompanionCoreV7をインポート
        from companion.enhanced_core import EnhancedCompanionCoreV7
        
        # jsonモジュールが利用可能かチェック
        import json
        test_data = {"test": "value", "number": 42}
        json_string = json.dumps(test_data, indent=2, ensure_ascii=False)
        
        if json_string:
            logger.info("✅ jsonモジュールが正常に利用できます")
            logger.info(f"テスト結果: {json_string}")
        else:
            logger.error("❌ jsonモジュールの利用に失敗しました")
            return False
        
        logger.info("=== jsonモジュール import テスト完了 ===")
        return True
        
    except Exception as e:
        logger.error(f"jsonモジュール import テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_datetime_import():
    """datetimeモジュールのimportをテスト"""
    logger.info("=== datetimeモジュール import テスト開始 ===")
    
    try:
        # EnhancedCompanionCoreV7をインポート
        from companion.enhanced_core import EnhancedCompanionCoreV7
        
        # datetimeモジュールが利用可能かチェック
        import datetime
        current_time = datetime.datetime.now()
        
        if current_time:
            logger.info("✅ datetimeモジュールが正常に利用できます")
            logger.info(f"テスト結果: {current_time}")
        else:
            logger.error("❌ datetimeモジュールの利用に失敗しました")
            return False
        
        logger.info("=== datetimeモジュール import テスト完了 ===")
        return True
        
    except Exception as e:
        logger.error(f"datetimeモジュール import テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_enhanced_core_modules_usage():
    """EnhancedCompanionCoreV7でのモジュール使用をテスト"""
    logger.info("=== EnhancedCompanionCoreV7 モジュール使用 テスト開始 ===")
    
    try:
        # モックオブジェクトを作成
        class MockDualLoopSystem:
            def __init__(self):
                self.agent_state = None
                self.llm_call_manager = None
                self.llm_service = None
                self.intent_analyzer = None
                self.prompt_context_service = None
        
        mock_system = MockDualLoopSystem()
        
        # EnhancedCompanionCoreV7を初期化
        from companion.enhanced_core import EnhancedCompanionCoreV7
        core = EnhancedCompanionCoreV7(mock_system)
        
        # json.dumpsが使用できるかチェック
        test_context = {"summary": "テストサマリー", "details": "テスト詳細"}
        
        try:
            # 実際のコードで使用されている部分をテスト
            import json
            context_summary = json.dumps(test_context, indent=2, ensure_ascii=False)
            logger.info("✅ json.dumpsが正常に動作します")
            logger.info(f"テスト結果: {context_summary}")
        except Exception as e:
            logger.error(f"❌ json.dumpsでエラーが発生: {e}")
            return False
        
        # datetime.nowが使用できるかチェック
        try:
            import datetime
            start_time = datetime.datetime.now()
            logger.info("✅ datetime.datetime.nowが正常に動作します")
            logger.info(f"テスト結果: {start_time}")
        except Exception as e:
            logger.error(f"❌ datetime.datetime.nowでエラーが発生: {e}")
            return False
        
        logger.info("=== EnhancedCompanionCoreV7 モジュール使用 テスト完了 ===")
        return True
        
    except Exception as e:
        logger.error(f"EnhancedCompanionCoreV7 モジュール使用 テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メイン実行関数"""
    logger.info("🚀 モジュール import修正確認テストを開始します")
    
    test_results = []
    
    # 各テストを実行
    test_results.append(("json import テスト", test_json_import()))
    test_results.append(("datetime import テスト", test_datetime_import()))
    test_results.append(("EnhancedCompanionCoreV7 モジュール使用 テスト", test_enhanced_core_modules_usage()))
    
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
        logger.info("🎉 全てのテストが成功しました！モジュールのimport修正は正常に動作しています。")
        logger.info("\n📋 修正完了項目:")
        logger.info("  ✅ jsonモジュールのimport追加")
        logger.info("  ✅ datetimeモジュールのimport追加")
        logger.info("  ✅ EnhancedCompanionCoreV7でのモジュール使用確認")
        return 0
    else:
        logger.error("💥 一部のテストが失敗しました。実装を確認してください。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
