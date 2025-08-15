#!/usr/bin/env python3
"""
Enhanced Dual-Loop System テストスクリプト
Step 2統合機能のテスト
"""

import sys
import asyncio
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from companion.enhanced_dual_loop import EnhancedDualLoopSystem
    from companion.enhanced_core import EnhancedCompanionCore
    from codecrafter.ui.rich_ui import rich_ui
except ImportError as e:
    print(f"❌ インポートエラー: {e}")
    sys.exit(1)


async def test_enhanced_companion_core():
    """EnhancedCompanionCoreの基本機能テスト"""
    print("🧪 EnhancedCompanionCore テスト開始")
    
    # EnhancedCompanionCoreを作成
    enhanced_companion = EnhancedCompanionCore("test-session-001")
    
    # 基本情報確認
    agent_state = enhanced_companion.get_agent_state()
    print(f"📋 セッションID: {agent_state.session_id}")
    print(f"🧠 拡張モード: {enhanced_companion.use_enhanced_mode}")
    
    # 意図理解テスト
    test_messages = [
        "こんにちは！",
        "design-doc_v3.mdの内容を確認してください",
        "新しいPythonファイルを作成してください",
        "プロジェクトの概要を教えて"
    ]
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n--- テスト {i}: {message} ---")
        
        try:
            # 意図理解テスト
            intent_result = await enhanced_companion.analyze_intent_only(message)
            print(f"🎯 ActionType: {intent_result['action_type'].value}")
            print(f"🧠 拡張モード: {intent_result.get('enhanced_mode', False)}")
            
            # 処理テスト（簡易版）
            if intent_result['action_type'].value == "direct_response":
                response = await enhanced_companion.process_with_intent_result(intent_result)
                print(f"💬 応答: {response[:100]}...")
            else:
                print(f"📋 タスクとして処理される予定")
                
        except Exception as e:
            print(f"❌ エラー: {e}")
    
    # セッションサマリー確認
    summary = enhanced_companion.get_session_summary()
    print(f"\n📊 セッションサマリー:")
    print(f"  - 総メッセージ数: {summary.get('total_messages', 0)}")
    print(f"  - 記憶管理状態: {summary.get('memory_status', {})}")
    print(f"  - 拡張モード: {summary.get('enhanced_mode', False)}")
    
    print("✅ EnhancedCompanionCore テスト完了")


def test_enhanced_dual_loop_system_status():
    """EnhancedDualLoopSystemの状態確認テスト"""
    print("\n🧪 EnhancedDualLoopSystem 状態テスト開始")
    
    # システム作成
    system = EnhancedDualLoopSystem("test-session-002")
    
    # 状態確認
    status = system.get_status()
    print(f"📋 システム状態:")
    print(f"  - セッションID: {status.get('session_id')}")
    print(f"  - 拡張モード: {status.get('enhanced_mode')}")
    print(f"  - 実行中: {status.get('running')}")
    
    # AgentState確認
    agent_state = system.get_agent_state()
    print(f"🧠 AgentState:")
    print(f"  - セッションID: {agent_state.session_id}")
    print(f"  - 作成時刻: {agent_state.created_at}")
    print(f"  - 対話履歴数: {len(agent_state.conversation_history)}")
    
    # 拡張モード切り替えテスト
    print(f"\n🔧 拡張モード切り替えテスト:")
    original_mode = system.toggle_enhanced_mode()
    print(f"  - 元のモード: {original_mode}")
    
    new_mode = system.toggle_enhanced_mode()
    print(f"  - 切り替え後: {new_mode}")
    
    # 元に戻す
    system.toggle_enhanced_mode(original_mode)
    print(f"  - 復元後: {system.enhanced_companion.use_enhanced_mode}")
    
    print("✅ EnhancedDualLoopSystem 状態テスト完了")


def test_integration_compatibility():
    """既存システムとの統合互換性テスト"""
    print("\n🧪 統合互換性テスト開始")
    
    try:
        # 既存システムのインポートテスト
        from codecrafter.state.agent_state import AgentState
        from codecrafter.memory.conversation_memory import conversation_memory
        from codecrafter.prompts.prompt_compiler import prompt_compiler
        from codecrafter.prompts.context_builder import PromptContextBuilder
        
        print("✅ 既存システムのインポート成功")
        
        # AgentState作成テスト
        test_state = AgentState(session_id="integration-test")
        test_state.add_message("user", "テストメッセージ")
        print(f"✅ AgentState作成・操作成功: {len(test_state.conversation_history)}メッセージ")
        
        # ConversationMemory機能テスト
        memory_status = conversation_memory.get_memory_status(
            test_state.conversation_history,
            test_state.history_summary
        )
        print(f"✅ ConversationMemory機能確認成功: {memory_status}")
        
        # PromptContextBuilder機能テスト
        context_builder = PromptContextBuilder()
        context = context_builder.from_agent_state(
            state=test_state,
            template_name="system_base"
        ).build()
        print(f"✅ PromptContextBuilder機能確認成功: {context.template_name}")
        
        print("✅ 統合互換性テスト完了")
        
    except Exception as e:
        print(f"❌ 統合互換性テストエラー: {e}")
        import traceback
        traceback.print_exc()


def main():
    """メイン関数"""
    print("🦆 Enhanced Dual-Loop System 総合テスト")
    print("=" * 60)
    
    # 1. EnhancedCompanionCore基本機能テスト
    asyncio.run(test_enhanced_companion_core())
    
    # 2. EnhancedDualLoopSystem状態テスト
    test_enhanced_dual_loop_system_status()
    
    # 3. 既存システム統合互換性テスト
    test_integration_compatibility()
    
    print("\n🎉 全テスト完了！")
    print("\n📋 次のステップ:")
    print("  1. python main_companion_enhanced.py で拡張システム起動")
    print("  2. 通常の対話で拡張機能を体験")
    print("  3. `toggle enhanced` で拡張モード切り替え")
    print("  4. `status enhanced` でシステム状態確認")


if __name__ == "__main__":
    main()