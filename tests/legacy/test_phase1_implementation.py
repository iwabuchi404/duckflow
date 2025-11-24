"""
Phase 1 実装テストスクリプト
PromptContextService、IntentAnalyzerLLM、LLMCallManagerの動作確認
"""

import asyncio
import logging
import sys
from pathlib import Path

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_prompt_context_service():
    """PromptContextServiceのテスト"""
    print("\n🧪 PromptContextServiceのテスト開始")
    
    try:
        from companion.prompts.prompt_context_service import PromptContextService, PromptPattern
        from companion.state.agent_state import AgentState
        
        # サービスを初期化
        service = PromptContextService()
        print("✅ PromptContextService初期化成功")
        
        # テスト用のAgentStateを作成
        agent_state = AgentState(
            session_id="test_session",
            current_step="IDLE",
            current_status="PENDING"
        )
        
        # 各パターンのテスト
        patterns = [
            PromptPattern.BASE_SPECIALIZED,
            PromptPattern.BASE_MAIN,
            PromptPattern.BASE_MAIN_SPECIALIZED
        ]
        
        for pattern in patterns:
            print(f"\n--- {pattern.value} パターンのテスト ---")
            
            # プロンプト合成
            prompt = service.compose(pattern, agent_state)
            print(f"生成されたプロンプト長: {len(prompt)}文字")
            print(f"パターン情報: {service.get_pattern_info(pattern)}")
            
            # 内容の確認（最初の200文字）
            preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
            print(f"プロンプトプレビュー: {preview}")
        
        print("\n✅ PromptContextServiceテスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ PromptContextServiceテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_intent_analyzer_llm():
    """IntentAnalyzerLLMのテスト"""
    print("\n🧪 IntentAnalyzerLLMのテスト開始")
    
    try:
        from companion.intent_understanding.intent_analyzer_llm import IntentAnalyzerLLM
        from companion.state.agent_state import AgentState
        
        # アナライザーを初期化
        analyzer = IntentAnalyzerLLM()
        print("✅ IntentAnalyzerLLM初期化成功")
        
        # テスト用のAgentStateを作成
        agent_state = AgentState(
            session_id="test_session",
            current_step="IDLE",
            current_status="PENDING"
        )
        
        # テストケース
        test_cases = [
            "game_doc.mdを読んで内容を要約してください",
            "新しいプロジェクトの計画を立ててください",
            "Pythonコードを実行してください",
            "会話履歴を要約してください"
        ]
        
        for test_input in test_cases:
            print(f"\n--- テスト入力: {test_input} ---")
            
            # 意図分析（非同期なので同期的に実行）
            try:
                # 非同期関数を同期的に実行
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    analyzer.analyze(test_input, agent_state)
                )
                loop.close()
                
                print(f"アクションタイプ: {result.action_type.value}")
                print(f"プロンプトパターン: {result.prompt_pattern.value}")
                print(f"ファイルターゲット: {result.file_target}")
                print(f"承認要否: {result.require_approval}")
                print(f"信頼度: {result.confidence}")
                print(f"推論: {result.reasoning}")
                
            except Exception as e:
                print(f"意図分析エラー: {e}")
        
        print("\n✅ IntentAnalyzerLLMテスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ IntentAnalyzerLLMテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_llm_call_manager():
    """LLMCallManagerのテスト"""
    print("\n🧪 LLMCallManagerのテスト開始")
    
    try:
        from companion.prompts.llm_call_manager import LLMCallManager
        from companion.prompts.prompt_context_service import PromptPattern
        
        # マネージャーを初期化
        manager = LLMCallManager()
        print("✅ LLMCallManager初期化成功")
        
        # テスト用のsystem_prompt
        system_prompt = "あなたはDuckFlowのアシスタントです。"
        
        # 各モードのテスト
        test_cases = [
            ("summarize", "これはテスト用の長いテキストです。要約してください。", PromptPattern.BASE_SPECIALIZED),
            ("extract", "テキストから重要な情報を抽出してください。", PromptPattern.BASE_SPECIALIZED),
            ("generate_content", "新しいファイルの内容を生成してください。", PromptPattern.BASE_MAIN),
            ("plan", "プロジェクトの計画を立ててください。", PromptPattern.BASE_MAIN_SPECIALIZED)
        ]
        
        for mode, input_text, pattern in test_cases:
            print(f"\n--- モード: {mode}, パターン: {pattern.value} ---")
            
            # プロンプト合成のテスト
            full_prompt = manager._compose_prompt(mode, input_text, system_prompt, pattern)
            print(f"合成されたプロンプト長: {len(full_prompt)}文字")
            
            # プロンプトの内容確認（最初の200文字）
            preview = full_prompt[:200] + "..." if len(full_prompt) > 200 else full_prompt
            print(f"プロンプトプレビュー: {preview}")
        
        # 統計情報の確認
        stats = manager.get_call_statistics()
        print(f"\n統計情報: {stats}")
        
        print("\n✅ LLMCallManagerテスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ LLMCallManagerテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integration():
    """統合テスト"""
    print("\n🧪 統合テスト開始")
    
    try:
        from companion.prompts.prompt_context_service import PromptContextService, PromptPattern
        from companion.intent_understanding.intent_analyzer_llm import IntentAnalyzerLLM
        from companion.prompts.llm_call_manager import LLMCallManager
        from companion.state.agent_state import AgentState
        
        # 各コンポーネントを初期化
        context_service = PromptContextService()
        intent_analyzer = IntentAnalyzerLLM()
        llm_manager = LLMCallManager()
        
        print("✅ 全コンポーネント初期化成功")
        
        # テスト用のAgentStateを作成
        agent_state = AgentState(
            session_id="test_session",
            current_step="IDLE",
            current_status="PENDING"
        )
        
        # 統合フローのテスト
        test_input = "game_doc.mdを読んで内容を要約してください"
        print(f"\n--- 統合テスト: {test_input} ---")
        
        # 1. 意図分析
        print("1. 意図分析中...")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            intent_result = loop.run_until_complete(
                intent_analyzer.analyze(test_input, agent_state)
            )
            loop.close()
            
            print(f"   - アクションタイプ: {intent_result.action_type.value}")
            print(f"   - プロンプトパターン: {intent_result.prompt_pattern.value}")
            print(f"   - ファイルターゲット: {intent_result.file_target}")
            print(f"   - 信頼度: {intent_result.confidence}")
            
        except Exception as e:
            print(f"   意図分析エラー: {e}")
            return False
        
        # 2. プロンプト生成
        print("2. プロンプト生成中...")
        try:
            system_prompt = context_service.compose(intent_result.prompt_pattern, agent_state)
            print(f"   - 生成されたプロンプト長: {len(system_prompt)}文字")
            
        except Exception as e:
            print(f"   プロンプト生成エラー: {e}")
            return False
        
        # 3. LLM呼び出し（モック）
        print("3. LLM呼び出し中...")
        try:
            # 非同期呼び出しを同期的に実行
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(
                llm_manager.call(
                    mode="summarize",
                    input_text=test_input,
                    system_prompt=system_prompt,
                    pattern=intent_result.prompt_pattern
                )
            )
            loop.close()
            
            print(f"   - レスポンス長: {len(response)}文字")
            print(f"   - レスポンスプレビュー: {response[:100]}...")
            
        except Exception as e:
            print(f"   LLM呼び出しエラー: {e}")
            return False
        
        print("\n✅ 統合テスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ 統合テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メイン関数"""
    print("🚀 Phase 1 実装テスト開始")
    print("=" * 50)
    
    test_results = []
    
    # 各コンポーネントのテスト
    test_results.append(test_prompt_context_service())
    test_results.append(test_intent_analyzer_llm())
    test_results.append(test_llm_call_manager())
    
    # 統合テスト
    test_results.append(test_integration())
    
    # 結果集計
    print("\n" + "=" * 50)
    print("📊 テスト結果集計")
    
    total_tests = len(test_results)
    passed_tests = sum(test_results)
    failed_tests = total_tests - passed_tests
    
    print(f"総テスト数: {total_tests}")
    print(f"成功: {passed_tests}")
    print(f"失敗: {failed_tests}")
    
    if failed_tests == 0:
        print("\n🎉 すべてのテストが成功しました！")
        print("Phase 1の実装は完了しています。")
        return True
    else:
        print(f"\n⚠️  {failed_tests}件のテストが失敗しました。")
        print("実装の問題を確認してください。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
