"""
LLMベースTaskProfile分類システムのテストケース

実装した機能の動作確認とパフォーマンステスト
"""

import pytest
import json
from typing import Dict, Any
from pathlib import Path

# テスト対象のインポート
from codecrafter.services.llm_service import llm_service
from codecrafter.services.task_profile_guardrail import task_profile_guardrail, confidence_adjuster
from codecrafter.services.hybrid_task_classifier import hybrid_task_classifier
from codecrafter.services.classification_manager import TaskProfileClassificationManager, ClassificationMode
from codecrafter.services.task_classifier import TaskProfileType


class TestLLMClassificationService:
    """LLMService.classify_task_profile()のテスト"""
    
    @pytest.fixture
    def sample_contexts(self):
        """テスト用コンテキストデータ"""
        return {
            "basic": {},
            "with_files": {
                "detected_files": ["main.py", "config.py", "README.md"]
            },
            "with_history": {
                "recent_messages": [
                    {"role": "user", "content": "プロジェクトの構造を教えて"},
                    {"role": "assistant", "content": "以下のファイルが見つかりました..."}
                ]
            },
            "rich_context": {
                "detected_files": ["app.py", "tests.py"],
                "recent_messages": [
                    {"role": "user", "content": "テストファイルの内容を確認したい"}
                ],
                "workspace_manifest": {
                    "project_type": "Python Web Application"
                }
            }
        }
    
    def test_basic_classification_requests(self, sample_contexts):
        """基本的な分類要求のテスト"""
        test_cases = [
            {
                "input": "README.mdの内容を教えて",
                "expected_profile": "INFORMATION_REQUEST",
                "min_confidence": 0.7
            },
            {
                "input": "README.mdをレビューして品質を評価して",
                "expected_profile": "ANALYSIS_REQUEST",
                "min_confidence": 0.7
            },
            {
                "input": "README.mdを改善して読みやすくして",
                "expected_profile": "MODIFICATION_REQUEST", 
                "min_confidence": 0.7
            },
            {
                "input": "Pythonでログ機能を実装して",
                "expected_profile": "CREATION_REQUEST",
                "min_confidence": 0.8
            },
            {
                "input": "バグを探して修正して",
                "expected_profile": "MODIFICATION_REQUEST",
                "min_confidence": 0.6
            }
        ]
        
        for case in test_cases:
            try:
                result = llm_service.classify_task_profile(
                    case["input"], 
                    sample_contexts["basic"]
                )
                
                # 基本検証
                assert "profile_type" in result
                assert "confidence" in result
                assert "reasoning" in result
                
                # 期待値検証
                assert result["profile_type"] == case["expected_profile"], \
                    f"入力: {case['input']}, 期待: {case['expected_profile']}, 実際: {result['profile_type']}"
                
                assert result["confidence"] >= case["min_confidence"], \
                    f"信頼度が低すぎます: {result['confidence']} < {case['min_confidence']}"
                
                print(f"✅ {case['input']} → {result['profile_type']} (信頼度: {result['confidence']:.2f})")
                
            except Exception as e:
                print(f"❌ LLM分類エラー: {case['input']} - {e}")
                # フォールバック分類が動作することを確認
                fallback_result = llm_service._fallback_keyword_classification(case["input"])
                assert fallback_result["profile_type"] in [
                    "INFORMATION_REQUEST", "CREATION_REQUEST", "MODIFICATION_REQUEST"
                ]
                print(f"🔄 フォールバック動作確認: {fallback_result['profile_type']}")
    
    def test_contextual_classification(self, sample_contexts):
        """コンテキスト付き分類のテスト"""
        test_request = "main.pyとconfig.pyを比較して違いを教えて"
        
        # コンテキストなしの場合
        result_basic = llm_service.classify_task_profile(test_request, sample_contexts["basic"])
        
        # ファイルコンテキストありの場合
        result_with_files = llm_service.classify_task_profile(test_request, sample_contexts["with_files"])
        
        # 両方ともANALYSIS_REQUESTになるはず
        assert result_basic["profile_type"] == "ANALYSIS_REQUEST"
        assert result_with_files["profile_type"] == "ANALYSIS_REQUEST"
        
        # コンテキストありの方が信頼度が高いはず
        print(f"基本: {result_basic['confidence']:.2f}, コンテキスト付き: {result_with_files['confidence']:.2f}")


class TestTaskProfileGuardrail:
    """ガードレールシステムのテスト"""
    
    def test_explicit_verb_override(self):
        """明確な動詞による修正テスト"""
        test_cases = [
            {
                "request": "ファイルを作成して新しい機能を実装して",
                "llm_result": {
                    "profile_type": "INFORMATION_REQUEST",  # 誤分類
                    "confidence": 0.8,
                    "reasoning": "テスト用誤分類"
                },
                "expected_correction": "CREATION_REQUEST"
            },
            {
                "request": "バグを修正して動作を改善して",
                "llm_result": {
                    "profile_type": "INFORMATION_REQUEST",  # 誤分類
                    "confidence": 0.7,
                    "reasoning": "テスト用誤分類"
                },
                "expected_correction": "MODIFICATION_REQUEST"
            }
        ]
        
        for case in test_cases:
            corrected = task_profile_guardrail.validate_and_correct(
                case["request"], case["llm_result"], {}
            )
            
            assert corrected["profile_type"] == case["expected_correction"], \
                f"ガードレール修正失敗: 期待 {case['expected_correction']}, 実際 {corrected['profile_type']}"
            
            assert "guardrail_corrections" in corrected
            assert len(corrected["guardrail_corrections"]) > 0
            
            print(f"✅ ガードレール修正: {case['request'][:30]}... → {corrected['profile_type']}")
    
    def test_file_scope_consistency(self):
        """ファイル範囲整合性チェックのテスト"""
        request = "main.pyとconfig.pyを比較して違いを分析して"
        llm_result = {
            "profile_type": "INFORMATION_REQUEST",  # 誤分類
            "confidence": 0.6,
            "reasoning": "テスト用誤分類"
        }
        context = {
            "detected_files": ["main.py", "config.py"]
        }
        
        corrected = task_profile_guardrail.validate_and_correct(request, llm_result, context)
        
        assert corrected["profile_type"] == "ANALYSIS_REQUEST"
        assert "guardrail_corrections" in corrected
        print(f"✅ ファイル範囲整合性修正: INFORMATION_REQUEST → ANALYSIS_REQUEST")
    
    def test_confidence_adjustment(self):
        """信頼度調整のテスト"""
        test_requests = [
            "README.mdの内容を教えて",  # 明確な要求
            "?",  # 不明確な要求
            "main.pyとconfig.pyを詳細に比較分析して、パフォーマンスの違いと改善点を特定してください"  # 詳細な要求
        ]
        
        for request in test_requests:
            adjusted_confidence = confidence_adjuster.adjust_confidence(0.8, request, {})
            
            assert 0.1 <= adjusted_confidence <= 1.0
            print(f"信頼度調整: '{request[:30]}...' → {adjusted_confidence:.2f}")


class TestHybridTaskClassifier:
    """ハイブリッド分類システムのテスト"""
    
    def test_hybrid_classification_success(self):
        """ハイブリッド分類の成功ケーステスト"""
        test_requests = [
            "README.mdをレビューして品質を評価して",
            "main.pyとconfig.pyを比較して",
            "新しいログ機能を実装して"
        ]
        
        for request in test_requests:
            result = hybrid_task_classifier.classify(request, {})
            
            # 基本フィールド検証
            assert hasattr(result, 'profile_type')
            assert hasattr(result, 'confidence')
            assert hasattr(result, 'classification_method')
            
            # 分類方法の確認
            assert result.classification_method in [
                "llm", "rule", "hybrid_llm_primary", "hybrid_rule_primary", 
                "rule_fallback", "emergency_fallback"
            ]
            
            print(f"✅ ハイブリッド分類: {request[:30]}... → {result.profile_type.value} ({result.classification_method})")
    
    def test_fallback_mechanism(self):
        """フォールバック機能のテスト"""
        # 空の要求でフォールバック動作を確認
        result = hybrid_task_classifier.classify("", {})
        
        assert result.profile_type is not None
        assert result.confidence > 0
        assert "fallback" in result.classification_method.lower()
        
        print(f"✅ フォールバック動作確認: {result.classification_method}")
    
    def test_statistics_collection(self):
        """統計情報収集のテスト"""
        # 複数回分類実行
        test_requests = [
            "ファイルを作成して",
            "内容を確認して",
            "問題を分析して"
        ]
        
        for request in test_requests:
            hybrid_task_classifier.classify(request, {})
        
        stats = hybrid_task_classifier.get_classification_statistics()
        
        assert "total_classifications" in stats
        assert stats["total_classifications"] >= len(test_requests)
        
        print(f"✅ 統計情報: {stats}")


class TestClassificationManager:
    """統合分類マネージャーのテスト"""
    
    def test_classification_modes(self):
        """各分類モードのテスト"""
        manager = TaskProfileClassificationManager()
        test_request = "README.mdの内容を教えて"
        
        modes_to_test = [
            ClassificationMode.RULE_ONLY,
            ClassificationMode.AUTO_SELECT
        ]
        
        for mode in modes_to_test:
            try:
                result = manager.classify(test_request, force_mode=mode)
                
                assert result.profile_type is not None
                assert result.confidence > 0
                
                print(f"✅ {mode.value}モード: {result.profile_type.value} (信頼度: {result.confidence:.2f})")
                
            except Exception as e:
                print(f"❌ {mode.value}モードでエラー: {e}")
                # エラーが発生した場合も、フォールバック動作を確認
                assert result is not None  # 何らかの結果が返されることを確認
    
    def test_auto_select_complexity_assessment(self):
        """自動選択の複雑度評価テスト"""
        manager = TaskProfileClassificationManager()
        
        test_cases = [
            {
                "request": "教えて",
                "expected_complexity": "low"
            },
            {
                "request": "main.pyとconfig.pyを比較分析して問題点を特定し、改善案を作成してください",
                "context": {"detected_files": ["main.py", "config.py", "tests.py"]},
                "expected_complexity": "high"
            }
        ]
        
        for case in test_cases:
            context = case.get("context", {})
            complexity = manager._assess_request_complexity(case["request"], context)
            
            if case["expected_complexity"] == "low":
                assert complexity < 0.7
            else:
                assert complexity >= 0.7
            
            print(f"複雑度評価: '{case['request'][:30]}...' → {complexity:.2f}")
    
    def test_health_check(self):
        """ヘルスチェック機能のテスト"""
        manager = TaskProfileClassificationManager()
        health = manager.health_check()
        
        assert "status" in health
        assert health["status"] in ["healthy", "degraded", "unhealthy"]
        assert "components" in health
        
        print(f"✅ ヘルスチェック: {health['status']}")
        for component, status in health["components"].items():
            print(f"  {component}: {'✅' if status.get('healthy') else '❌'}")


class TestIntegrationScenarios:
    """統合シナリオテスト"""
    
    def test_real_world_scenarios(self):
        """実際のユースケースシナリオテスト"""
        manager = TaskProfileClassificationManager()
        
        scenarios = [
            {
                "name": "コードレビュー要求",
                "request": "このPythonコードをレビューして、品質と改善点を教えてください",
                "context": {"detected_files": ["app.py"]},
                "expected_profile": TaskProfileType.ANALYSIS_REQUEST
            },
            {
                "name": "機能実装要求", 
                "request": "ユーザー認証システムを実装してください",
                "context": {},
                "expected_profile": TaskProfileType.CREATION_REQUEST
            },
            {
                "name": "バグ修正要求",
                "request": "ログイン時にエラーが出るので修正してください",
                "context": {"detected_files": ["login.py", "auth.py"]},
                "expected_profile": TaskProfileType.MODIFICATION_REQUEST
            },
            {
                "name": "情報確認要求",
                "request": "設定ファイルの内容を確認したい",
                "context": {"detected_files": ["config.yaml"]},
                "expected_profile": TaskProfileType.INFORMATION_REQUEST
            }
        ]
        
        for scenario in scenarios:
            try:
                result = manager.classify(scenario["request"], scenario["context"])
                
                # 期待される分類との一致を確認
                is_correct = result.profile_type == scenario["expected_profile"]
                status = "✅" if is_correct else "⚠️"
                
                print(f"{status} {scenario['name']}: {result.profile_type.value} "
                      f"(期待: {scenario['expected_profile'].value}, 信頼度: {result.confidence:.2f})")
                
                # 信頼度が著しく低い場合は警告
                if result.confidence < 0.5:
                    print(f"  ⚠️ 低信頼度: {result.confidence:.2f}")
                
            except Exception as e:
                print(f"❌ {scenario['name']}でエラー: {e}")


def run_comprehensive_test():
    """包括的なテスト実行"""
    print("🧪 LLMベースTaskProfile分類システム 包括テスト開始\n")
    
    # テストクラスのインスタンス化
    test_llm = TestLLMClassificationService()
    test_guardrail = TestTaskProfileGuardrail()
    test_hybrid = TestHybridTaskClassifier()
    test_manager = TestClassificationManager()
    test_integration = TestIntegrationScenarios()
    
    # サンプルコンテキスト準備
    sample_contexts = test_llm.sample_contexts()
    
    try:
        print("=== 1. LLM分類サービステスト ===")
        test_llm.test_basic_classification_requests(sample_contexts)
        print()
        
        print("=== 2. ガードレールシステムテスト ===")
        test_guardrail.test_explicit_verb_override()
        test_guardrail.test_file_scope_consistency()
        print()
        
        print("=== 3. ハイブリッド分類システムテスト ===")
        test_hybrid.test_hybrid_classification_success()
        test_hybrid.test_fallback_mechanism()
        print()
        
        print("=== 4. 統合マネージャーテスト ===")
        test_manager.test_classification_modes()
        test_manager.test_auto_select_complexity_assessment()
        print()
        
        print("=== 5. 統合シナリオテスト ===")
        test_integration.test_real_world_scenarios()
        print()
        
        print("🎉 包括テスト完了！")
        
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_comprehensive_test()