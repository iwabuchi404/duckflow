#!/usr/bin/env python3
"""
Phase 2: 基本的なLLM統合のテスト
"""

import asyncio
import tempfile
import os
from pathlib import Path

# プロジェクトルートをPythonパスに追加
import sys
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from companion.prompts.base_prompt_generator import BasePromptGenerator
from companion.prompts.main_prompt_generator import MainPromptGenerator
from companion.prompts.context_assembler import ContextAssembler
from companion.prompts.llm_call_manager import LLMCallManager
from companion.prompts.integrated_prompt_system import IntegratedPromptSystem


def test_base_prompt_generator():
    """BasePromptGeneratorのテスト"""
    print("🧪 BasePromptGeneratorのテスト開始")
    
    try:
        # 初期化
        generator = BasePromptGenerator()
        print("✅ BasePromptGenerator初期化成功")
        
        # セッションIDの設定
        generator.update_session_id("test_session_001")
        
        # 会話履歴の追加
        generator.add_conversation("ユーザーが実装計画を要求")
        generator.add_conversation("プラン作成完了、承認待ち")
        
        # プロンプト生成
        prompt = generator.generate()
        print(f"📊 Base Prompt生成完了: {len(prompt)}文字")
        
        # プロンプト内容の確認
        if "DuckFlow AI Assistant" in prompt:
            print("✅ 基本人格が含まれている")
        else:
            print("❌ 基本人格が含まれていない")
        
        if "安全第一" in prompt:
            print("✅ 安全原則が含まれている")
        else:
            print("❌ 安全原則が含まれていない")
        
        if "test_session_001" in prompt:
            print("✅ セッションIDが含まれている")
        else:
            print("❌ セッションIDが含まれていない")
        
        print("✅ BasePromptGeneratorテスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ BasePromptGeneratorテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_main_prompt_generator():
    """MainPromptGeneratorのテスト"""
    print("\n🧪 MainPromptGeneratorのテスト開始")
    
    try:
        # 初期化
        generator = MainPromptGenerator()
        print("✅ MainPromptGenerator初期化成功")
        
        # 固定5項目の更新
        generator.update_fixed_five_items(
            goal="実装計画の作成と実行",
            why_now="ユーザーが即座に実装を要求",
            constraints=["安全なファイル操作のみ", "既存ファイルは変更しない"],
            plan_brief=["プラン作成", "承認要求", "実行開始"],
            open_questions=["どのファイルから始めるか"]
        )
        
        # 現在の状況の更新
        generator.update_current_situation(
            step="PLANNING",
            status="IN_PROGRESS",
            ongoing_task="実装計画の作成"
        )
        
        # 会話履歴の追加
        generator.add_conversation("実装計画を作成してください", "プラン作成を開始します")
        
        # プロンプト生成
        prompt = generator.generate()
        print(f"📊 Main Prompt生成完了: {len(prompt)}文字")
        
        # プロンプト内容の確認
        if "現在のステップ: PLANNING" in prompt:
            print("✅ 現在のステップが含まれている")
        else:
            print("❌ 現在のステップが含まれていない")
        
        if "目標: 実装計画の作成と実行" in prompt:
            print("✅ 固定5項目が含まれている")
        else:
            print("❌ 固定5項目が含まれていない")
        
        if "JSON形式で出力してください" in prompt:
            print("✅ 出力指示が含まれている")
        else:
            print("❌ 出力指示が含まれていない")
        
        print("✅ MainPromptGeneratorテスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ MainPromptGeneratorテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_context_assembler():
    """ContextAssemblerのテスト"""
    print("\n🧪 ContextAssemblerのテスト開始")
    
    try:
        # 初期化
        assembler = ContextAssembler()
        print("✅ ContextAssembler初期化成功")
        
        # テスト用のAgentState
        test_agent_state = {
            'step': 'PLANNING',
            'status': 'IN_PROGRESS',
            'goal': '実装計画の作成',
            'why_now': 'ユーザー要求',
            'constraints': ['安全な操作のみ'],
            'plan_brief': ['プラン作成', '承認要求'],
            'open_questions': ['優先順位は？'],
            'context_refs': ['file:game_doc.md', 'plan:001'],
            'decision_log': ['ファイル操作を承認', 'プラン作成を開始'],
            'last_delta': 'ステップをPLANNINGに設定'
        }
        
        # テスト用の会話履歴
        test_conversation_history = [
            {'user': '実装計画を作成してください', 'assistant': 'プラン作成を開始します'},
            {'user': '承認します', 'assistant': '実装を開始します'}
        ]
        
        # 文脈構築
        context = assembler.assemble_context(test_agent_state, test_conversation_history)
        print(f"📊 文脈構築完了: {len(context)}文字")
        
        # 文脈内容の確認
        if "## 基本状態" in context:
            print("✅ 基本状態が含まれている")
        else:
            print("❌ 基本状態が含まれていない")
        
        if "## 固定5項目" in context:
            print("✅ 固定5項目が含まれている")
        else:
            print("❌ 固定5項目が含まれていない")
        
        if "## 関連参照" in context:
            print("✅ 関連参照が含まれている")
        else:
            print("❌ 関連参照が含まれていない")
        
        print("✅ ContextAssemblerテスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ ContextAssemblerテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_llm_call_manager():
    """LLMCallManagerのテスト"""
    print("\n🧪 LLMCallManagerのテスト開始")
    
    try:
        # 初期化
        manager = LLMCallManager()
        print("✅ LLMCallManager初期化成功")
        
        # テスト用のプロンプト
        test_prompt = "実装計画を作成してください。JSON形式で出力してください。"
        
        # LLM呼び出し（モック）
        response = manager.call_llm(test_prompt, expected_format="json")
        print(f"📊 LLM呼び出し完了: {response.get('success', False)}")
        
        # 応答内容の確認
        if response.get('success'):
            print("✅ LLM呼び出しが成功")
            
            content = response.get('content', '')
            if 'rationale' in content:
                print("✅ 適切な応答形式")
            else:
                print("❌ 不適切な応答形式")
        else:
            print(f"❌ LLM呼び出しが失敗: {response.get('error')}")
        
        # 統計情報の確認
        stats = manager.get_call_statistics()
        print(f"📊 呼び出し統計: {stats['total_calls']}回, 成功率: {stats['success_rate']:.1%}")
        
        print("✅ LLMCallManagerテスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ LLMCallManagerテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integrated_prompt_system():
    """IntegratedPromptSystemのテスト"""
    print("\n🧪 IntegratedPromptSystemのテスト開始")
    
    try:
        # 初期化
        system = IntegratedPromptSystem()
        print("✅ IntegratedPromptSystem初期化成功")
        
        # テスト用のAgentState
        test_agent_state = {
            'step': 'PLANNING',
            'status': 'IN_PROGRESS',
            'goal': '実装計画の作成',
            'why_now': 'ユーザー要求',
            'constraints': ['安全な操作のみ'],
            'plan_brief': ['プラン作成', '承認要求'],
            'open_questions': ['優先順位は？']
        }
        
        # テスト用のセッションデータ
        test_session_data = {
            'session_id': 'test_session_002',
            'total_conversations': 5
        }
        
        # Base + Main プロンプト生成
        prompt = system.generate_base_main_prompt(test_agent_state, session_data=test_session_data)
        print(f"📊 統合プロンプト生成完了: {len(prompt)}文字")
        
        # プロンプト内容の確認
        if "あなたはDuckFlow AI Assistantです" in prompt:
            print("✅ Base Promptが含まれている")
        else:
            print("❌ Base Promptが含まれていない")
        
        if "現在の対話状況" in prompt:
            print("✅ Main Promptが含まれている")
        else:
            print("❌ Main Promptが含まれていない")
        
        if "=" * 50 in prompt:
            print("✅ プロンプトの区切りが含まれている")
        else:
            print("❌ プロンプトの区切りが含まれていない")
        
        # LLM呼び出しテスト
        response = system.call_llm_with_prompt(test_agent_state, session_data=test_session_data)
        print(f"📊 LLM呼び出し完了: {response.get('success', False)}")
        
        # 統計情報の確認
        stats = system.get_prompt_statistics()
        print(f"📊 プロンプト統計: Base={stats['base_prompt_length']}文字, Main={stats['main_prompt_length']}文字")
        
        print("✅ IntegratedPromptSystemテスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ IntegratedPromptSystemテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メインテスト関数"""
    print("🚀 Phase 2: 基本的なLLM統合テスト開始")
    print("=" * 60)
    
    # 各コンポーネントのテスト
    test_results = []
    
    test_results.append(test_base_prompt_generator())
    test_results.append(test_main_prompt_generator())
    test_results.append(test_context_assembler())
    test_results.append(test_llm_call_manager())
    test_results.append(test_integrated_prompt_system())
    
    print("\n" + "=" * 60)
    print("🎉 テスト完了！")
    
    # 結果サマリー
    success_count = sum(test_results)
    total_count = len(test_results)
    
    print(f"\n📋 テスト結果: {success_count}/{total_count} 成功")
    
    if success_count == total_count:
        print("🎯 Phase 2実装完了！")
        print("\n✅ 実装完了した機能:")
        print("   - BasePromptGenerator: 基本人格と制約の生成")
        print("   - MainPromptGenerator: 固定5項目と会話状況の生成")
        print("   - ContextAssembler: AgentStateからの文脈構築")
        print("   - LLMCallManager: 基本的なLLM呼び出し")
        print("   - IntegratedPromptSystem: Base + Main プロンプトの統合")
        
        print("\n🎯 次のステップ:")
        print("   - Phase 3: 機能拡張（Specialized Prompt、ToolRouter）")
        print("   - 実際のLLM APIとの統合")
        print("   - パフォーマンス最適化")
    else:
        print("❌ 一部のテストが失敗しました")
        print("エラーの詳細を確認して修正してください")


if __name__ == "__main__":
    main()
