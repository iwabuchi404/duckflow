#!/usr/bin/env python3
"""
統合E2Eテストの実行スクリプト
実際のDuckflowCompanionとの統合テスト
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.e2e.integrated_test_runner import IntegratedTestRunner


async def main():
    """メイン関数"""
    # ログ設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('integrated_e2e_test.log')
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("統合E2Eテスト開始")
    
    # 環境変数の確認
    api_keys = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
    }
    
    available_apis = [name for name, key in api_keys.items() if key]
    
    if not available_apis:
        print("⚠️ 警告: 実LLM APIキーが設定されていません")
        print("モック版LLMを使用して統合テストを実行します")
        print("実際のLLMを使用する場合は、.envファイルにAPIキーを設定してください")
    else:
        print(f"✅ 利用可能なLLM API: {', '.join(available_apis)}")
    
    try:
        # 統合テストランナーの初期化
        runner = IntegratedTestRunner()
        
        if len(sys.argv) > 1:
            # 特定のシナリオファイルを実行
            scenario_file = sys.argv[1]
            logger.info(f"統合テスト単体実行: {scenario_file}")
            
            result = await runner.run_integrated_test(scenario_file)
            
            # 結果の表示
            print("\\n" + "="*60)
            print("統合E2Eテスト結果")
            print("="*60)
            print(f"シナリオ: {result['scenario_config']['name']}")
            print(f"成功: {'✅' if result['success'] else '❌'}")
            
            # 統合情報の表示
            if "integration_info" in result:
                info = result["integration_info"]
                print(f"システム: {info.get('duckflow_system', 'Unknown')}")
                print(f"バージョン: {info.get('system_version', 'Unknown')}")
            
            if result.get('evaluation', {}).get('evaluation'):
                eval_data = result['evaluation']['evaluation']
                print(f"総合スコア: {eval_data.get('overall_score', {}).get('score', 0)}/5.0")
                
                # 各項目のスコア表示
                for key, label in [
                    ('scenario_achievement', 'シナリオ達成度'),
                    ('conversation_naturalness', '対話の自然さ'),
                    ('technical_accuracy', '技術的正確性'),
                    ('error_handling', 'エラーハンドリング')
                ]:
                    score_data = eval_data.get(key, {})
                    print(f"{label}: {score_data.get('score', 0)}/5.0")
            
            print(f"\\nログファイル: {result.get('log_file', 'なし')}")
            
        else:
            # 統合テストスイートを実行
            logger.info("統合テストスイート実行")
            
            # Level 1シナリオを実行
            suite_result = await runner.run_integrated_suite("tests/scenarios/level1/*.yaml")
            
            # 結果の表示
            print("\\n" + "="*60)
            print("統合E2Eテストスイート結果")
            print("="*60)
            
            summary = suite_result['summary']
            print(f"統合システム: {summary.get('integration_type', 'Unknown')}")
            print(f"総テスト数: {summary['total']}")
            print(f"成功: {summary['passed']}")
            print(f"失敗: {summary['failed']}")
            print(f"成功率: {summary['pass_rate']:.1f}%")
            print(f"平均スコア: {summary['average_score']:.2f}/5.0")
            print(f"実行時間: {suite_result['execution_time']:.1f}秒")
            
            print("\\n個別結果:")
            for result in suite_result['results']:
                name = result['scenario_config']['name']
                success = "✅" if result['success'] else "❌"
                score = 0
                
                if result.get('evaluation', {}).get('evaluation'):
                    score = result['evaluation']['evaluation'].get('overall_score', {}).get('score', 0)
                
                duration = result.get('test_duration', 0)
                print(f"  {success} {name}: {score}/5.0 ({duration:.1f}s)")
            
            # レポート生成
            report = runner.generate_report(suite_result['results'])
            print("\\n" + "="*60)
            print("統合テスト詳細レポート")
            print("="*60)
            print(report)
            
            # 統合テスト特有の分析
            print("\\n" + "="*60)
            print("統合分析")
            print("="*60)
            
            total_exchanges = sum(
                len(r.get('conversation_log', {}).get('exchanges', []))
                for r in suite_result['results']
            )
            
            total_files = sum(
                len(r.get('conversation_log', {}).get('files_created', []))
                for r in suite_result['results']
            )
            
            print(f"総対話数: {total_exchanges}")
            print(f"作成ファイル数: {total_files}")
            print(f"平均対話時間: {suite_result['execution_time'] / summary['total']:.1f}秒/テスト")
            
            if summary['pass_rate'] >= 80:
                print("\\n🎉 統合テスト成功! Duckflowシステムは正常に動作しています。")
            else:
                print("\\n⚠️ 統合テストで問題が検出されました。ログを確認してください。")
        
        logger.info("統合E2Eテスト完了")
        
    except Exception as e:
        logger.error(f"統合E2Eテストでエラーが発生しました: {e}")
        print(f"❌ エラー: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))