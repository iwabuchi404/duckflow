#!/usr/bin/env python3
"""
PromptCompiler記憶注入機能統合テスト

3層構造（Base/Main/Specialized）と記憶注入機能の動作確認
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_memory_context_extractor():
    """MemoryContextExtractorのテスト"""
    print("\n🧪 MemoryContextExtractorのテスト開始")
    
    try:
        from companion.prompts.memory_context_extractor import MemoryContextExtractor
        from companion.state.agent_state import AgentState
        
        # 抽出器を初期化
        extractor = MemoryContextExtractor()
        print("✅ MemoryContextExtractor初期化成功")
        
        # テスト用のAgentStateを作成
        agent_state = AgentState(
            session_id="test_session_001",
            current_step="IDLE",
            current_status="PENDING"
        )
        
        # 短期記憶にテストデータを追加
        agent_state.short_term_memory = {
            'file_operations': [
                {
                    'operation': 'read',
                    'file_path': 'test.txt',
                    'timestamp': '2024-01-01T10:00:00'
                },
                {
                    'operation': 'write',
                    'file_path': 'output.txt',
                    'timestamp': '2024-01-01T10:30:00'
                }
            ],
            'operations': [
                {
                    'type': 'file_analysis',
                    'description': 'テキストファイルの分析',
                    'timestamp': '2024-01-01T10:15:00'
                }
            ],
            'file_cache': {
                'test.txt': 'これはテストファイルです。',
                'test.txt_timestamp': '2024-01-01T10:00:00'
            },
            'summaries': [
                {
                    'type': 'file_summary',
                    'timestamp': '2024-01-01T10:20:00'
                }
            ],
            'plans': [
                {
                    'type': 'file_processing',
                    'status': 'completed',
                    'timestamp': '2024-01-01T10:25:00'
                }
            ]
        }
        
        # 会話履歴を追加
        agent_state.conversation_history = [
            {
                'role': 'user',
                'content': 'ファイルを分析してください',
                'timestamp': '2024-01-01T10:00:00'
            },
            {
                'role': 'assistant',
                'content': 'ファイルの分析を開始します',
                'timestamp': '2024-01-01T10:01:00'
            }
        ]
        
        # 各パターンでの記憶データ抽出をテスト
        patterns = ["base_specialized", "base_main", "base_main_specialized"]
        
        for pattern in patterns:
            print(f"\n--- {pattern} パターンのテスト ---")
            
            # 記憶データを抽出
            memory_data = extractor.extract_for_pattern(pattern, agent_state, "test.txt")
            
            print(f"抽出された記憶データ:")
            for layer, data in memory_data.items():
                print(f"  {layer}: {type(data).__name__}")
                if isinstance(data, dict) and 'error' not in data:
                    print(f"    データ件数: {len(data)}")
        
        # 統計情報の取得
        stats = extractor.get_memory_statistics(agent_state)
        print(f"\n記憶統計情報: {stats}")
        
        print("\n✅ MemoryContextExtractorテスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ MemoryContextExtractorテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prompt_compiler_memory_integration():
    """PromptCompilerの記憶注入機能のテスト"""
    print("\n🧪 PromptCompiler記憶注入機能のテスト開始")
    
    try:
        from companion.prompts.prompt_compiler import PromptCompiler
        from companion.state.agent_state import AgentState
        
        # PromptCompilerを初期化
        compiler = PromptCompiler()
        print("✅ PromptCompiler初期化成功")
        
        # 利用可能なパターンを確認
        patterns = compiler.list_patterns()
        print(f"利用可能なパターン: {patterns}")
        
        # テスト用のAgentStateを作成
        agent_state = AgentState(
            session_id="test_session_002",
            current_step="EXECUTION",
            current_status="RUNNING"
        )
        
        # 短期記憶にテストデータを追加
        agent_state.short_term_memory = {
            'file_operations': [
                {
                    'operation': 'read',
                    'file_path': 'main.py',
                    'timestamp': '2024-01-01T11:00:00'
                }
            ],
            'operations': [
                {
                    'type': 'code_execution',
                    'description': 'Pythonスクリプトの実行',
                    'timestamp': '2024-01-01T11:15:00'
                }
            ]
        }
        
        # 各パターンでの記憶統合プロンプトコンパイルをテスト
        test_contexts = {
            "base": "あなたはDuckFlowのAIアシスタントです。",
            "main": "現在のタスク: コードの実行と分析",
            "specialized": "実行環境: Python 3.9+"
        }
        
        for pattern in patterns:
            print(f"\n--- {pattern} パターンのテスト ---")
            
            # 記憶統合プロンプトをコンパイル
            result = compiler.compile_with_memory(
                pattern=pattern,
                base_context=test_contexts["base"],
                main_context=test_contexts["main"],
                specialized_context=test_contexts["specialized"],
                agent_state=agent_state,
                target_file="main.py"
            )
            
            print(f"生成されたプロンプト長: {len(result)}文字")
            print(f"パターン情報: {compiler.get_pattern_info(pattern)}")
            
            # 内容の確認（最初の300文字）
            preview = result[:300] + "..." if len(result) > 300 else result
            print(f"プロンプトプレビュー: {preview}")
        
        # 記憶統計情報の取得
        stats = compiler.get_memory_statistics(agent_state)
        print(f"\n記憶統計情報: {stats}")
        
        print("\n✅ PromptCompiler記憶注入機能テスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ PromptCompiler記憶注入機能テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prompt_context_service_integration():
    """PromptContextServiceとPromptCompilerの統合テスト"""
    print("\n🧪 PromptContextService統合テスト開始")
    
    try:
        from companion.prompts.prompt_context_service import PromptContextService, PromptPattern
        from companion.state.agent_state import AgentState
        
        # サービスを初期化
        service = PromptContextService()
        print("✅ PromptContextService初期化成功")
        
        # 利用可能なパターンを確認
        patterns = service.get_available_patterns()
        print(f"利用可能なパターン: {len(patterns)}件")
        for pattern in patterns:
            print(f"  - {pattern['pattern']}: {pattern['description']}")
        
        # テスト用のAgentStateを作成
        agent_state = AgentState(
            session_id="test_session_003",
            current_step="PLANNING",
            current_status="ACTIVE"
        )
        
        # 短期記憶にテストデータを追加
        agent_state.short_term_memory = {
            'file_operations': [
                {
                    'operation': 'create',
                    'file_path': 'plan.md',
                    'timestamp': '2024-01-01T12:00:00'
                }
            ],
            'operations': [
                {
                    'type': 'planning',
                    'description': 'プロジェクト計画の作成',
                    'timestamp': '2024-01-01T12:15:00'
                }
            ]
        }
        
        # 各パターンでの統合プロンプト合成をテスト
        test_patterns = [
            PromptPattern.BASE_SPECIALIZED,
            PromptPattern.BASE_MAIN,
            PromptPattern.BASE_MAIN_SPECIALIZED
        ]
        
        for pattern in test_patterns:
            print(f"\n--- {pattern.value} パターンのテスト ---")
            
            # 従来方式での合成
            traditional_result = service.compose(pattern, agent_state)
            print(f"従来方式: {len(traditional_result)}文字")
            
            # 記憶注入版での合成
            memory_result = service.compose_with_memory(pattern, agent_state, "plan.md")
            print(f"記憶注入版: {len(memory_result)}文字")
            
            # 拡張版での合成
            enhanced_result = service.compose_enhanced(pattern, agent_state, "plan.md", True)
            print(f"拡張版: {len(enhanced_result)}文字")
            
            # パターン情報の取得
            pattern_info = service.get_pattern_info(pattern)
            print(f"パターン情報: {pattern_info}")
        
        # パターンの最適化テスト
        print(f"\n--- パターン最適化テスト ---")
        optimized = service.validate_and_enhance_pattern("base_specialized", agent_state)
        print(f"最適化結果: base_specialized -> {optimized}")
        
        # パターン比較テスト
        comparison = service.compare_patterns("base_main", "base_main_specialized")
        print(f"パターン比較: {comparison}")
        
        # 記憶統計情報の取得
        stats = service.get_memory_statistics(agent_state)
        print(f"\n記憶統計情報: {stats}")
        
        print("\n✅ PromptContextService統合テスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ PromptContextService統合テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_memory_injection_workflow():
    """記憶注入ワークフローの統合テスト"""
    print("\n🧪 記憶注入ワークフローの統合テスト開始")
    
    try:
        from companion.prompts.prompt_compiler import compile_with_memory
        from companion.prompts.prompt_context_service import PromptContextService, PromptPattern
        from companion.state.agent_state import AgentState
        
        # サービスを初期化
        service = PromptContextService()
        
        # テスト用のAgentStateを作成（段階的に状態を変化）
        agent_state = AgentState(
            session_id="test_session_004",
            current_step="IDLE",
            current_status="PENDING"
        )
        
        # 段階1: 初期状態
        print("\n--- 段階1: 初期状態 ---")
        result1 = service.compose_with_memory(
            PromptPattern.BASE_MAIN, agent_state
        )
        print(f"初期状態プロンプト: {len(result1)}文字")
        
        # 段階2: ファイル操作後
        print("\n--- 段階2: ファイル操作後 ---")
        agent_state.short_term_memory['file_operations'] = [
            {
                'operation': 'read',
                'file_path': 'config.yaml',
                'timestamp': datetime.now().isoformat()
            }
        ]
        agent_state.current_step = "EXECUTION"
        agent_state.current_status = "RUNNING"
        
        result2 = service.compose_with_memory(
            PromptPattern.BASE_MAIN_SPECIALIZED, agent_state, "config.yaml"
        )
        print(f"ファイル操作後プロンプト: {len(result2)}文字")
        
        # 段階3: 会話履歴蓄積後
        print("\n--- 段階3: 会話履歴蓄積後 ---")
        for i in range(10):
            agent_state.conversation_history.append({
                'role': 'user' if i % 2 == 0 else 'assistant',
                'content': f'テストメッセージ {i+1}',
                'timestamp': datetime.now().isoformat()
            })
        
        result3 = service.compose_with_memory(
            PromptPattern.BASE_MAIN_SPECIALIZED, agent_state
        )
        print(f"会話履歴蓄積後プロンプト: {len(result3)}文字")
        
        # 直接PromptCompilerを使用したテスト
        print("\n--- 直接PromptCompiler使用テスト ---")
        direct_result = compile_with_memory(
            pattern="base_main_specialized",
            base_context="システム設定",
            main_context="会話履歴",
            specialized_context="専門知識",
            agent_state=agent_state,
            target_file="config.yaml"
        )
        print(f"直接コンパイル結果: {len(direct_result)}文字")
        
        print("\n✅ 記憶注入ワークフローテスト成功！")
        return True
        
    except Exception as e:
        print(f"❌ 記憶注入ワークフローテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """メイン関数"""
    print("🚀 PromptCompiler記憶注入機能統合テスト開始")
    
    # テスト実行
    tests = [
        test_memory_context_extractor,
        test_prompt_compiler_memory_integration,
        test_prompt_context_service_integration,
        test_memory_injection_workflow
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ テスト実行エラー: {e}")
            results.append(False)
    
    # 結果サマリー
    print(f"\n📊 テスト結果サマリー")
    print(f"実行テスト数: {len(tests)}")
    print(f"成功: {sum(results)}")
    print(f"失敗: {len(results) - sum(results)}")
    
    if all(results):
        print("\n🎉 全テスト成功！PromptCompiler記憶注入機能が正常に動作しています。")
        return True
    else:
        print("\n⚠️ 一部のテストが失敗しました。詳細を確認してください。")
        return False


if __name__ == "__main__":
    asyncio.run(main())
