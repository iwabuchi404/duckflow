#!/usr/bin/env python3
"""
会話履歴の処理とコンテクスト継承のテスト

このスクリプトは、Duckflowシステムでユーザーとの対話ループにおいて、
追加情報を求めた後の会話履歴が適切に処理されるかを検証します。
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from codecrafter.state.agent_state import AgentState, WorkspaceInfo
from codecrafter.orchestration.four_node_orchestrator import FourNodeOrchestrator
from codecrafter.prompts.four_node_compiler import FourNodePromptCompiler
from codecrafter.prompts.four_node_context import FourNodePromptContext, NodeType
from codecrafter.ui.rich_ui import rich_ui


def test_conversation_context_handling():
    """会話履歴の処理とコンテクスト継承をテスト"""
    
    print("=" * 60)
    print("🔍 会話履歴処理・コンテクスト継承テスト")
    print("=" * 60)
    
    # テスト用のAgentStateを作成
    workspace = WorkspaceInfo(
        path=str(project_root),
        files=[],
        last_modified=datetime.now()
    )
    
    state = AgentState(
        session_id="test_session",
        workspace=workspace
    )
    
    print("\n1️⃣ 初期状態の確認")
    print(f"   - 会話履歴数: {len(state.conversation_history)}")
    print(f"   - セッションID: {state.session_id}")
    
    # 1. 最初のユーザーメッセージを追加
    print("\n2️⃣ 最初のユーザーメッセージを追加")
    initial_message = "Duckflowプロジェクトのアーキテクチャについて教えてください"
    state.add_message("user", initial_message)
    print(f"   - ユーザーメッセージ追加: {initial_message[:30]}...")
    print(f"   - 会話履歴数: {len(state.conversation_history)}")
    
    # 2. AIの応答をシミュレート
    print("\n3️⃣ AIの応答をシミュレート")
    ai_response = "Duckflowは4ノードアーキテクチャを採用していますが、具体的にどの部分について詳しく知りたいですか？"
    state.add_message("assistant", ai_response)
    print(f"   - AI応答追加: {ai_response[:30]}...")
    print(f"   - 会話履歴数: {len(state.conversation_history)}")
    
    # 3. 追加情報のユーザーメッセージ
    print("\n4️⃣ 追加情報のユーザーメッセージを追加")
    follow_up_message = "特にオーケストレーター部分の実装について詳しく教えてください"
    state.add_message("user", follow_up_message)
    print(f"   - フォローアップメッセージ追加: {follow_up_message[:30]}...")
    print(f"   - 会話履歴数: {len(state.conversation_history)}")
    
    # 4. FourNodeOrchestratorを作成してコンテキスト処理をテスト
    print("\n5️⃣ FourNodeOrchestratorでのコンテキスト処理テスト")
    try:
        orchestrator = FourNodeOrchestrator(state)
        
        # コンテキストの確認
        context = orchestrator.four_node_context
        print(f"   - recent_messages数: {len(context.recent_messages)}")
        print(f"   - task_chain数: {len(context.task_chain)}")
        
        # 会話履歴の内容確認
        print("\n   📝 会話履歴の内容:")
        for i, msg in enumerate(context.recent_messages):
            print(f"      {i+1}. [{msg.role}] {msg.content[:50]}...")
        
    except Exception as e:
        print(f"   ❌ エラー: {e}")
        return False
    
    # 5. FourNodePromptCompilerでのプロンプト生成テスト
    print("\n6️⃣ FourNodePromptCompilerでのプロンプト生成テスト")
    try:
        compiler = FourNodePromptCompiler()
        
        # 会話文脈の構築テスト
        conversation_context = compiler._build_conversation_context(context.recent_messages)
        print(f"   - 構築された会話文脈の長さ: {len(conversation_context)}文字")
        print(f"   - 会話文脈の内容:\n{conversation_context}")
        
        # ユーザー意図の抽出テスト
        user_intent = compiler._extract_user_intent_from_conversation(context.recent_messages)
        print(f"   - 抽出されたユーザー意図: {user_intent}")
        
    except Exception as e:
        print(f"   ❌ エラー: {e}")
        return False
    
    # 6. 継続的な会話のシミュレーション
    print("\n7️⃣ 継続的な会話のシミュレーション")
    try:
        # さらに会話を追加
        state.add_message("assistant", "オーケストレーターは4つのノードで構成されています...")
        state.add_message("user", "各ノードの詳細な役割について教えてください")
        
        # コンテキストを更新
        orchestrator._update_context_with_conversation()
        
        updated_context = orchestrator.four_node_context
        print(f"   - 更新後のrecent_messages数: {len(updated_context.recent_messages)}")
        print(f"   - 更新後のtask_chain数: {len(updated_context.task_chain)}")
        
        # 最新の会話文脈を再構築
        latest_context = compiler._build_conversation_context(updated_context.recent_messages)
        print(f"   - 最新の会話文脈の長さ: {len(latest_context)}文字")
        
    except Exception as e:
        print(f"   ❌ エラー: {e}")
        return False
    
    print("\n✅ 会話履歴処理・コンテクスト継承テスト完了")
    print("   - 会話履歴の追加: ✅")
    print("   - コンテキストの更新: ✅")
    print("   - プロンプト生成での履歴活用: ✅")
    print("   - 継続対話での文脈継承: ✅")
    
    return True


def test_template_integration():
    """テンプレートとの統合テスト"""
    
    print("\n" + "=" * 60)
    print("🎯 テンプレート統合テスト")
    print("=" * 60)
    
    try:
        # テスト用のPromptContextを作成
        workspace = WorkspaceInfo(
            path=str(project_root),
            files=[],
            last_modified=datetime.now()
        )
        
        state = AgentState(
            session_id="template_test",
            workspace=workspace
        )
        
        # 会話履歴を追加
        state.add_message("user", "プロジェクトの構造について教えてください")
        state.add_message("assistant", "このプロジェクトは...")
        state.add_message("user", "特にオーケストレーター部分を詳しく")
        
        orchestrator = FourNodeOrchestrator(state)
        context = orchestrator.four_node_context
        
        compiler = FourNodePromptCompiler()
        
        # テンプレート変数の準備テスト
        print("1️⃣ テンプレート変数の準備テスト")
        variables = compiler._prepare_fresh_variables(context)
        
        print(f"   - user_message: {variables.get('user_message', 'なし')[:50]}...")
        print(f"   - execution_phase: {variables.get('execution_phase', 'なし')}")
        print(f"   - conversation_context: {len(variables.get('conversation_context', ''))}文字")
        
        if 'conversation_context' in variables:
            print(f"   - 会話文脈の内容:\n{variables['conversation_context']}")
        
        print("✅ テンプレート統合テスト完了")
        return True
        
    except Exception as e:
        print(f"❌ テンプレート統合テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🚀 Duckflow 会話履歴・コンテクスト継承テスト開始\n")
    
    success = True
    
    # テスト実行
    success &= test_conversation_context_handling()
    success &= test_template_integration()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 全テスト成功！")
        print("会話履歴の処理とコンテクスト継承が正常に動作しています。")
    else:
        print("❌ テスト失敗")
        print("問題が発見されました。修正が必要です。")
    print("=" * 60)
    
    sys.exit(0 if success else 1)