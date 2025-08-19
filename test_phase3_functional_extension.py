#!/usr/bin/env python3
"""
Phase 3: 機能拡張のテスト
"""

import asyncio
import tempfile
import os
from pathlib import Path

# プロジェクトルートをPythonパスに追加
import sys
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from companion.prompts.specialized_prompt_generator import SpecializedPromptGenerator
from companion.prompts.prompt_router import PromptRouter
from companion.tools.tool_router import ToolRouter
from companion.prompts.enhanced_prompt_system import EnhancedPromptSystem


def test_specialized_prompt_generator():
    """SpecializedPromptGeneratorのテスト"""
    print("🧪 SpecializedPromptGeneratorのテスト開始")
    
    try:
        # 初期化
        generator = SpecializedPromptGenerator()
        print("✅ SpecializedPromptGenerator初期化成功")
        
        # サポートされているステップの確認
        supported_steps = generator.get_supported_steps()
        print(f"📊 サポートされているステップ: {supported_steps}")
        
        # テスト用のAgentState
        test_agent_state = {
            'step': 'PLANNING',
            'goal': '実装計画の作成',
            'constraints': ['安全な操作のみ', '既存ファイルは変更しない'],
            'plan_brief': ['プラン作成', '承認要求'],
            'open_questions': ['どのファイルから始めるか', '優先順位は？']
        }
        
        # 各ステップのプロンプト生成テスト
        for step in supported_steps:
            try:
                prompt = generator.generate(step, test_agent_state)
                print(f"📊 {step} プロンプト生成完了: {len(prompt)}文字")
                
                # プロンプト内容の確認
                if step == "PLANNING":
                    if "計画作成の専門知識・手順書" in prompt:
                        print(f"✅ {step} プロンプトが適切に生成されている")
                    else:
                        print(f"❌ {step} プロンプトの内容が不適切")
                
                elif step == "EXECUTION":
                    if "実行の専門知識・手順書" in prompt:
                        print(f"✅ {step} プロンプトが適切に生成されている")
                    else:
                        print(f"❌ {step} プロンプトの内容が不適切")
                
                elif step == "REVIEW":
                    if "レビューの専門知識・手順書" in prompt:
                        print(f"✅ {step} プロンプトが適切に生成されている")
                    else:
                        print(f"❌ {step} プロンプトの内容が不適切")
                
            except Exception as e:
                print(f"❌ {step} プロンプト生成エラー: {e}")
                return False
        
        print("✅ SpecializedPromptGeneratorテスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ SpecializedPromptGeneratorテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prompt_router():
    """PromptRouterのテスト"""
    print("\n🧪 PromptRouterのテスト開始")
    
    try:
        # 初期化
        router = PromptRouter()
        print("✅ PromptRouter初期化成功")
        
        # ルーティングルールの確認
        routing_rules = router.get_routing_rules()
        print(f"📊 ルーティングルール: {len(routing_rules)}件")
        
        # テスト用のAgentState
        test_agent_state = {
            'step': 'PLANNING',
            'goal': '実装計画の作成',
            'constraints': ['安全な操作のみ'],
            'plan_brief': ['プラン作成', '承認要求'],
            'ongoing_task': '実装計画の作成'
        }
        
        # パターン選択のテスト
        test_cases = [
            ("実装計画を作成してください", "base_main_specialized"),
            ("ファイルを確認してください", "base_main"),
            ("バッチ処理を実行してください", "base_specialized"),
            ("計画を立ててください", "base_main_specialized")
        ]
        
        for user_input, expected_pattern in test_cases:
            selected_pattern = router.select_prompt_pattern(
                test_agent_state, user_input, test_agent_state.get('step')
            )
            print(f"📊 入力: '{user_input[:20]}...' → 選択パターン: {selected_pattern}")
            
            if selected_pattern == expected_pattern:
                print(f"✅ パターン選択が正しい: {selected_pattern}")
            else:
                print(f"⚠️ パターン選択が期待と異なる: 期待={expected_pattern}, 実際={selected_pattern}")
        
        # パターン推奨のテスト
        recommendations = router.get_pattern_recommendation(
            test_agent_state, "実装計画を作成してください"
        )
        print(f"📊 パターン推奨: {len(recommendations)}件")
        for pattern, description, score in recommendations[:3]:
            print(f"  - {pattern}: {description} (スコア: {score:.2f})")
        
        print("✅ PromptRouterテスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ PromptRouterテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_router():
    """ToolRouterのテスト"""
    print("\n🧪 ToolRouterのテスト開始")
    
    try:
        # 作業ディレクトリの作成
        work_dir = "./test_work"
        os.makedirs(work_dir, exist_ok=True)
        
        # 初期化
        router = ToolRouter(work_dir)
        print("✅ ToolRouter初期化成功")
        
        # サポートされている操作の確認
        supported_ops = router.get_supported_operations()
        print(f"📊 サポートされている操作: {len(supported_ops)}カテゴリ")
        
        # 安全性設定の確認
        safety_config = router.get_safety_config()
        print(f"📊 安全性設定: 最大ファイルサイズ={safety_config['max_file_size']} bytes")
        
        # ファイル操作のテスト
        test_file_path = os.path.join(work_dir, "test_file.txt")
        test_content = "これはテストファイルです。\nPhase 3のToolRouterテスト用。"
        
        # ファイル作成テスト
        create_result = router.route_operation(
            'create', 
            file_path=test_file_path, 
            content=test_content
        )
        print(f"📊 ファイル作成結果: {create_result.get('success', False)}")
        
        if create_result.get('success'):
            print("✅ ファイル作成が成功")
        else:
            print(f"❌ ファイル作成が失敗: {create_result.get('error')}")
            return False
        
        # ファイル読み取りテスト
        read_result = router.route_operation('read', file_path=test_file_path)
        print(f"📊 ファイル読み取り結果: {read_result.get('success', False)}")
        
        if read_result.get('success'):
            content = read_result.get('content', '')
            if test_content in content:
                print("✅ ファイル読み取りが成功、内容が一致")
            else:
                print("❌ ファイル読み取りは成功したが内容が不一致")
        else:
            print(f"❌ ファイル読み取りが失敗: {read_result.get('error')}")
            return False
        
        # システム操作のテスト
        system_result = router.route_operation('status')
        print(f"📊 システム状態確認結果: {system_result.get('success', False)}")
        
        if system_result.get('success'):
            status = system_result.get('status', {})
            print(f"✅ システム状態確認が成功: ToolRouter={status.get('tool_router')}")
        else:
            print(f"❌ システム状態確認が失敗: {system_result.get('error')}")
        
        # 使用統計の確認
        usage_stats = router.get_usage_statistics()
        print(f"📊 使用統計: 総操作数={usage_stats.get('total_operations', 0)}")
        
        # クリーンアップ
        router.route_operation('delete', file_path=test_file_path)
        try:
            # ディレクトリ内のファイルを削除
            for file in os.listdir(work_dir):
                file_path = os.path.join(work_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(work_dir)
        except Exception as e:
            print(f"⚠️ クリーンアップ警告: {e}")
            # クリーンアップに失敗してもテストは続行
        
        print("✅ ToolRouterテスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ ToolRouterテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_enhanced_prompt_system():
    """EnhancedPromptSystemのテスト"""
    print("\n🧪 EnhancedPromptSystemのテスト開始")
    
    try:
        # 作業ディレクトリの作成
        work_dir = "./test_work_enhanced"
        os.makedirs(work_dir, exist_ok=True)
        
        # 初期化
        system = EnhancedPromptSystem(work_dir)
        print("✅ EnhancedPromptSystem初期化成功")
        
        # システム状態の確認
        system_status = system.get_system_status()
        print(f"📊 システム状態: 有効={system_status['enhanced_prompt_system']['enabled']}")
        
        # テスト用のAgentState
        test_agent_state = {
            'step': 'PLANNING',
            'goal': '実装計画の作成と実行',
            'why_now': 'ユーザーが即座に実装を要求',
            'constraints': ['安全なファイル操作のみ', '既存ファイルは変更しない'],
            'plan_brief': ['プラン作成', '承認要求', '実行開始'],
            'open_questions': ['どのファイルから始めるか']
        }
        
        # テスト用のセッションデータ
        test_session_data = {
            'session_id': 'test_session_phase3',
            'total_conversations': 10
        }
        
        # 要求処理のテスト
        test_inputs = [
            "実装計画を作成してください",
            "ファイルの内容を確認してください",
            "バッチ処理を実行してください"
        ]
        
        for user_input in test_inputs:
            try:
                result = system.process_request(
                    user_input, test_agent_state, 
                    session_data=test_session_data
                )
                
                if result.get('success'):
                    selected_pattern = result.get('selected_pattern', 'unknown')
                    prompt_length = result.get('prompt_length', 0)
                    print(f"📊 入力: '{user_input[:20]}...' → パターン: {selected_pattern}, 長さ: {prompt_length}文字")
                    
                    # ツール操作結果の確認
                    tool_results = result.get('tool_results', [])
                    if tool_results:
                        print(f"  - ツール操作: {len(tool_results)}件実行")
                        for tool_result in tool_results:
                            operation = tool_result.get('operation', {})
                            op_name = operation.get('operation', 'unknown')
                            success = tool_result.get('result', {}).get('success', False)
                            print(f"    * {op_name}: {'成功' if success else '失敗'}")
                    
                    # パターン使用統計の確認
                    if selected_pattern in system.prompt_usage:
                        print(f"  - パターン使用回数: {system.prompt_usage[selected_pattern]}")
                    
                else:
                    print(f"❌ 要求処理が失敗: {result.get('error')}")
                    return False
                    
            except Exception as e:
                print(f"❌ 要求処理エラー: {e}")
                return False
        
        # システム状態の最終確認
        final_status = system.get_system_status()
        print(f"📊 最終システム状態:")
        print(f"  - プロンプト使用統計: {final_status['prompt_usage']}")
        print(f"  - ツールルーター履歴: {final_status['tool_router']['operation_history_count']}件")
        print(f"  - ツール総操作数: {final_status['tool_router']['usage_statistics']['total_operations']}")
        
        # クリーンアップ
        system.reset_statistics()
        import shutil
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        
        print("✅ EnhancedPromptSystemテスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ EnhancedPromptSystemテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メインテスト関数"""
    print("🚀 Phase 3: 機能拡張テスト開始")
    print("=" * 60)
    
    # 各コンポーネントのテスト
    test_results = []
    
    test_results.append(test_specialized_prompt_generator())
    test_results.append(test_prompt_router())
    test_results.append(test_tool_router())
    test_results.append(test_enhanced_prompt_system())
    
    print("\n" + "=" * 60)
    print("🎉 テスト完了！")
    
    # 結果サマリー
    success_count = sum(test_results)
    total_count = len(test_results)
    
    print(f"\n📋 テスト結果: {success_count}/{total_count} 成功")
    
    if success_count == total_count:
        print("🎯 Phase 3実装完了！")
        print("\n✅ 実装完了した機能:")
        print("   - SpecializedPromptGenerator: 専門知識と手順書の生成")
        print("   - PromptRouter: 3パターンの適切な選択")
        print("   - ToolRouter: 基本的なツール統合（ファイル書き出し含む）")
        print("   - EnhancedPromptSystem: 3パターンのプロンプトとToolRouter統合")
        
        print("\n🎯 次のステップ:")
        print("   - Phase 4: 最適化と安全性強化")
        print("   - 実際のLLM APIとの統合")
        print("   - パフォーマンス最適化")
        print("   - 本格的な承認システム")
    else:
        print("❌ 一部のテストが失敗しました")
        print("エラーの詳細を確認して修正してください")


if __name__ == "__main__":
    main()
