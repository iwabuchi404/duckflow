#!/usr/bin/env python3
"""
動的Duck Pacemakerのテストスクリプト
"""

import sys
import asyncio
from datetime import datetime
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from codecrafter.state.agent_state import AgentState, Vitals
from codecrafter.services.task_classifier import TaskProfileType
from codecrafter.pacemaker import DynamicDuckPacemaker, AdaptiveLoopCalculator
from codecrafter.ui.rich_ui import rich_ui


def test_adaptive_loop_calculator():
    """適応的ループ計算器のテスト"""
    print("\n=== 適応的ループ計算器テスト ===")
    
    calculator = AdaptiveLoopCalculator()
    
    # テストケース1: 簡単な質問、良好なバイタル
    vitals_good = Vitals(mood=0.9, focus=0.8, stamina=0.9)
    result1 = calculator.calculate_max_loops(
        task_profile=TaskProfileType.SIMPLE_QUESTION,
        vitals=vitals_good,
        user_urgency=0.3,
        context_complexity=0.2,
        success_rate=0.9
    )
    
    print(f"テスト1 (簡単な質問、良好状態):")
    print(f"  最大ループ: {result1['max_loops']}回")
    print(f"  ティア: {result1['tier']}")
    print(f"  理由: {result1['reasoning']}")
    
    # テストケース2: 複雑な推論、疲労状態
    vitals_tired = Vitals(mood=0.4, focus=0.3, stamina=0.2)
    result2 = calculator.calculate_max_loops(
        task_profile=TaskProfileType.COMPLEX_REASONING,
        vitals=vitals_tired,
        user_urgency=0.8,
        context_complexity=0.9,
        success_rate=0.5
    )
    
    print(f"\nテスト2 (複雑な推論、疲労状態):")
    print(f"  最大ループ: {result2['max_loops']}回")
    print(f"  ティア: {result2['tier']}")
    print(f"  理由: {result2['reasoning']}")
    
    # テストケース3: コード分析、バランス状態
    vitals_balanced = Vitals(mood=0.7, focus=0.6, stamina=0.7)
    result3 = calculator.calculate_max_loops(
        task_profile=TaskProfileType.CODE_ANALYSIS,
        vitals=vitals_balanced,
        user_urgency=0.5,
        context_complexity=0.6,
        success_rate=0.8
    )
    
    print(f"\nテスト3 (コード分析、バランス状態):")
    print(f"  最大ループ: {result3['max_loops']}回")
    print(f"  ティア: {result3['tier']}")
    print(f"  理由: {result3['reasoning']}")


def test_dynamic_duck_pacemaker():
    """動的Duck Pacemakerのテスト"""
    print("\n=== 動的Duck Pacemakerテスト ===")
    
    # テスト用AgentStateを作成
    test_state = AgentState(
        session_id="test_session_001",
        vitals=Vitals(mood=0.8, focus=0.7, stamina=0.9)
    )
    
    # 簡単な対話履歴を追加
    test_state.add_message("user", "このPythonコードを分析して、バグを見つけてください。急いでいます。")
    
    # 動的Duck Pacemakerを初期化
    pacemaker = DynamicDuckPacemaker()
    
    # セッション開始
    print("セッション開始...")
    start_result = pacemaker.start_session(
        state=test_state,
        task_profile=TaskProfileType.CODE_ANALYSIS
    )
    
    print(f"動的制限設定結果:")
    print(f"  最大ループ: {start_result['max_loops']}回")
    print(f"  複雑度: {start_result['context_complexity']:.2f}")
    print(f"  緊急度: {start_result['user_urgency']:.2f}")
    print(f"  成功率: {start_result['success_rate']:.2f}")
    
    # 実行中の更新をシミュレート
    print("\n実行中の動的更新をシミュレート...")
    for loop in range(1, 6):
        test_state.graph_state.loop_count = loop
        
        # バイタルを徐々に悪化させる
        test_state.vitals.stamina -= 0.1
        test_state.vitals.focus -= 0.05
        
        update_result = pacemaker.update_during_execution(
            state=test_state,
            current_loop=loop
        )
        
        print(f"  ループ {loop}: 進捗率 {update_result['progress_rate']:.1%}, "
              f"バイタル状態 {update_result['vitals_status']}, "
              f"推奨: {update_result.get('recommendation', 'なし')}")
        
        if update_result["intervention_required"]:
            print(f"    ⚠️ 介入が必要です！")
            break
    
    # セッション終了
    print("\nセッション終了...")
    pacemaker.end_session(
        state=test_state,
        success=True
    )
    
    # パフォーマンス要約
    summary = pacemaker.get_performance_summary()
    print(f"\nパフォーマンス要約:")
    print(f"  総セッション数: {summary['overall_stats']['total_sessions']}")
    print(f"  全体成功率: {summary['overall_stats']['overall_success_rate']:.2%}")


def test_vitals_intervention():
    """バイタル介入テスト"""
    print("\n=== バイタル介入テスト ===")
    
    # 危険状態のテスト
    critical_state = AgentState(
        session_id="critical_test",
        vitals=Vitals(mood=0.3, focus=0.2, stamina=0.05)  # 危険状態
    )
    
    intervention = critical_state.needs_duck_intervention()
    print(f"危険状態テスト:")
    print(f"  介入必要: {intervention['required']}")
    print(f"  理由: {intervention['reason']}")
    print(f"  アクション: {intervention['action']}")
    print(f"  優先度: {intervention.get('priority', 'なし')}")
    
    # 集中力低下のテスト
    focus_low_state = AgentState(
        session_id="focus_test",
        vitals=Vitals(mood=0.8, focus=0.25, stamina=0.7)  # 集中力低下
    )
    
    intervention2 = focus_low_state.needs_duck_intervention()
    print(f"\n集中力低下テスト:")
    print(f"  介入必要: {intervention2['required']}")
    print(f"  理由: {intervention2['reason']}")
    print(f"  アクション: {intervention2['action']}")
    print(f"  優先度: {intervention2.get('priority', 'なし')}")
    
    # 正常状態のテスト
    normal_state = AgentState(
        session_id="normal_test",
        vitals=Vitals(mood=0.8, focus=0.8, stamina=0.9)  # 正常状態
    )
    
    intervention3 = normal_state.needs_duck_intervention()
    print(f"\n正常状態テスト:")
    print(f"  介入必要: {intervention3['required']}")
    print(f"  バイタル状態: {intervention3['vitals_status']}")


def main():
    """メインテスト実行"""
    print("🦆 動的Duck Pacemakerテスト開始")
    print("=" * 50)
    
    try:
        # 各テストを実行
        test_adaptive_loop_calculator()
        test_dynamic_duck_pacemaker()
        test_vitals_intervention()
        
        print("\n" + "=" * 50)
        print("✅ 全てのテストが完了しました！")
        
    except Exception as e:
        print(f"\n❌ テスト中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()