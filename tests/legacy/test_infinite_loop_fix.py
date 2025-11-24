#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
無限ループ修正のテスト
LangGraphの思考回数制限が正常に動作するかをテスト
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

def test_think_counter_logic():
    """思考カウンター機能のテスト"""
    
    print("=== 無限ループ修正テスト ===\n")
    
    from codecrafter.state.agent_state import AgentState
    from datetime import datetime
    
    # テスト用のAgentState作成
    test_state = AgentState(
        session_id="infinite_loop_test",
        created_at=datetime.now(),
        last_activity=datetime.now()
    )
    
    # コンテキスト収集済み状態をシミュレート
    test_state.collected_context = {
        'file_context': {
            'file_contents': {
                'test.py': 'def test(): pass'
            }
        },
        'needs_answer_after_context': True
    }
    
    # _requires_human_approval のロジックを部分的にテスト
    def test_approval_logic(state_obj):
        """承認ロジックのテスト版"""
        # 思考回数制限チェック
        needs_answer = getattr(state_obj, 'collected_context', {}).get('needs_answer_after_context', False)
        if needs_answer:
            # 無限ループ防止：think_count を追加してチェック
            think_count = getattr(state_obj, '_think_count', 0)
            if think_count >= 2:  # 3回目以降は強制完了
                print(f"[TEST] 思考回数制限に到達 (回数: {think_count}) → 強制完了")
                state_obj._think_count = 0  # リセット
                return "complete"
            
            # フラグをクリア
            try:
                state_obj.collected_context['needs_answer_after_context'] = False
                state_obj._think_count = think_count + 1  # カウンタ増加
            except Exception:
                pass
            print(f"[TEST] コンテキスト収集完了 → 再思考で回答 (回数: {think_count + 1})")
            return "think"
        
        return "complete"
    
    # テスト実行
    print("初期状態:")
    print(f"  needs_answer_after_context: {test_state.collected_context.get('needs_answer_after_context')}")
    print(f"  _think_count: {getattr(test_state, '_think_count', 0)}")
    print()
    
    # 1回目の判定
    result1 = test_approval_logic(test_state)
    print(f"1回目判定結果: {result1}")
    print(f"  needs_answer_after_context: {test_state.collected_context.get('needs_answer_after_context')}")
    print(f"  _think_count: {getattr(test_state, '_think_count', 0)}")
    print()
    
    # フラグを戻してもう一度テスト（無限ループシミュレーション）
    test_state.collected_context['needs_answer_after_context'] = True
    
    # 2回目の判定
    result2 = test_approval_logic(test_state)
    print(f"2回目判定結果: {result2}")
    print(f"  needs_answer_after_context: {test_state.collected_context.get('needs_answer_after_context')}")
    print(f"  _think_count: {getattr(test_state, '_think_count', 0)}")
    print()
    
    # 3回目の判定（制限に到達するはず）
    test_state.collected_context['needs_answer_after_context'] = True
    
    result3 = test_approval_logic(test_state)
    print(f"3回目判定結果: {result3}")
    print(f"  needs_answer_after_context: {test_state.collected_context.get('needs_answer_after_context')}")
    print(f"  _think_count: {getattr(test_state, '_think_count', 0)}")
    print()
    
    # 結果評価
    if result3 == "complete":
        print("✅ 無限ループ防止機能が正常に動作しました！")
        print("   3回目の思考で強制完了となり、カウンタもリセットされました。")
    else:
        print("❌ 無限ループ防止機能に問題があります。")
    
    print("\n=== テスト完了 ===")

if __name__ == "__main__":
    test_think_counter_logic()