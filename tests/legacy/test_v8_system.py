#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V8システムのテスト

JSON+LLM方式の動作確認テスト
"""

import asyncio
import logging
import sys
from pathlib import Path

# パス設定
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / "companion"))

# V8システムのテスト
def test_human_formatter():
    """HumanOutputFormatterのテスト"""
    print("\n=== HumanOutputFormatter テスト ===")
    
    try:
        from companion.output.human_formatter import HumanOutputFormatter, FormatterRequest
        
        formatter = HumanOutputFormatter()
        
        # テストデータ（ファイル分析結果）
        test_data = {
            "operation": "構造分析",
            "file_path": "game_doc.md",
            "file_info": {
                "total_lines": 40,
                "total_chars": 1500,
                "encoding": "utf-8"
            },
            "headers": [
                {"line_number": 1, "level": 1, "text": "RPGゲーム「勇者の旅路」設計ドキュメント"},
                {"line_number": 3, "level": 2, "text": "ゲーム概要"},
                {"line_number": 7, "level": 2, "text": "主要システム"}
            ],
            "sections": [
                {"title": "ゲーム概要", "level": 2, "start_line": 3, "end_line": 6},
                {"title": "主要システム", "level": 2, "start_line": 7, "end_line": 22}
            ],
            "tool_used": "structure_analyzer"
        }
        
        # フォーマット要求作成
        request = FormatterRequest(
            data=test_data,
            context="ゲームドキュメントの分析",
            format_type="file_analysis",
            user_intent="ファイルの内容を理解したい"
        )
        
        # 同期版フォーマット（テンプレートベース）
        result = formatter._format_with_template(request, formatter.templates['file_analysis'])
        
        print(f"✅ フォーマット成功")
        print(f"要約: {result.summary}")
        print(f"内容:\n{result.human_text}")
        
        return True
        
    except Exception as e:
        print(f"❌ HumanOutputFormatterテストエラー: {e}")
        return False

def test_structured_file_ops():
    """StructuredFileOpsのテスト"""
    print("\n=== StructuredFileOps テスト ===")
    
    try:
        from companion.tools.structured_file_ops import (
            StructuredFileOps, 
            AnalyzeFileRequest, 
            SearchContentRequest
        )
        from companion.simple_approval import ApprovalMode
        
        # 自動承認モードで初期化
        file_ops = StructuredFileOps(approval_mode=ApprovalMode.AUTO_APPROVE)
        
        # ファイル分析テスト
        if Path("game_doc.md").exists():
            print("📄 ファイル分析テスト")
            
            request = AnalyzeFileRequest(
                file_path="game_doc.md",
                include_content_preview=True,
                max_headers=10
            )
            
            response = file_ops.analyze_file_structure(request)
            
            print(f"  ファイルパス: {response.file_path}")
            print(f"  成功: {response.success}")
            print(f"  総行数: {response.file_info.total_lines}")
            print(f"  ヘッダー数: {len(response.headers)}")
            print(f"  セクション数: {len(response.sections)}")
            
            # 検索テスト
            print("\n🔍 検索テスト")
            search_request = SearchContentRequest(
                file_path="game_doc.md",
                pattern="ゲーム|概要|システム",
                context_lines=1,
                max_results=5
            )
            
            search_response = file_ops.search_content(search_request)
            print(f"  検索パターン: {search_response.pattern}")
            print(f"  マッチ数: {search_response.matches_found}")
            print(f"  成功: {search_response.success}")
            
            for i, match in enumerate(search_response.results[:3]):
                print(f"    {i+1}. L{match.line_number}: {match.match_text}")
        else:
            print("⚠️ game_doc.md が見つかりません - ダミーテストを実行")
            
            # ダミーファイルでテスト
            dummy_request = AnalyzeFileRequest(file_path="nonexistent.md")
            dummy_response = file_ops.analyze_file_structure(dummy_request)
            
            print(f"  エラーハンドリング確認: {not dummy_response.success}")
            print(f"  エラーメッセージ: {dummy_response.error_message}")
        
        return True
        
    except Exception as e:
        print(f"❌ StructuredFileOpsテストエラー: {e}")
        return False

def test_v8_integration():
    """V8統合テスト（基本動作確認）"""
    print("\n=== V8統合テスト ===")
    
    try:
        # モックのDualLoopSystemを作成
        class MockDualLoopSystem:
            def __init__(self):
                self.agent_state = MockAgentState()
                self.llm_call_manager = None
                self.llm_service = None
                self.intent_analyzer = None
                self.prompt_context_service = None
        
        class MockAgentState:
            def __init__(self):
                self.action_results = {}
                
            def add_action_result(self, action_id, result):
                self.action_results[action_id] = result
                
            def get_action_result_by_id(self, action_id):
                return self.action_results.get(action_id)
        
        # V8コア初期化テスト
        from companion.enhanced_core_v8 import EnhancedCompanionCoreV8
        
        mock_system = MockDualLoopSystem()
        core_v8 = EnhancedCompanionCoreV8(mock_system)
        
        print("✅ V8コア初期化成功")
        print(f"  ツール数: {len(core_v8.tools)}")
        print(f"  ファイル操作ツール: {'structured_file_ops' in core_v8.tools}")
        print(f"  フォーマッター: {core_v8.human_formatter is not None}")
        
        # ActionV8テスト
        from companion.enhanced_core_v8 import ActionV8
        
        test_action = ActionV8(
            operation="structured_file_ops.analyze_file_structure",
            args={"file_path": "game_doc.md"},
            reasoning="テスト実行",
            action_id="test_001",
            needs_human_formatting=True
        )
        
        print(f"✅ ActionV8作成成功: {test_action.operation}")
        
        return True
        
    except Exception as e:
        print(f"❌ V8統合テストエラー: {e}")
        return False

async def test_v8_full_flow():
    """V8完全フローテスト（非同期）"""
    print("\n=== V8完全フロー テスト ===")
    
    try:
        # 基本的な非同期処理テスト
        from companion.enhanced_core_v8 import EnhancedCompanionCoreV8
        
        # モッククラス
        class MockLLMService:
            async def generate_direct_response(self, message, context):
                return f"モック応答: {message[:20]}..."
                
            async def generate_text(self, prompt):
                return f"LLMモック応答\n詳細な説明をここに記載します。"
        
        class MockDualLoopSystem:
            def __init__(self):
                self.agent_state = MockAgentState()
                self.llm_call_manager = None
                self.llm_service = MockLLMService()
                self.intent_analyzer = None
                self.prompt_context_service = None
        
        class MockAgentState:
            def __init__(self):
                self.action_results = {}
                
            def add_action_result(self, action_id, result):
                self.action_results[action_id] = result
                print(f"    📝 AgentState保存: {action_id}")
                
            def get_action_result_by_id(self, action_id):
                return self.action_results.get(action_id)
        
        # フルシステムテスト
        mock_system = MockDualLoopSystem()
        core_v8 = EnhancedCompanionCoreV8(mock_system)
        
        # 直接応答テスト
        print("🔄 直接応答テスト")
        response = await core_v8._handle_direct_response(
            "こんにちは", 
            {"action_type": "direct_response", "confidence": 0.8}
        )
        print(f"  応答: {response}")
        
        # ActionList生成テスト
        print("\n📋 ActionList生成テスト")
        actions = await core_v8._generate_action_list_v8(
            "game_doc.md を読んで内容を分析してください",
            {"action_type": "action_execution", "confidence": 0.9}
        )
        print(f"  生成されたAction数: {len(actions)}")
        for action in actions:
            print(f"    - {action.operation} (format: {action.needs_human_formatting})")
        
        print("\n✅ V8完全フローテスト成功")
        return True
        
    except Exception as e:
        print(f"❌ V8完全フローテストエラー: {e}")
        return False

def main():
    """テストメイン実行"""
    print("🚀 V8システムテスト開始")
    
    # ログ設定
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    success_count = 0
    total_tests = 4
    
    # 個別コンポーネントテスト
    if test_human_formatter():
        success_count += 1
    
    if test_structured_file_ops():
        success_count += 1
    
    if test_v8_integration():
        success_count += 1
    
    # 非同期テスト
    try:
        if asyncio.run(test_v8_full_flow()):
            success_count += 1
    except Exception as e:
        print(f"❌ 非同期テストでエラー: {e}")
    
    # 結果まとめ
    print(f"\n🎯 テスト結果: {success_count}/{total_tests} 成功")
    
    if success_count == total_tests:
        print("✅ 全テスト成功 - V8システムの基本動作が確認されました")
        return 0
    else:
        print("⚠️ 一部テスト失敗 - 問題を確認してください")
        return 1

if __name__ == "__main__":
    exit(main())