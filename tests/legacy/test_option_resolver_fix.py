#!/usr/bin/env python3
"""
OptionResolver修正の動作確認テスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from companion.intent_understanding.intent_integration import OptionResolver

def test_creation_requests_not_detected_as_selection():
    """新規作成要求が選択入力として誤認識されないことを確認"""
    creation_requests = [
        "ドキュメントをベースに実装プランを作成してください",
        "新しいファイルを作成してください", 
        "実装してください",
        "作成してください",
        "実装を開始してください",
        "機能を実装してください",
        "コードを作成してください"
    ]
    
    print("[TEST] 新規作成要求の選択入力検出テスト")
    for request in creation_requests:
        is_selection = OptionResolver.is_selection_input(request)
        selection_num = OptionResolver.parse_selection(request)
        print(f"   '{request[:30]}...' -> 選択入力: {is_selection}, 選択番号: {selection_num}")
        
        # 新規作成要求は選択入力として検出されるべきではない
        assert not is_selection, f"新規作成要求が選択入力として誤検出: {request}"
        assert selection_num is None, f"新規作成要求に選択番号が割り当てられた: {request}"
    
    print("[OK] 新規作成要求が選択入力として誤検出されないことを確認")

def test_valid_selections_still_detected():
    """有効な選択入力が正しく検出されることを確認"""
    valid_selections = [
        ("1", 1),
        ("2", 2), 
        ("はい", 1),
        ("ok", 1),
        ("デフォルト", 1),
        ("推奨", 1),
        ("それで", 1),
        ("了解", 1),
        ("実行", 1)
    ]
    
    print("\n[TEST] 有効な選択入力の検出テスト")
    for selection_text, expected_num in valid_selections:
        is_selection = OptionResolver.is_selection_input(selection_text)
        selection_num = OptionResolver.parse_selection(selection_text)
        print(f"   '{selection_text}' -> 選択入力: {is_selection}, 選択番号: {selection_num}")
        
        # 有効な選択入力は正しく検出されるべき
        assert is_selection, f"有効な選択入力が検出されない: {selection_text}"
        assert selection_num == expected_num, f"選択番号が不正: {selection_text} -> 期待値{expected_num}, 実際{selection_num}"
    
    print("[OK] 有効な選択入力が正しく検出されることを確認")

def test_ambiguous_inputs():
    """曖昧な入力の処理を確認"""
    ambiguous_inputs = [
        "お願いします",  # 文脈次第で選択にも新規要求にもなる
        "進めてください",  # 選択承認か新規要求か曖昧
        "続行してください",  # 選択承認か新規要求か曖昧
    ]
    
    print("\n[TEST] 曖昧な入力の処理テスト")
    for input_text in ambiguous_inputs:
        is_selection = OptionResolver.is_selection_input(input_text)
        selection_num = OptionResolver.parse_selection(input_text)
        print(f"   '{input_text}' -> 選択入力: {is_selection}, 選択番号: {selection_num}")
    
    print("[OK] 曖昧な入力の処理確認完了")

if __name__ == "__main__":
    print("[START] OptionResolver修正の動作確認テスト開始\n")
    
    try:
        test_creation_requests_not_detected_as_selection()
        test_valid_selections_still_detected()
        test_ambiguous_inputs()
        
        print("\n[SUCCESS] 全てのテストに合格しました！")
        print("   - 新規作成要求が選択入力として誤検出されない")
        print("   - 有効な選択入力は正しく検出される")
        print("   - OptionResolver修正が正常に機能している")
        
    except AssertionError as e:
        print(f"\n[FAILED] テスト失敗: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] テスト実行エラー: {e}")
        sys.exit(1)