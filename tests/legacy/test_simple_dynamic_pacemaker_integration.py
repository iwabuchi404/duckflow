#!/usr/bin/env python3
"""
シンプル動的Duck Pacemakerの統合テスト
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from codecrafter.state.agent_state import AgentState, Vitals
from codecrafter.services.task_classifier import TaskProfileType
from codecrafter.pacemaker import (
    SimpleLoopCalculator,
    SimpleContextAnalyzer, 
    SimpleFallback,
    SimpleDynamicPacemaker,
    UserConsultation,
    InterventionPattern
)


def test_simple_loop_calculator():
    """シンプル制限計算器のテスト"""
    print("\n=== シンプル制限計算器テスト ===")
    
    calculator = SimpleLoopCalculator()
    
    # テストケース1: 一般的な対話、良好なバイタル
    vitals_good = Vitals(mood=0.9, focus=0.8, stamina=0.9)
    result1 = calculator.calculate_max_loops(
        task_profile=TaskProfileType.GENERAL_CHAT,
        vitals=vitals_good,
        context_complexity=0.3
    )
    
    print(f"テスト1 (一般対話、良好状態):")
    print(f"  最大ループ: {result1['max_loops']}回")
    print(f"  ベース: {result1['base_loops']}回")
    print(f"  バイタル係数: {result1['vitals_factor']:.1f}")
    print(f"  複雑度係数: {result1['complexity_factor']:.1f}")
    
    # テストケース2: 実装タスク、疲労状態
    vitals_tired = Vitals(mood=0.3, focus=0.2, stamina=0.1)
    result2 = calculator.calculate_max_loops(
        task_profile=TaskProfileType.IMPLEMENTATION_TASK,
        vitals=vitals_tired,
        context_complexity=0.8
    )
    
    print(f"\nテスト2 (実装タスク、疲労状態):")
    print(f"  最大ループ: {result2['max_loops']}回")
    print(f"  ベース: {result2['base_loops']}回")
    print(f"  バイタル係数: {result2['vitals_factor']:.1f}")
    print(f"  複雑度係数: {result2['complexity_factor']:.1f}")
    
    return result1['max_loops'] > 0 and result2['max_loops'] > 0


def test_simple_context_analyzer():
    """シンプルコンテキスト分析器のテスト"""
    print("\n=== シンプルコンテキスト分析器テスト ===")
    
    # テスト用のモックAgentState
    class MockState:
        def __init__(self, file_count=0, history_length=0, error_count=0, tool_executions=0):
            self.collected_context = {
                "gathered_info": {
                    "collected_files": {f"file_{i}.py": {} for i in range(file_count)}
                }
            }
            self.conversation_history = [f"message_{i}" for i in range(history_length)]
            self.error_count = error_count
            self.tool_executions = [f"tool_{i}" for i in range(tool_executions)]
    
    # テストケース1: シンプルな状況
    mock_state1 = MockState(file_count=2, history_length=5, error_count=0, tool_executions=10)
    complexity1 = SimpleContextAnalyzer.analyze_complexity(mock_state1)
    
    print(f"テスト1 (シンプル): 複雑度 {complexity1:.2f}")
    
    # テストケース2: 複雑な状況
    mock_state2 = MockState(file_count=10, history_length=20, error_count=5, tool_executions=10)
    complexity2 = SimpleContextAnalyzer.analyze_complexity(mock_state2)
    
    print(f"テスト2 (複雑): 複雑度 {complexity2:.2f}")
    
    # 詳細分析テスト
    detailed = SimpleContextAnalyzer.get_detailed_analysis(mock_state2)
    print(f"詳細分析: {detailed['description']}")
    
    return 0 <= complexity1 <= 1 and 0 <= complexity2 <= 1


def test_simple_fallback():
    """シンプルフォールバックのテスト"""
    print("\n=== シンプルフォールバックテスト ===")
    
    fallback = SimpleFallback()
    
    # フォールバック情報取得
    info = fallback.get_fallback_info()
    print(f"最終フォールバック値: {info['final_fallback_value']}回")
    print(f"設定ファイル最大値: {info['config_max_loops']}")
    
    # フォールバックテスト実行
    test_result = fallback.test_fallback()
    print(f"フォールバックテスト結果: {test_result['overall_status']}")
    
    return test_result['overall_status'] in ['正常', '成功']


def test_simple_dynamic_pacemaker():
    """シンプル動的Duck Pacemakerのテスト"""
    print("\n=== シンプル動的Duck Pacemakerテスト ===")
    
    # テスト用AgentStateを作成
    test_state = AgentState(
        session_id="test_session_001",
        vitals=Vitals(mood=0.8, focus=0.7, stamina=0.9)
    )
    
    # 簡単な対話履歴を追加
    test_state.add_message("user", "このPythonコードを分析してください。")
    
    # シンプル動的Duck Pacemakerを初期化
    pacemaker = SimpleDynamicPacemaker()
    
    # システム情報取得
    system_info = pacemaker.get_system_info()
    print(f"システム: {system_info['system_name']} v{system_info['version']}")
    
    # セッション開始
    print("セッション開始...")
    start_result = pacemaker.start_session(
        state=test_state,
        task_profile=TaskProfileType.FILE_ANALYSIS
    )
    
    print(f"動的制限設定結果:")
    print(f"  最大ループ: {start_result['max_loops']}回")
    print(f"  複雑度: {start_result['context_complexity']:.2f}")
    
    # 実行中の更新をシミュレート
    print("\n実行中の動的更新をシミュレート...")
    for loop in range(1, 4):
        test_state.graph_state.loop_count = loop
        
        # バイタルを徐々に変化させる
        test_state.vitals.stamina -= 0.1
        test_state.vitals.focus -= 0.05
        
        update_result = pacemaker.update_during_execution(
            state=test_state,
            current_loop=loop
        )
        
        print(f"  ループ {loop}: {update_result['recommendation']}, バイタル: {update_result['vitals_status']}")
        
        if update_result["intervention_required"]:
            print(f"    ⚠️ 介入が必要です！")
            break
    
    # セッション終了
    print("\nセッション終了...")
    end_result = pacemaker.end_session(
        state=test_state,
        success=True,
        loops_used=3
    )
    
    print(f"効率: {end_result.get('efficiency', 0):.1%}")
    
    return start_result['max_loops'] > 0


def test_user_consultation():
    """ユーザー相談システムのテスト"""
    print("\n=== ユーザー相談システムテスト ===")
    
    consultation = UserConsultation()
    
    # 全パターン情報を取得
    patterns = consultation.get_all_patterns()
    print(f"サポートされている介入パターン: {len(patterns)}種類")
    
    for pattern_name, pattern_info in patterns.items():
        print(f"  - {pattern_info['title']}")
    
    # 特定パターンの情報取得
    pattern_info = consultation.get_pattern_info(InterventionPattern.PROGRESS_STAGNATION)
    print(f"\n進捗停滞パターンの選択肢数: {len(pattern_info['options'])}")
    
    return len(patterns) == 4


def test_system_integration():
    """システム統合テスト"""
    print("\n=== システム統合テスト ===")
    
    pacemaker = SimpleDynamicPacemaker()
    
    # システムテスト実行
    test_results = pacemaker.test_system()
    print(f"システムテスト結果: {test_results['overall_status']}")
    
    for test_name, result in test_results.items():
        if test_name != 'overall_status':
            print(f"  {test_name}: {result}")
    
    return test_results['overall_status'] in ['正常', '成功']


def main():
    """メインテスト実行"""
    print("🦆 シンプル動的Duck Pacemaker統合テスト開始")
    print("=" * 60)
    
    test_results = []
    
    try:
        # 各テストを実行
        test_results.append(("制限計算器", test_simple_loop_calculator()))
        test_results.append(("コンテキスト分析器", test_simple_context_analyzer()))
        test_results.append(("フォールバック", test_simple_fallback()))
        test_results.append(("動的Pacemaker", test_simple_dynamic_pacemaker()))
        test_results.append(("ユーザー相談", test_user_consultation()))
        test_results.append(("システム統合", test_system_integration()))
        
        print("\n" + "=" * 60)
        print("📊 テスト結果サマリー:")
        
        passed = 0
        for test_name, result in test_results:
            status = "✅ 成功" if result else "❌ 失敗"
            print(f"  {test_name}: {status}")
            if result:
                passed += 1
        
        print(f"\n総合結果: {passed}/{len(test_results)} テスト成功")
        
        if passed == len(test_results):
            print("🎉 全てのテストが成功しました！")
            print("シンプル動的Duck Pacemakerシステムは正常に動作しています。")
        else:
            print("⚠️ 一部のテストが失敗しました。")
        
    except Exception as e:
        print(f"\n❌ テスト中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()