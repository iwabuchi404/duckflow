#!/usr/bin/env python3
"""
応答制限機能の動作確認テストスクリプト

このスクリプトは、新しく実装された応答制限機能が正しく動作するかを確認します。
"""

import sys
import os
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from companion.prompts.main_prompt_generator import MainPromptGenerator
from companion.prompts.base_prompt_generator import BasePromptGenerator
from companion.state.agent_state import AgentState

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_main_prompt_generator():
    """MainPromptGeneratorの応答ガイドライン機能をテスト"""
    logger.info("=== MainPromptGenerator テスト開始 ===")
    
    try:
        # テスト用のAgentStateを作成
        agent_state = AgentState()
        agent_state.goal = "テスト用の目標"
        agent_state.why_now = "テスト用の理由"
        agent_state.constraints = ["テスト用の制約1", "テスト用の制約2"]
        agent_state.plan_brief = ["テスト用の計画1", "テスト用の計画2"]
        agent_state.open_questions = ["テスト用の質問1"]
        
        # MainPromptGeneratorをテスト
        generator = MainPromptGenerator()
        prompt = generator.generate(agent_state)
        
        # 応答ガイドラインが含まれているかチェック
        if "応答ガイドライン" in prompt:
            logger.info("✅ 応答ガイドラインが正常に含まれています")
        else:
            logger.error("❌ 応答ガイドラインが含まれていません")
            return False
        
        if "最大1000文字以内" in prompt:
            logger.info("✅ 文字数制限の指示が正常に含まれています")
        else:
            logger.error("❌ 文字数制限の指示が含まれていません")
            return False
        
        if "大容量データの処理" in prompt:
            logger.info("✅ 大容量データ処理の指示が正常に含まれています")
        else:
            logger.error("❌ 大容量データ処理の指示が含まれていません")
            return False
        
        logger.info(f"生成されたプロンプトの長さ: {len(prompt)}文字")
        logger.info("=== MainPromptGenerator テスト完了 ===")
        return True
        
    except Exception as e:
        logger.error(f"MainPromptGenerator テストエラー: {e}")
        return False

def test_base_prompt_generator():
    """BasePromptGeneratorの応答制限基本原則をテスト"""
    logger.info("=== BasePromptGenerator テスト開始 ===")
    
    try:
        generator = BasePromptGenerator()
        base_context = generator.generate_base_context()
        
        # 応答制限の基本原則が含まれているかチェック
        if "応答制限の基本原則" in base_context:
            logger.info("✅ 応答制限の基本原則が正常に含まれています")
        else:
            logger.error("❌ 応答制限の基本原則が含まれていません")
            return False
        
        if "簡潔性" in base_context and "可読性" in base_context:
            logger.info("✅ 応答品質の指針が正常に含まれています")
        else:
            logger.error("❌ 応答品質の指針が含まれていません")
            return False
        
        if "大容量データの扱い" in base_context:
            logger.info("✅ 大容量データ処理の指針が正常に含まれています")
        else:
            logger.error("❌ 大容量データ処理の指針が含まれていません")
            return False
        
        logger.info(f"生成されたBaseコンテキストの長さ: {len(base_context)}文字")
        logger.info("=== BasePromptGenerator テスト完了 ===")
        return True
        
    except Exception as e:
        logger.error(f"BasePromptGenerator テストエラー: {e}")
        return False

def test_config_integration():
    """設定ファイルの統合をテスト"""
    logger.info("=== 設定ファイル統合テスト開始 ===")
    
    try:
        import yaml
        
        config_path = Path("config/config.yaml")
        if not config_path.exists():
            logger.error("❌ 設定ファイルが見つかりません: config/config.yaml")
            return False
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 応答制限設定が含まれているかチェック
        if 'response_control' in config:
            logger.info("✅ 応答制限設定が正常に設定ファイルに含まれています")
            
            response_config = config['response_control']
            if response_config.get('enable_prompt_level_control'):
                logger.info("✅ プロンプトレベル制御が有効化されています")
            else:
                logger.warning("⚠️ プロンプトレベル制御が無効化されています")
            
            if 'length_limits' in response_config:
                logger.info("✅ 操作別制限が正常に設定されています")
                limits = response_config['length_limits']
                logger.info(f"  - echo: {limits.get('echo', 'N/A')}文字")
                logger.info(f"  - file_analysis: {limits.get('file_analysis', 'N/A')}文字")
                logger.info(f"  - plan_display: {limits.get('plan_display', 'N/A')}文字")
            else:
                logger.error("❌ 操作別制限が設定されていません")
                return False
        else:
            logger.error("❌ 応答制限設定が設定ファイルに含まれていません")
            return False
        
        logger.info("=== 設定ファイル統合テスト完了 ===")
        return True
        
    except Exception as e:
        logger.error(f"設定ファイル統合テストエラー: {e}")
        return False

def main():
    """メイン実行関数"""
    logger.info("🚀 応答制限機能の動作確認テストを開始します")
    
    test_results = []
    
    # 各テストを実行
    test_results.append(("MainPromptGenerator", test_main_prompt_generator()))
    test_results.append(("BasePromptGenerator", test_base_prompt_generator()))
    test_results.append(("設定ファイル統合", test_config_integration()))
    
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
        logger.info("🎉 全てのテストが成功しました！応答制限機能は正常に動作しています。")
        return 0
    else:
        logger.error("💥 一部のテストが失敗しました。実装を確認してください。")
        return 1

if __name__ == "__main__":
    sys.exit(main())



