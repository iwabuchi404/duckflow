#!/usr/bin/env python3
"""
E2Eテストの実行スクリプト
"""

import asyncio
import logging
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.e2e.test_runner import E2ETestRunner


async def main():
    """メイン関数"""
    # ログ設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('e2e_test.log')
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("E2Eテスト開始")
    
    try:
        # テストランナーの初期化
        runner = E2ETestRunner()
        
        if len(sys.argv) > 1:
            # 特定のシナリオファイルを実行
            scenario_file = sys.argv[1]
            logger.info(f"単一テスト実行: {scenario_file}")
            
            result = await runner.run_single_test(scenario_file)
            
            # 結果の表示
            print("\\n" + "="*50)
            print("E2Eテスト結果")
            print("="*50)
            print(f"シナリオ: {result['scenario_config']['name']}")
            print(f"成功: {'✅' if result['success'] else '❌'}")
            
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
            # テストスイートを実行
            logger.info("テストスイート実行")
            
            # Level 1シナリオを実行
            suite_result = await runner.run_test_suite("tests/scenarios/level1/*.yaml")
            
            # 結果の表示
            print("\\n" + "="*50)
            print("E2Eテストスイート結果")
            print("="*50)
            
            summary = suite_result['summary']
            print(f"総テスト数: {summary['total']}")
            print(f"成功: {summary['passed']}")
            print(f"失敗: {summary['failed']}")
            print(f"成功率: {summary['pass_rate']:.1f}%")
            print(f"平均スコア: {summary['average_score']:.2f}/5.0")
            
            print("\\n個別結果:")
            for result in suite_result['results']:
                name = result['scenario_config']['name']
                success = "✅" if result['success'] else "❌"
                score = 0
                
                if result.get('evaluation', {}).get('evaluation'):
                    score = result['evaluation']['evaluation'].get('overall_score', {}).get('score', 0)
                
                print(f"  {success} {name}: {score}/5.0")
            
            # レポート生成
            report = runner.generate_report(suite_result['results'])
            print("\\n" + "="*50)
            print("詳細レポート")
            print("="*50)
            print(report)
        
        logger.info("E2Eテスト完了")
        
    except Exception as e:
        logger.error(f"E2Eテストでエラーが発生しました: {e}")
        print(f"❌ エラー: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))