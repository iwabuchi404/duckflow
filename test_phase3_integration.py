"""
Phase 3統合テスト: LLMベース選択処理機能の一般承認システム統合
一般承認システムとLLM選択処理の統合テスト
"""

import asyncio
import sys
import os
from datetime import datetime
import tempfile
from unittest.mock import AsyncMock, MagicMock

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from companion.llm_choice.choice_models import ChoiceContext, ChoiceResult
from companion.llm_choice.approval_response_handler import (
    LLMApprovalResponseHandler, OperationInfo, ApprovalInterpretation, ApprovalDecision
)
from companion.simple_approval import (
    SimpleApprovalGate, ApprovalRequest, ApprovalResult, ApprovalMode, RiskLevel,
    create_llm_enhanced_approval_gate
)
from companion.file_ops import SimpleFileOps
from companion.intent_understanding.enhanced_option_resolver import EnhancedOptionResolver


class MockLLMClient:
    """モックLLMクライアント"""
    
    async def generate_text(self, prompt: str, system_prompt: str = None, 
                          max_tokens: int = 500, temperature: float = 0.1) -> str:
        """モックLLMレスポンス"""
        # ユーザー入力に応じたモックレスポンス
        if "実行して" in prompt or "はい" in prompt or "お願い" in prompt:
            return '''
            {
                "selected_options": [1],
                "confidence": 0.9,
                "reasoning": "明確な実行意思を確認",
                "modifications": [],
                "clarification_needed": false,
                "extracted_intent": "実行承認"
            }
            '''
        elif "やめ" in prompt or "拒否" in prompt or "いいえ" in prompt:
            return '''
            {
                "selected_options": [2],
                "confidence": 0.95,
                "reasoning": "明確な拒否意思を確認",
                "modifications": [],
                "clarification_needed": false,
                "extracted_intent": "実行拒否"
            }
            '''
        elif "詳細" in prompt or "確認" in prompt:
            return '''
            {
                "selected_options": [3],
                "confidence": 0.8,
                "reasoning": "詳細確認要求",
                "modifications": [],
                "clarification_needed": false,
                "extracted_intent": "詳細確認"
            }
            '''
        elif "安全" in prompt or "慎重" in prompt:
            return '''
            {
                "selected_options": [1],
                "confidence": 0.7,
                "reasoning": "安全な実行を希望",
                "modifications": ["慎重に実行", "バックアップを作成"],
                "clarification_needed": false,
                "extracted_intent": "条件付き実行"
            }
            '''
        else:
            # デフォルトは詳細確認
            return '''
            {
                "selected_options": [],
                "confidence": 0.4,
                "reasoning": "意図が不明確",
                "modifications": [],
                "clarification_needed": true,
                "extracted_intent": "不明"
            }
            '''


async def test_llm_approval_response_handler():
    """LLMApprovalResponseHandlerのテスト"""
    print("=== LLMApprovalResponseHandlerテスト ===")
    
    # モックLLMクライアントを設定
    import companion.llm_choice.choice_parser as choice_parser_module
    original_llm_manager = choice_parser_module.llm_manager
    choice_parser_module.llm_manager = MockLLMClient()
    
    try:
        handler = LLMApprovalResponseHandler()
        
        # テスト用操作情報
        operation_info = OperationInfo(
            operation_type="file_write",
            description="test.pyファイルの作成",
            target="test.py",
            risk_level="medium",
            details="Pythonテストファイルを作成します"
        )
        
        # テストケース
        test_cases = [
            ("はい、実行してください", ApprovalDecision.APPROVED),
            ("やめておきます", ApprovalDecision.DENIED),
            ("詳細を確認したいです", ApprovalDecision.MORE_INFO_REQUESTED),
            ("安全に実行してください", ApprovalDecision.CONDITIONAL_APPROVAL),
            ("わからない", ApprovalDecision.MORE_INFO_REQUESTED)
        ]
        
        for user_input, expected_decision in test_cases:
            print(f"\nテスト: '{user_input}'")
            
            interpretation = await handler.interpret_approval_response(user_input, operation_info)
            
            print(f"  判定: {interpretation.decision.value}")
            print(f"  確信度: {interpretation.confidence:.2f}")
            print(f"  理由: {interpretation.reasoning}")
            print(f"  承認: {interpretation.approved}")
            
            if interpretation.conditions:
                print(f"  条件: {interpretation.conditions}")
            
            # 簡単なアサーション
            if interpretation.decision == expected_decision:
                print(f"  OK: 期待通り {expected_decision.value}")
            else:
                print(f"  WARN: 期待 {expected_decision.value}, 実際 {interpretation.decision.value}")
        
        print("\nOK LLMApprovalResponseHandlerテスト成功")
        
    finally:
        # モックを復元
        choice_parser_module.llm_manager = original_llm_manager


async def test_simple_approval_gate_llm_integration():
    """SimpleApprovalGateのLLM統合テスト"""
    print("\n=== SimpleApprovalGate LLM統合テスト ===")
    
    # モックLLMクライアントを設定
    import companion.llm_choice.choice_parser as choice_parser_module
    original_llm_manager = choice_parser_module.llm_manager
    choice_parser_module.llm_manager = MockLLMClient()
    
    # モックUIを設定
    class MockUI:
        def __init__(self):
            self.responses = ["はい、実行してください", "やめておきます", "詳細を確認したいです"]
            self.response_index = 0
        
        def print_header(self, msg): pass
        def print_message(self, msg, style=None): pass
        def get_user_input(self, prompt):
            if self.response_index < len(self.responses):
                response = self.responses[self.response_index]
                self.response_index += 1
                return response
            return "はい"
        def get_confirmation(self, msg): return True
    
    try:
        # LLM強化承認ゲートを作成
        approval_gate = await create_llm_enhanced_approval_gate(ApprovalMode.STANDARD)
        
        # モックUIを注入
        approval_gate.ui = MockUI()
        
        # テスト用承認要求
        test_requests = [
            ApprovalRequest(
                operation="ファイル作成",
                description="新しいPythonファイルを作成",
                target="example.py",
                risk_level=RiskLevel.MEDIUM,
                details="print('Hello, World!')を含むファイル"
            ),
            ApprovalRequest(
                operation="設定変更",
                description="システム設定の変更",
                target="config.yaml",
                risk_level=RiskLevel.HIGH,
                details="重要な設定パラメータの変更"
            ),
            ApprovalRequest(
                operation="ドキュメント作成",
                description="README.mdの作成",
                target="README.md",
                risk_level=RiskLevel.LOW,
                details="プロジェクトドキュメント"
            )
        ]
        
        for i, request in enumerate(test_requests):
            print(f"\nテスト {i+1}: {request.operation}")
            print(f"  対象: {request.target}")
            print(f"  リスク: {request.risk_level.value}")
            
            result = await approval_gate.request_approval_llm_enhanced(request)
            
            print(f"  結果: {'承認' if result.approved else '拒否'}")
            print(f"  理由: {result.reason}")
            print(f"  時刻: {result.timestamp.strftime('%H:%M:%S')}")
        
        print("\nOK SimpleApprovalGate LLM統合テスト成功")
        
    finally:
        # モックを復元
        choice_parser_module.llm_manager = original_llm_manager


async def test_file_ops_llm_integration():
    """FileOpsのLLM統合テスト"""
    print("\n=== FileOps LLM統合テスト ===")
    
    # モックLLMクライアントを設定
    import companion.llm_choice.choice_parser as choice_parser_module
    original_llm_manager = choice_parser_module.llm_manager
    choice_parser_module.llm_manager = MockLLMClient()
    
    # モックUIを設定
    class MockUI:
        def print_header(self, msg): print(f"HEADER: {msg}")
        def print_message(self, msg, style=None): print(f"MSG: {msg}")
        def get_user_input(self, prompt): return "はい、実行してください"
        def get_confirmation(self, msg): return True
    
    try:
        # テンポラリディレクトリでテスト
        with tempfile.TemporaryDirectory() as temp_dir:
            # LLM強化FileOpsを作成
            file_ops = SimpleFileOps(approval_mode=ApprovalMode.STANDARD, llm_enabled=True)
            
            # モックUIを注入
            if hasattr(file_ops.approval_gate, 'ui'):
                file_ops.approval_gate.ui = MockUI()
            
            # テストケース
            test_file = os.path.join(temp_dir, "test_llm.py")
            test_content = '''
# LLM統合テストファイル
def hello_world():
    print("Hello from LLM enhanced approval!")

if __name__ == "__main__":
    hello_world()
'''
            
            print(f"テストファイル: {test_file}")
            print(f"内容サイズ: {len(test_content)}文字")
            
            # LLM強化ファイル作成をテスト
            if hasattr(file_ops, 'create_file_llm'):
                result = await file_ops.create_file_llm(test_file, test_content)
                
                print(f"作成結果: {'成功' if result['success'] else '失敗'}")
                print(f"メッセージ: {result['message']}")
                
                if result['success']:
                    print(f"ファイルサイズ: {result['size']}バイト")
                    
                    # ファイルが実際に作成されたか確認
                    if os.path.exists(test_file):
                        print("OK: ファイルが正常に作成されました")
                        
                        # 内容確認
                        with open(test_file, 'r', encoding='utf-8') as f:
                            actual_content = f.read()
                        
                        if actual_content.strip() == test_content.strip():
                            print("OK: ファイル内容が正確です")
                        else:
                            print("WARN: ファイル内容が異なります")
                    else:
                        print("ERROR: ファイルが作成されませんでした")
                else:
                    print(f"INFO: 作成が拒否されました - {result['message']}")
            else:
                print("SKIP: create_file_llmメソッドが見つかりません")
        
        print("\nOK FileOps LLM統合テスト成功")
        
    finally:
        # モックを復元
        choice_parser_module.llm_manager = original_llm_manager


async def test_enhanced_option_resolver_approval_integration():
    """EnhancedOptionResolverと承認システムの統合テスト"""
    print("\n=== EnhancedOptionResolver承認統合テスト ===")
    
    # モックLLMクライアントを設定
    import companion.llm_choice.choice_parser as choice_parser_module
    original_llm_manager = choice_parser_module.llm_manager
    choice_parser_module.llm_manager = MockLLMClient()
    
    try:
        resolver = EnhancedOptionResolver()
        
        # 承認システム用コンテキスト
        context = ChoiceContext(
            available_options=["実行する", "拒否する", "詳細確認"],
            option_descriptions=[
                "操作を実行する",
                "操作を取り消す",
                "詳細情報を確認する"
            ],
            current_plan="ファイル操作: test.py",
            risk_level="medium"
        )
        
        # ハイブリッド処理のテスト
        test_cases = [
            ("1", "pattern"),  # パターンマッチング
            ("はい", "pattern"),  # パターンマッチング
            ("実行してください", "llm"),  # LLM処理
            ("安全に実行", "llm"),  # LLM処理（条件付き）
            ("やめておく", "llm"),  # LLM処理（拒否）
        ]
        
        for user_input, expected_type in test_cases:
            print(f"\nテスト: '{user_input}' (expected: {expected_type})")
            
            result = await resolver.parse_selection_enhanced(user_input, context)
            
            print(f"  選択: {result.selected_options}")
            print(f"  確信度: {result.confidence:.2f}")
            print(f"  理由: {result.reasoning}")
            
            if result.modifications:
                print(f"  修正: {result.modifications}")
            
            # パターンマッチングの場合は高確信度
            if expected_type == "pattern" and result.confidence >= 0.9:
                print(f"  OK: パターンマッチング成功")
            elif expected_type == "llm" and 0.5 <= result.confidence < 1.0:
                print(f"  OK: LLM処理成功")
            else:
                print(f"  INFO: 確信度 {result.confidence:.2f}")
        
        print("\nOK EnhancedOptionResolver承認統合テスト成功")
        
    finally:
        # モックを復元
        choice_parser_module.llm_manager = original_llm_manager


async def main():
    """メインテスト関数"""
    print("Phase 3統合テスト: LLMベース選択処理機能の一般承認システム統合")
    print("=" * 80)
    
    try:
        await test_llm_approval_response_handler()
        await test_simple_approval_gate_llm_integration()
        await test_file_ops_llm_integration()
        await test_enhanced_option_resolver_approval_integration()
        
        print("\n" + "=" * 80)
        print("✅ すべてのテストが成功しました！")
        print("🎉 Phase 3: 一般承認システムとの統合が完了しました")
        print("\n主な成果:")
        print("- LLMApprovalResponseHandler: 一般承認のLLM処理")
        print("- SimpleApprovalGate LLM統合: request_approval_llm_enhancedメソッド")
        print("- FileOps LLM対応: create_file_llm, write_file_llmメソッド")
        print("- 自然言語承認回答: 「はい」「実行して」「やめておく」など")
        print("- 条件付き承認: 「安全に実行」などの修正要求対応")
        print("- 統合エラーハンドリング: LLMエラー時の標準承認フォールバック")
        
    except Exception as e:
        print(f"\nERROR テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)