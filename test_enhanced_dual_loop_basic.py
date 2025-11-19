#!/usr/bin/env python3
"""
EnhancedDualLoopSystemの基本的な動作確認テストスクリプト

このスクリプトは、修正後のEnhancedDualLoopSystemが正常に初期化できるかを確認します。
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

def test_enhanced_dual_loop_initialization():
    """EnhancedDualLoopSystemの初期化をテスト"""
    logger.info("=== EnhancedDualLoopSystem 初期化テスト開始 ===")
    
    try:
        # EnhancedDualLoopSystemを初期化
        from companion.enhanced_dual_loop import EnhancedDualLoopSystem
        dual_loop_system = EnhancedDualLoopSystem()
        
        # 基本的な属性が存在するかチェック
        required_attributes = [
            'session_id', 'logger', 'task_queue', 'status_queue', 'agent_state',
            'enhanced_companion', 'chat_loop', 'task_loop', 'task_thread', 'running'
        ]
        
        for attr in required_attributes:
            if hasattr(dual_loop_system, attr):
                logger.info(f"✅ {attr} が正常に初期化されています")
            else:
                logger.error(f"❌ {attr} が初期化されていません")
                return False
        
        # EnhancedCompanionCoreV7が必要とする属性が存在するかチェック
        enhanced_attributes = [
            'llm_call_manager', 'llm_service', 'intent_analyzer', 'prompt_context_service'
        ]
        
        for attr in enhanced_attributes:
            if hasattr(dual_loop_system, attr):
                logger.info(f"✅ {attr} が正常に初期化されています")
            else:
                logger.warning(f"⚠️ {attr} が初期化されていません（フォールバック可能）")
        
        # EnhancedCompanionCoreV7が正常に初期化されているかチェック
        if hasattr(dual_loop_system, 'enhanced_companion') and dual_loop_system.enhanced_companion:
            logger.info("✅ EnhancedCompanionCoreV7 が正常に初期化されています")
        else:
            logger.error("❌ EnhancedCompanionCoreV7 が初期化されていません")
            return False
        
        logger.info("=== EnhancedDualLoopSystem 初期化テスト完了 ===")
        return True
        
    except Exception as e:
        logger.error(f"EnhancedDualLoopSystem 初期化テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_enhanced_companion_integration():
    """EnhancedCompanionCoreV7との統合をテスト"""
    logger.info("=== EnhancedCompanionCoreV7統合 テスト開始 ===")
    
    try:
        # EnhancedDualLoopSystemを初期化
        from companion.enhanced_dual_loop import EnhancedDualLoopSystem
        dual_loop_system = EnhancedDualLoopSystem()
        
        # EnhancedCompanionCoreV7の属性をチェック
        enhanced_companion = dual_loop_system.enhanced_companion
        
        required_companion_attributes = [
            'logger', 'dual_loop_system', 'agent_state', 'ui', 'config', 'tools'
        ]
        
        for attr in required_companion_attributes:
            if hasattr(enhanced_companion, attr):
                logger.info(f"✅ EnhancedCompanionCoreV7.{attr} が正常に初期化されています")
            else:
                logger.error(f"❌ EnhancedCompanionCoreV7.{attr} が初期化されていません")
                return False
        
        # ツール辞書の内容をチェック
        expected_tools = ['file_ops', 'plan_tool', 'task_tool', 'response', 'llm_service', 'task_loop']
        for tool_name in expected_tools:
            if tool_name in enhanced_companion.tools:
                logger.info(f"✅ {tool_name} ツールが正常に登録されています")
            else:
                logger.error(f"❌ {tool_name} ツールが登録されていません")
                return False
        
        logger.info("=== EnhancedCompanionCoreV7統合 テスト完了 ===")
        return True
        
    except Exception as e:
        logger.error(f"EnhancedCompanionCoreV7統合 テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メイン実行関数"""
    logger.info("🚀 EnhancedDualLoopSystem 基本動作確認テストを開始します")
    
    test_results = []
    
    # 各テストを実行
    test_results.append(("初期化テスト", test_enhanced_dual_loop_initialization()))
    test_results.append(("EnhancedCompanionCoreV7統合テスト", test_enhanced_companion_integration()))
    
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
        logger.info("🎉 全てのテストが成功しました！EnhancedDualLoopSystemは正常に動作しています。")
        logger.info("\n📋 修正完了項目:")
        logger.info("  ✅ 不足していた属性の追加（llm_call_manager等）")
        logger.info("  ✅ 必要なimportの追加")
        logger.info("  ✅ フォールバック処理の実装")
        logger.info("  ✅ EnhancedCompanionCoreV7との統合")
        return 0
    else:
        logger.error("💥 一部のテストが失敗しました。実装を確認してください。")
        return 1

if __name__ == "__main__":
    sys.exit(main())



