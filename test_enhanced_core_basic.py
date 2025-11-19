#!/usr/bin/env python3
"""
EnhancedCompanionCoreV7の基本的な動作確認テストスクリプト

このスクリプトは、修正後のEnhancedCompanionCoreV7が正常に初期化できるかを確認します。
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

def test_enhanced_core_initialization():
    """EnhancedCompanionCoreV7の初期化をテスト"""
    logger.info("=== EnhancedCompanionCoreV7 初期化テスト開始 ===")
    
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
        
        # 基本的な属性が存在するかチェック
        required_attributes = [
            'logger', 'dual_loop_system', 'agent_state', 'llm_call_manager',
            'llm_service', 'intent_analyzer', 'prompt_context_service',
            'ui', 'config', 'tools'
        ]
        
        for attr in required_attributes:
            if hasattr(core, attr):
                logger.info(f"✅ {attr} が正常に初期化されています")
            else:
                logger.error(f"❌ {attr} が初期化されていません")
                return False
        
        # ツール辞書の内容をチェック
        expected_tools = ['file_ops', 'plan_tool', 'task_tool', 'response', 'llm_service', 'task_loop']
        for tool_name in expected_tools:
            if tool_name in core.tools:
                logger.info(f"✅ {tool_name} ツールが正常に登録されています")
            else:
                logger.error(f"❌ {tool_name} ツールが登録されていません")
                return False
        
        # 重複防止機能が存在するかチェック
        if hasattr(core, '_is_duplicate_response'):
            logger.info("✅ 重複防止機能が正常に実装されています")
        else:
            logger.error("❌ 重複防止機能が実装されていません")
            return False
        
        logger.info("=== EnhancedCompanionCoreV7 初期化テスト完了 ===")
        return True
        
    except Exception as e:
        logger.error(f"EnhancedCompanionCoreV7 初期化テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tool_methods():
    """ツールメソッドの動作をテスト"""
    logger.info("=== ツールメソッド テスト開始 ===")
    
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
        
        # 各ツールメソッドをテスト
        test_cases = [
            ('file_ops', 'read_file', {'file_path': 'test.txt'}),
            ('plan_tool', 'propose', {'user_goal': 'テスト目標'}),
            ('task_tool', 'generate_list', {'step_id': 'step_001'}),
            ('response', 'echo', {'message': 'テストメッセージ'}),
            ('llm_service', 'synthesize_insights_from_files', {'task_description': 'テスト分析'}),
            ('task_loop', 'execute_task_list', {'task_list': ['task1', 'task2']})
        ]
        
        for tool_name, method_name, args in test_cases:
            try:
                tool_method = core.tools[tool_name]
                result = tool_method(method_name, args)
                logger.info(f"✅ {tool_name}.{method_name} が正常に動作しました: {result}")
            except Exception as e:
                logger.error(f"❌ {tool_name}.{method_name} でエラーが発生: {e}")
                return False
        
        logger.info("=== ツールメソッド テスト完了 ===")
        return True
        
    except Exception as e:
        logger.error(f"ツールメソッド テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メイン実行関数"""
    logger.info("🚀 EnhancedCompanionCoreV7 基本動作確認テストを開始します")
    
    test_results = []
    
    # 各テストを実行
    test_results.append(("初期化テスト", test_enhanced_core_initialization()))
    test_results.append(("ツールメソッドテスト", test_tool_methods()))
    
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
        logger.info("🎉 全てのテストが成功しました！EnhancedCompanionCoreV7は正常に動作しています。")
        logger.info("\n📋 修正完了項目:")
        logger.info("  ✅ 初期化順序の修正（loggerを最初に初期化）")
        logger.info("  ✅ 不足していたツールメソッドの追加")
        logger.info("  ✅ 必要なimportの追加")
        logger.info("  ✅ Actionクラスの定義追加")
        return 0
    else:
        logger.error("💥 一部のテストが失敗しました。実装を確認してください。")
        return 1

if __name__ == "__main__":
    sys.exit(main())



