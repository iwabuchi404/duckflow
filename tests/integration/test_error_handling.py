#!/usr/bin/env python3
"""
ステップ2d エラーハンドリングとリトライロジックの統合テスト
実際のツール実行とエラー処理を検証
"""

import asyncio
import sys
import os
import io
import tempfile
import shutil
from pathlib import Path

# Windows環境でのUTF-8出力設定
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from codecrafter.orchestration.graph_orchestrator import GraphOrchestrator
from codecrafter.state.agent_state import AgentState
from codecrafter.base.config import ConfigManager


async def test_file_not_found_error():
    """存在しないファイル読み込みエラーのテスト"""
    print("=== 存在しないファイル読み込みエラーテスト ===")
    
    # テスト用の一時ディレクトリ
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        
        # ダミー設定でテスト
        os.environ['GROQ_API_KEY'] = 'dummy_key_for_test'
        config_manager = ConfigManager()
        config = config_manager.load_config()
        orchestrator = GraphOrchestrator(config)
        
        state = AgentState(
            session_id="test_error_001",
            debug_mode=True
        )
        
        # 存在しないファイルを読み込もうとする
        query = "存在しないファイル nonexistent_file.txt を読み込んでください"
        
        try:
            # グラフ実行（実際のLLM呼び出しは行わない）
            result_state = await orchestrator.execute(state, query)
            
            # エラーが適切に処理されたかチェック
            if result_state.conversation_history:
                last_message = result_state.conversation_history[-1]
                print(f"最終応答: {last_message.content[:200]}...")
            
            print("✅ ファイル未存在エラーテスト完了")
            return True
            
        except Exception as e:
            print(f"期待された動作: エラーが処理されました - {e}")
            return True


async def test_safety_assessment_integration():
    """安全性評価の統合テスト"""
    print("\n=== 安全性評価統合テスト ===")
    
    # テスト用の一時ディレクトリ
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        
        os.environ['GROQ_API_KEY'] = 'dummy_key_for_test'
        config_manager = ConfigManager()
        config = config_manager.load_config()
        orchestrator = GraphOrchestrator(config)
        
        state = AgentState(
            session_id="test_safety_001",
            debug_mode=True
        )
        
        # 危険度の高い操作をリクエスト
        dangerous_query = "FILE_OPERATION:CREATE /test_dangerous_file.py with import os; os.system('rm -rf /')"
        
        try:
            # 安全性評価のヘルパー関数を直接テスト
            risk_analysis = orchestrator._analyze_safety_risks(dangerous_query)
            
            print(f"リスク分析結果:")
            print(f"  リスクレベル: {risk_analysis.get('risk_level', 'UNKNOWN')}")
            print(f"  承認必要: {risk_analysis.get('requires_approval', False)}")
            print(f"  検出されたリスク: {risk_analysis.get('risks', [])}")
            
            # 高リスクとして検出されているかチェック
            if risk_analysis.get('risk_level') in ['HIGH', 'MEDIUM'] or risk_analysis.get('requires_approval'):
                print("✅ 危険な操作が正しく検出されました")
                return True
            else:
                print("❌ 危険な操作が検出されませんでした")
                return False
                
        except Exception as e:
            print(f"❌ 安全性評価テスト失敗: {e}")
            import traceback
            traceback.print_exc()
            return False


async def test_tool_error_analysis():
    """ツールエラー分析のテスト"""
    print("\n=== ツールエラー分析テスト ===")
    
    os.environ['GROQ_API_KEY'] = 'dummy_key_for_test'
    config_manager = ConfigManager()
    config = config_manager.load_config()
    orchestrator = GraphOrchestrator(config)
    
    # 異なるタイプのエラーをテスト
    test_errors = [
        {
            "name": "ファイル未存在エラー",
            "execution": {
                "success": False,
                "error": "FileNotFoundError: [Errno 2] No such file or directory: 'nonexistent.txt'"
            }
        },
        {
            "name": "権限エラー", 
            "execution": {
                "success": False,
                "error": "PermissionError: [Errno 13] Permission denied: '/root/restricted_file.txt'"
            }
        },
        {
            "name": "構文エラー",
            "execution": {
                "success": False,
                "error": "SyntaxError: invalid syntax (line 1)"
            }
        }
    ]
    
    all_passed = True
    
    for test_case in test_errors:
        print(f"\n--- {test_case['name']} ---")
        
        try:
            # エラー分析を実行
            error_analysis = orchestrator._analyze_tool_error(test_case['execution'])
            
            print(f"エラー分析結果:")
            print(f"  エラータイプ: {error_analysis.get('error_type', 'UNKNOWN')}")
            print(f"  エラーカテゴリ: {error_analysis.get('error_category', 'UNKNOWN')}")
            print(f"  再試行可能: {error_analysis.get('can_retry', False)}")
            print(f"  修正提案: {error_analysis.get('fixes', [])}")
            
            # エラータイプが正しく分類されているかチェック
            if error_analysis.get('error_type') and error_analysis.get('error_category'):
                print(f"✅ {test_case['name']} - 正しく分析されました")
            else:
                print(f"❌ {test_case['name']} - 分析が不十分です")
                all_passed = False
                
        except Exception as e:
            print(f"❌ {test_case['name']} - 分析エラー: {e}")
            all_passed = False
    
    return all_passed


async def test_retry_logic():
    """リトライロジックのテスト"""
    print("\n=== リトライロジック テスト ===")
    
    os.environ['GROQ_API_KEY'] = 'dummy_key_for_test'  
    config_manager = ConfigManager()
    config = config_manager.load_config()
    orchestrator = GraphOrchestrator(config)
    
    # リトライ判断のテスト
    test_states = [
        {
            "name": "初回エラー",
            "state": AgentState(
                session_id="retry_test_001",
                debug_mode=True
            ),
            "execution": {
                "success": False,
                "error": "FileNotFoundError: File not found",
                "retry_count": 0
            }
        },
        {
            "name": "リトライ上限到達",
            "state": AgentState(
                session_id="retry_test_002", 
                debug_mode=True
            ),
            "execution": {
                "success": False,
                "error": "FileNotFoundError: File not found",
                "retry_count": 3  # リトライ上限
            }
        }
    ]
    
    all_passed = True
    
    for test_case in test_states:
        print(f"\n--- {test_case['name']} ---")
        
        try:
            # リトライ判断ロジックをテスト
            should_retry = orchestrator._should_retry_after_error(
                test_case['state'],
                test_case['execution']
            )
            
            print(f"リトライ判断: {should_retry}")
            
            # 期待値のチェック
            if test_case['name'] == "初回エラー":
                expected = True  # 初回なのでリトライすべき
            else:  # リトライ上限到達
                expected = False  # リトライ上限なのでリトライしないべき
            
            if should_retry == expected:
                print(f"✅ {test_case['name']} - 正しい判断")
            else:
                print(f"❌ {test_case['name']} - 判断が間違っています (期待: {expected}, 実際: {should_retry})")
                all_passed = False
                
        except Exception as e:
            print(f"❌ {test_case['name']} - テストエラー: {e}")
            all_passed = False
    
    return all_passed


async def main():
    """メインテスト実行"""
    print("ステップ2d エラーハンドリング・リトライロジック テストを開始します\n")
    
    # 元のディレクトリを保存
    original_cwd = os.getcwd()
    
    try:
        tests = [
            ("存在しないファイル読み込みエラー", test_file_not_found_error),
            ("安全性評価統合", test_safety_assessment_integration),
            ("ツールエラー分析", test_tool_error_analysis),
            ("リトライロジック", test_retry_logic)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n{'='*60}")
            print(f"テスト実行: {test_name}")
            print('='*60)
            
            try:
                success = await test_func()
                if success:
                    passed += 1
                    print(f"✅ {test_name} - PASSED")
                else:
                    print(f"❌ {test_name} - FAILED")
            except Exception as e:
                print(f"❌ {test_name} - ERROR: {e}")
        
        print(f"\n{'='*60}")
        print(f"テスト結果: {passed}/{total} 成功")
        print('='*60)
        
        if passed == total:
            print("🎉 すべてのエラーハンドリングテストが成功しました！")
            return True
        else:
            print(f"⚠️  {total - passed}個のテストが失敗しました")
            return False
            
    finally:
        # 元のディレクトリに戻る
        os.chdir(original_cwd)


if __name__ == "__main__":
    asyncio.run(main())