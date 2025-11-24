#!/usr/bin/env python3
"""
会話履歴統合の修正をテストするスクリプト
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'companion'))

from companion.state.agent_state import AgentState
from companion.state.enums import Step, Status
from companion.prompts.prompt_context_service import PromptContextService, PromptPattern
from companion.prompts.prompt_compiler import PromptCompiler

def test_conversation_history_integration():
    """会話履歴統合のテスト"""
    print("=== 会話履歴統合テスト開始 ===")
    
    # AgentStateを作成し、会話履歴を追加
    agent_state = AgentState(
        session_id="test_session_001",
        goal="会話履歴統合のテスト",
        why_now="システムの動作確認が必要",
        constraints=["安全性を最優先"],
        plan_brief=["テスト実行", "結果確認"],
        open_questions=["会話履歴が正しく統合されているか"],
        step=Step.PLANNING,
        status=Status.PENDING
    )
    
    # 会話履歴を追加
    agent_state.add_message("user", "こんにちは、DuckFlowについて教えてください")
    agent_state.add_message("assistant", "DuckFlowは、AIアシスタントと協力して開発を行うためのシステムです")
    agent_state.add_message("user", "会話履歴は保存されていますか？")
    agent_state.add_message("assistant", "はい、会話履歴は保存されています")
    agent_state.add_message("user", "実装プランを提案してください")
    
    print(f"会話履歴数: {len(agent_state.conversation_history)}")
    print(f"最新メッセージ: {agent_state.conversation_history[-1].content}")
    
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
    
    print("\n=== PromptCompiler直接テスト ===")
    try:
        compiler = PromptCompiler()
        
        # 各層のコンテキストを構築
        base_context = "あなたはDuckFlowのアシスタントです。"
        main_context = "現在のコンテキスト情報"
        specialized_context = "専門知識とガイドライン"
        
        result = compiler.compile_with_memory(
            "base_main_specialized",
            base_context,
            main_context,
            specialized_context,
            agent_state
        )
        
        print(f"PromptCompiler結果長: {len(result)}文字")
        print("\n=== PromptCompiler結果（最初の500文字） ===")
        print(result[:500])
        
    except Exception as e:
        print(f"❌ PromptCompilerエラー: {e}")

def test_memory_extraction():
    """記憶データ抽出のテスト"""
    print("\n=== 記憶データ抽出テスト ===")
    
    try:
        from companion.prompts.memory_context_extractor import MemoryContextExtractor
        
        extractor = MemoryContextExtractor()
        agent_state = AgentState(session_id="test_memory")
        agent_state.add_message("user", "テストメッセージ")
        
        memory_data = extractor.extract_for_pattern("base_main_specialized", agent_state)
        
        print("抽出された記憶データ:")
        for category, data in memory_data.items():
            print(f"  {category}: {len(str(data))}文字")
            
    except Exception as e:
        print(f"❌ 記憶データ抽出エラー: {e}")

if __name__ == "__main__":
    test_conversation_history_integration()
    test_memory_extraction()
    print("\n=== テスト完了 ===")

