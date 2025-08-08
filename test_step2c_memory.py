#!/usr/bin/env python3
"""
ステップ2c: 記憶管理機能のテスト
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from codecrafter.main_v2 import DuckflowAgentV2
from codecrafter.memory.conversation_memory import conversation_memory
from codecrafter.state.agent_state import ConversationMessage
from datetime import datetime

def test_memory_system():
    """記憶管理システムの包括テスト"""
    print("=== ステップ2c: 記憶管理機能テスト ===")
    
    # エージェント初期化
    agent = DuckflowAgentV2()
    agent.state.debug_mode = True
    
    print(f"\n1. 初期状態:")
    print(f"   - 対話数: {len(agent.state.conversation_history)}")
    print(f"   - 要約: {'あり' if agent.state.history_summary else 'なし'}")
    
    # 複数ターンの対話をシミュレーション
    print(f"\n2. 対話シミュレーション（10ターン）:")
    for i in range(10):
        user_msg = f"テスト質問 {i+1}: Pythonでファイル操作について教えて"
        ai_msg = f"回答 {i+1}: Pythonでファイル操作を行う場合、pathlib モジュールを使用することを推奨します。"
        
        agent.state.add_message("user", user_msg)
        agent.state.add_message("assistant", ai_msg)
        
        print(f"   ターン {i+1}: 対話数={len(agent.state.conversation_history)}")
    
    # 記憶状態を確認
    print(f"\n3. 記憶状態確認:")
    memory_status = agent.state.get_memory_status()
    print(f"   - 総メッセージ数: {memory_status.get('total_messages', 0)}")
    print(f"   - 要約が必要: {memory_status.get('needs_summary', False)}")
    print(f"   - トークン数: {memory_status.get('total_tokens', 0)}")
    
    # 手動要約テスト
    print(f"\n4. 手動要約テスト:")
    if agent.state.create_memory_summary():
        print("   [OK] 要約作成成功")
        print(f"   - 要約後の対話数: {len(agent.state.conversation_history)}")
        print(f"   - 要約長: {len(agent.state.history_summary) if agent.state.history_summary else 0}文字")
        
        if agent.state.history_summary:
            print(f"   - 要約内容 (最初の200文字):")
            print(f"     {agent.state.history_summary[:200]}...")
    else:
        print("   [ERROR] 要約作成失敗")
    
    # 記憶コンテキスト取得テスト
    print(f"\n5. 記憶コンテキスト取得テスト:")
    memory_context = agent.state.get_memory_context()
    if memory_context:
        print(f"   [OK] 記憶コンテキスト取得成功 ({len(memory_context)}文字)")
        print(f"   - 内容 (最初の300文字):")
        print(f"     {memory_context[:300]}...")
    else:
        print("   - 記憶コンテキストなし")
    
    # さらに対話を追加して自動要約トリガーをテスト
    print(f"\n6. 自動要約トリガーテスト:")
    for i in range(15):  # さらに15ターン追加
        user_msg = f"追加質問 {i+1}: データ構造について詳しく教えて"
        ai_msg = f"追加回答 {i+1}: Pythonの主要なデータ構造には、リスト、タプル、辞書、集合があります。それぞれに特徴があり..."
        
        agent.state.add_message("user", user_msg)
        agent.state.add_message("assistant", ai_msg)
    
    # 要約トリガー確認
    print(f"   - 現在の対話数: {len(agent.state.conversation_history)}")
    print(f"   - 要約必要性: {agent.state.needs_memory_management()}")
    
    if agent.state.needs_memory_management():
        print("   [OK] 自動要約が必要と判定")
        if agent.state.create_memory_summary():
            print("   [OK] 自動要約実行成功")
        else:
            print("   [ERROR] 自動要約実行失敗")
    
    # 最終状態
    print(f"\n7. 最終状態:")
    final_status = agent.state.get_memory_status()
    print(f"   - 最終対話数: {final_status.get('total_messages', 0)}")
    print(f"   - 要約状態: {'あり' if agent.state.history_summary else 'なし'}")
    print(f"   - 元の対話数: {agent.state.original_conversation_length}")
    print(f"   - 要約作成時刻: {agent.state.summary_created_at}")

def test_conversation_memory_direct():
    """ConversationMemory クラスの直接テスト"""
    print(f"\n=== ConversationMemory 直接テスト ===")
    
    # テスト用メッセージ作成
    messages = []
    for i in range(8):
        messages.append(ConversationMessage(
            role="user",
            content=f"テスト質問 {i+1}: 詳細な技術的な質問です。" + "詳細な内容を含む長いメッセージです。" * 10,
            timestamp=datetime.now()
        ))
        messages.append(ConversationMessage(
            role="assistant", 
            content=f"テスト回答 {i+1}: 詳細な技術的回答を提供します。" + "回答の詳細な説明が続きます。" * 15,
            timestamp=datetime.now()
        ))
    
    print(f"1. テストメッセージ作成: {len(messages)}件")
    
    # トークン数計算
    total_tokens = conversation_memory.calculate_conversation_tokens(messages)
    print(f"2. 総トークン数: {total_tokens}")
    
    # 要約必要性判定
    needs_summary = conversation_memory.should_summarize(messages)
    print(f"3. 要約が必要: {needs_summary}")
    
    if needs_summary:
        # 要約作成テスト
        print(f"4. 要約作成テスト:")
        try:
            summary = conversation_memory.create_conversation_summary(messages)
            print(f"   [OK] 要約作成成功 ({len(summary)}文字)")
            print(f"   - 要約内容:")
            print(f"     {summary[:200]}...")
            
            # 履歴トリムテスト
            updated_summary, trimmed = conversation_memory.trim_conversation_history(messages, summary)
            print(f"   [OK] 履歴トリム完了: {len(messages)} → {len(trimmed)}メッセージ")
            
        except Exception as e:
            print(f"   [ERROR] 要約作成エラー: {e}")
    
    # メモリ状態取得
    memory_status = conversation_memory.get_memory_status(messages)
    print(f"5. メモリ状態:")
    for key, value in memory_status.items():
        print(f"   - {key}: {value}")

if __name__ == "__main__":
    try:
        test_memory_system()
        test_conversation_memory_direct()
        print(f"\n[OK] ステップ2c記憶管理機能のテスト完了")
    except Exception as e:
        print(f"\n[ERROR] テストエラー: {e}")
        import traceback
        traceback.print_exc()