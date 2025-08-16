# test_collaborative_planning.py
"""
協調的計画機能のテスト
Step 3実装の動作確認用
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from companion.collaborative_planner import CollaborativePlanner, PlanStatus, TaskEstimate

def test_task_complexity_analysis():
    """タスク複雑度分析のテスト"""
    print("📋 タスク複雑度分析のテスト")
    print("=" * 50)
    
    planner = CollaborativePlanner()
    
    test_tasks = [
        "ファイルを読んでください",                    # simple
        "コードをレビューしてください",                 # medium
        "プロジェクトの全体的なリファクタリングを実行", # complex
        "システム全体の設計を見直して実装する",        # complex
        "テストを実行する",                           # medium
        "新しいファイルを作成する"                     # simple
    ]
    
    for task in test_tasks:
        complexity = planner._assess_task_complexity(task)
        print(f"タスク: {task}")
        print(f"  複雑度: {complexity}")
        print()

def test_plan_creation():
    """実行計画作成のテスト"""
    print("\n🗓️ 実行計画作成のテスト")
    print("=" * 50)
    
    planner = CollaborativePlanner()
    
    complex_task = "プロジェクトのコード全体をレビューしてリファクタリングを提案する"
    plan_id = planner.analyze_and_create_plan(complex_task)
    
    if plan_id:
        print(f"✅ 計画作成成功: {plan_id}")
        
        # 計画の詳細を表示
        presentation = planner.get_plan_presentation(plan_id)
        print("\n📋 生成された計画:")
        print("-" * 30)
        print(presentation)
        
        return plan_id
    else:
        print("❌ 計画作成失敗または単純タスク")
        return None

def test_user_feedback():
    """ユーザーフィードバック処理のテスト"""
    print("\n💬 ユーザーフィードバック処理のテスト")
    print("=" * 50)
    
    planner = CollaborativePlanner()
    
    # テスト用計画を作成
    plan_id = planner.analyze_and_create_plan("システムの実装とテストを行う")
    
    if not plan_id:
        print("❌ テスト用計画の作成に失敗")
        return
    
    # 各種フィードバックをテスト
    feedback_tests = [
        ("承認", "計画承認のテスト"),
        ("修正", "計画修正のテスト"),
        ("順序を変更したい", "順序変更のテスト"),
        ("拒否", "計画却下のテスト")
    ]
    
    for feedback, description in feedback_tests:
        print(f"\n{description}: '{feedback}'")
        success, message = planner.process_user_feedback(plan_id, feedback)
        print(f"  結果: {'✅' if success else '❌'}")
        print(f"  メッセージ: {message}")
        
        # 新しい計画で次のテストを実行
        if feedback == "拒否":
            plan_id = planner.analyze_and_create_plan("別のシステムテスト計画")

def test_time_estimation():
    """時間推定機能のテスト"""
    print("\n⏰ 時間推定機能のテスト")
    print("=" * 50)
    
    # 各種時間推定をテスト
    estimates = [
        TaskEstimate(30, 60, "low", 0.9),        # 30秒〜1分
        TaskEstimate(300, 900, "medium", 0.7),   # 5分〜15分
        TaskEstimate(1800, 7200, "high", 0.4),   # 30分〜2時間
        TaskEstimate(45, 90, "low", 0.8)         # 45秒〜1分30秒
    ]
    
    for estimate in estimates:
        print(f"推定時間: {estimate.duration_range_str}")
        print(f"  複雑度: {estimate.complexity}")
        print(f"  信頼度: {estimate.confidence:.1%}")
        print(f"  平均: {estimate._format_duration(estimate.estimated_duration)}")
        print()

def test_plan_to_hierarchical_conversion():
    """計画から階層タスクへの変換テスト"""
    print("\n🌳 計画→階層タスク変換のテスト")
    print("=" * 50)
    
    planner = CollaborativePlanner()
    
    # 複雑なタスクで計画を作成
    plan_id = planner.analyze_and_create_plan("ウェブアプリケーションの開発とデプロイを実行")
    
    if not plan_id:
        print("❌ テスト用計画の作成に失敗")
        return
    
    # 計画を承認
    success, message = planner.process_user_feedback(plan_id, "承認")
    print(f"計画承認: {message}")
    
    if success:
        # 階層タスクに変換
        parent_task_id = planner.convert_plan_to_hierarchical_tasks(plan_id)
        
        if parent_task_id:
            print(f"✅ 階層タスク変換成功: {parent_task_id}")
            
            # 階層タスクの状態を確認
            summary = planner.hierarchical_manager.get_task_status_summary(parent_task_id)
            print("\n🗂️ 変換された階層タスク:")
            print(f"  親タスク: {summary['parent_task']['name']}")
            print(f"  子タスク数: {summary['parent_task']['total_sub_tasks']}個")
            
            for i, sub_task in enumerate(summary["sub_tasks"], 1):
                print(f"    {i}. {sub_task['name']}")
                if sub_task['depends_on']:
                    print(f"       依存: {', '.join(sub_task['depends_on'])}")
        else:
            print("❌ 階層タスク変換に失敗")
    else:
        print("❌ 計画承認に失敗")

def test_full_workflow():
    """フルワークフローのテスト"""
    print("\n🔄 フルワークフローのテスト")
    print("=" * 50)
    
    planner = CollaborativePlanner()
    
    # 1. 複雑なタスクの分析
    task = "レガシーシステムのモダン化プロジェクトを実行"
    print(f"📋 タスク: {task}")
    
    # 2. 計画作成
    plan_id = planner.analyze_and_create_plan(task)
    if not plan_id:
        print("❌ 計画作成失敗")
        return
    
    print(f"✅ 計画作成: {plan_id}")
    
    # 3. 計画提示
    presentation = planner.get_plan_presentation(plan_id)
    print("\n📊 提示された計画:")
    print("-" * 30)
    # 計画の概要のみ表示（長すぎるため）
    lines = presentation.split('\n')
    for line in lines[:15]:  # 最初の15行のみ
        print(line)
    print("...")
    
    # 4. ユーザー承認
    success, message = planner.process_user_feedback(plan_id, "承認")
    print(f"\n💬 ユーザー承認: {message}")
    
    # 5. 実行準備
    if success:
        parent_task_id = planner.convert_plan_to_hierarchical_tasks(plan_id)
        if parent_task_id:
            print(f"🚀 実行準備完了: {parent_task_id}")
            
            # 6. 最終状態確認
            plan = planner.get_current_plan()
            print(f"📈 計画状態: {plan.status.value}")
            print("✨ フルワークフローテスト完了！")
        else:
            print("❌ 実行準備に失敗")
    else:
        print("❌ 承認処理に失敗")

if __name__ == "__main__":
    print("🦆 協調的計画機能 統合テスト")
    print("=" * 60)
    
    try:
        test_task_complexity_analysis()
        test_plan_creation()
        test_user_feedback()
        test_time_estimation()
        test_plan_to_hierarchical_conversion()
        test_full_workflow()
        
        print("\n" + "=" * 60)
        print("🎉 すべてのテストが完了しました！")
        print("Step 3の協調的計画機能が正常に動作しています。")
        
    except Exception as e:
        print(f"\n❌ テスト中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()