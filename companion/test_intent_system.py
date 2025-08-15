"""
Test Intent Understanding System

統合意図理解システムのテスト用メインファイル
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any

# パスを追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from companion.test_mock_llm import mock_llm_client
from companion.intent_understanding.intent_integration import IntentUnderstandingSystem


# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class IntentSystemTester:
    """意図理解システムのテスター"""
    
    def __init__(self):
        """テスターを初期化"""
        self.llm_client = None
        self.intent_system = None
        self.test_results = []
    
    async def initialize_system(self):
        """システムの初期化"""
        try:
            print("🔄 システム初期化中...")
            
            # モックLLMクライアントを使用
            self.llm_client = mock_llm_client
            print(f"✅ モックLLMクライアント初期化完了: {self.llm_client.provider.value}")
            
            # 統合意図理解システムの初期化
            self.intent_system = IntentUnderstandingSystem(self.llm_client)
            print("✅ 統合意図理解システム初期化完了")
            
            return True
            
        except Exception as e:
            print(f"❌ システム初期化エラー: {e}")
            return False
    
    async def test_intent_understanding(self, user_input: str, context: Dict[str, Any] = None):
        """意図理解のテスト"""
        if not self.intent_system:
            print("❌ システムが初期化されていません")
            return None
        
        try:
            print(f"\n🧪 意図理解テスト開始: {user_input}")
            
            # 意図理解の実行
            result = await self.intent_system.understand_intent(user_input, context)
            
            # 結果の表示
            self.intent_system.print_understanding_summary(result)
            
            # 実行計画の表示
            execution_plan = self.intent_system.get_task_execution_plan(result)
            self._print_execution_plan(execution_plan)
            
            # 結果を保存
            self.test_results.append({
                "input": user_input,
                "result": result,
                "execution_plan": execution_plan
            })
            
            return result
            
        except Exception as e:
            print(f"❌ 意図理解テストエラー: {e}")
            return None
    
    def _print_execution_plan(self, execution_plan: Dict[str, Any]):
        """実行計画の表示"""
        print(f"\n📋 **タスク実行計画**")
        
        # メインタスク
        main_task = execution_plan["main_task"]
        print(f"🎯 メインタスク: {main_task['title']}")
        print(f"   - 優先度: {main_task['priority']}")
        print(f"   - 複雑度: {main_task['complexity']}")
        
        # サブタスク
        print(f"\n📝 サブタスク ({len(execution_plan['subtasks'])}個):")
        for subtask in execution_plan["subtasks"]:
            print(f"  {subtask['step']}. {subtask['title']} (優先度: {subtask['priority']})")
        
        # 実行順序
        print(f"\n🔄 実行順序:")
        for i, task_id in enumerate(execution_plan["execution_order"], 1):
            # タスクIDからタイトルを取得
            task_title = "不明"
            for subtask in execution_plan["subtasks"]:
                if subtask["id"] == task_id:
                    task_title = subtask["title"]
                    break
            print(f"  {i}. {task_title}")
        
        # 推定時間
        estimated_duration = execution_plan["estimated_duration"]
        print(f"\n⏱️  推定所要時間: {estimated_duration}分")
        
        # クリティカルパス
        critical_path = execution_plan["critical_path"]
        print(f"\n🚨 クリティカルパス: {len(critical_path)}個のタスク")
    
    async def run_test_scenarios(self):
        """テストシナリオの実行"""
        test_scenarios = [
            {
                "input": "新しいPythonスクリプトを作成して、ファイルの内容を分析する機能を実装してください",
                "description": "作成要求（複雑）"
            },
            {
                "input": "現在のプロジェクトの構造を教えてください",
                "description": "情報要求（単純）"
            },
            {
                "input": "コードの品質を分析して、改善点を提案してください",
                "description": "分析要求（中程度）"
            },
            {
                "input": "READMEファイルを修正して、より分かりやすくしてください",
                "description": "修正要求（中程度）"
            },
            {
                "input": "特定の関数やクラスを探すにはどうすればいいですか？",
                "description": "ガイダンス要求（単純）"
            }
        ]
        
        print(f"\n🚀 {len(test_scenarios)}個のテストシナリオを実行します")
        
        for i, scenario in enumerate(test_scenarios, 1):
            print(f"\n{'='*60}")
            print(f"📋 テストシナリオ {i}: {scenario['description']}")
            print(f"{'='*60}")
            
            # 非同期テストの実行（awaitを使用）
            await self.test_intent_understanding(scenario["input"])
            
            print(f"\n✅ テストシナリオ {i} 完了")
    
    def print_test_summary(self):
        """テスト結果のサマリー表示"""
        print(f"\n{'='*60}")
        print(f"📊 テスト結果サマリー")
        print(f"{'='*60}")
        
        if not self.test_results:
            print("❌ テスト結果がありません")
            return
        
        print(f"総テスト数: {len(self.test_results)}")
        
        # 成功率の計算
        successful_tests = sum(1 for result in self.test_results if result["result"] is not None)
        success_rate = (successful_tests / len(self.test_results)) * 100
        
        print(f"成功数: {successful_tests}")
        print(f"成功率: {success_rate:.1f}%")
        
        # 平均信頼度の計算
        if successful_tests > 0:
            total_confidence = sum(
                result["result"].overall_confidence 
                for result in self.test_results 
                if result["result"] is not None
            )
            avg_confidence = total_confidence / successful_tests
            print(f"平均信頼度: {avg_confidence:.1%}")
        
        # TaskProfile別の統計
        profile_counts = {}
        for result in self.test_results:
            if result["result"]:
                profile_type = result["result"].task_profile.profile_type.value
                profile_counts[profile_type] = profile_counts.get(profile_type, 0) + 1
        
        print(f"\n📊 TaskProfile別の分布:")
        for profile_type, count in profile_counts.items():
            percentage = (count / len(self.test_results)) * 100
            print(f"  {profile_type}: {count}件 ({percentage:.1f}%)")
    
    def get_system_status(self):
        """システムの状態を取得・表示"""
        if not self.intent_system:
            print("❌ システムが初期化されていません")
            return
        
        print(f"\n📈 システム状態:")
        status = self.intent_system.get_system_status()
        
        for key, value in status.items():
            if key == "system_config":
                print(f"  {key}:")
                for config_key, config_value in value.items():
                    print(f"    {config_key}: {config_value}")
            else:
                print(f"  {key}: {value}")


async def main():
    """メイン関数"""
    print("🦆 Duckflow 統合意図理解システム テスト")
    print("=" * 60)
    
    # テスターの初期化
    tester = IntentSystemTester()
    
    # システムの初期化
    if not await tester.initialize_system():
        print("❌ システム初期化に失敗しました")
        return
    
    # システム状態の表示
    tester.get_system_status()
    
    # テストシナリオの実行
    await tester.run_test_scenarios()
    
    # テスト結果のサマリー
    tester.print_test_summary()
    
    print(f"\n🎉 テスト完了！")


if __name__ == "__main__":
    # 非同期メイン関数の実行
    asyncio.run(main())
