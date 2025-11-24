#!/usr/bin/env python3
"""
修正後の会話履歴統合をテストするスクリプト
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'companion'))

from companion.state.agent_state import AgentState
from companion.state.enums import Step, Status
from companion.prompts.prompt_context_service import PromptContextService, PromptPattern
from companion.prompts.llm_call_manager import LLMCallManager
from companion.enhanced_core import EnhancedCompanionCore

def test_conversation_history_integration_fixed():
    """修正後の会話履歴統合のテスト"""
    print("=== 修正後の会話履歴統合テスト開始 ===")
    
    # EnhancedCompanionCoreを作成（グローバルインスタンスが設定される）
    enhanced_core = EnhancedCompanionCore(session_id="test_session_002")
    
    # AgentStateを作成し、会話履歴を追加
    agent_state = enhanced_core.state
    agent_state.goal = "会話履歴統合の修正テスト"
    agent_state.why_now = "システムの動作確認が必要"
    agent_state.constraints = ["安全性を最優先"]
    agent_state.plan_brief = ["テスト実行", "結果確認"]
    agent_state.open_questions = ["会話履歴が正しく統合されているか"]
    agent_state.step = Step.PLANNING
    agent_state.status = Status.PENDING
    
    # 会話履歴を追加
    agent_state.add_message("user", "こんにちは、DuckFlowについて教えてください")
    agent_state.add_message("assistant", "DuckFlowは、AIアシスタントと協力して開発を行うためのシステムです")
    agent_state.add_message("user", "会話履歴は保存されていますか？")
    agent_state.add_message("assistant", "はい、会話履歴は保存されています")
    agent_state.add_message("user", "実装プランを提案してください")
    
    print(f"会話履歴数: {len(agent_state.conversation_history)}")
    print(f"最新メッセージ: {agent_state.conversation_history[-1].content}")
    
    # グローバルインスタンスが正しく設定されているか確認
    global_instance = EnhancedCompanionCore.get_global_instance()
    print(f"グローバルインスタンス取得: {global_instance is not None}")
    print(f"グローバルインスタンスのセッションID: {global_instance.state.session_id if global_instance else 'None'}")
    
    # PromptContextServiceでプロンプトを生成
    service = PromptContextService()
    
    print("\n=== BASE_MAIN_SPECIALIZEDパターンでのテスト ===")
    try:
        prompt = service.compose_with_memory(
            PromptPattern.BASE_MAIN_SPECIALIZED,
            agent_state
        )
        
        print(f"生成されたプロンプト長: {len(prompt)}文字")
        print("\n=== プロンプト内容（最初の1000文字） ===")
        print(prompt[:1000])
        
        # 会話履歴が含まれているかを確認
        if "会話履歴" in prompt and "実装プランを提案してください" in prompt:
            print("\n✅ 会話履歴が正しく統合されています！")
        else:
            print("\n❌ 会話履歴の統合に問題があります")
            
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
    
    # LLMCallManagerでのプロンプト合成テスト
    print("\n=== LLMCallManagerでのプロンプト合成テスト ===")
    try:
        llm_manager = LLMCallManager()
        
        # _compose_promptメソッドを直接テスト
        composed_prompt = llm_manager._compose_prompt(
            mode="generate_content",
            input_text="テスト入力",
            system_prompt="",
            pattern=PromptPattern.BASE_MAIN_SPECIALIZED
        )
        
        print(f"LLMCallManager合成プロンプト長: {len(composed_prompt)}文字")
        print("\n=== LLMCallManager結果（最初の500文字） ===")
        print(composed_prompt[:500])
        
        # 会話履歴が含まれているかを確認
        if "会話履歴" in composed_prompt and "実装プランを提案してください" in composed_prompt:
            print("\n✅ LLMCallManagerでも会話履歴が正しく統合されています！")
        else:
            print("\n❌ LLMCallManagerでの会話履歴統合に問題があります")
            
    except Exception as e:
        print(f"❌ LLMCallManagerテストエラー: {e}")

if __name__ == "__main__":
    test_conversation_history_integration_fixed()
    print("\n=== テスト完了 ===")

