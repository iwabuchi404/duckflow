"""
Simple Test for Intent Understanding System

基本的な動作確認用のテストファイル
"""

import sys
import os

# パスを追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """インポートのテスト"""
    try:
        print("🔄 インポートテスト開始...")
        
        # 基本モジュールのインポート
        from companion.llm.llm_client import LLMClient, LLMProvider
        print("✅ LLMClient インポート成功")
        
        from companion.intent_understanding.llm_intent_analyzer import LLMIntentAnalyzer
        print("✅ LLMIntentAnalyzer インポート成功")
        
        from companion.intent_understanding.task_profile_classifier import TaskProfileClassifier
        print("✅ TaskProfileClassifier インポート成功")
        
        from companion.task_management.task_hierarchy import TaskHierarchy
        print("✅ TaskHierarchy インポート成功")
        
        from companion.task_management.pecking_order import PeckingOrder
        print("✅ PeckingOrder インポート成功")
        
        from companion.intent_understanding.intent_integration import IntentUnderstandingSystem
        print("✅ IntentUnderstandingSystem インポート成功")
        
        print("🎉 全てのインポートが成功しました！")
        return True
        
    except Exception as e:
        print(f"❌ インポートエラー: {e}")
        return False

def test_basic_creation():
    """基本的なオブジェクト作成のテスト"""
    try:
        print("\n🔄 基本オブジェクト作成テスト開始...")
        
        # モックLLMクライアントの作成
        from companion.test_mock_llm import mock_llm_client
        print("✅ モックLLMクライアント作成成功")
        
        # 統合システムの作成
        from companion.intent_understanding.intent_integration import IntentUnderstandingSystem
        system = IntentUnderstandingSystem(mock_llm_client)
        print("✅ 統合意図理解システム作成成功")
        
        # システム状態の確認
        status = system.get_system_status()
        print(f"✅ システム状態取得成功: {len(status)}個の項目")
        
        print("🎉 基本オブジェクト作成テストが成功しました！")
        return True
        
    except Exception as e:
        print(f"❌ 基本オブジェクト作成エラー: {e}")
        return False

def main():
    """メイン関数"""
    print("🦆 Duckflow 簡易テスト開始")
    print("=" * 50)
    
    # インポートテスト
    if not test_imports():
        print("❌ インポートテストが失敗しました")
        return
    
    # 基本オブジェクト作成テスト
    if not test_basic_creation():
        print("❌ 基本オブジェクト作成テストが失敗しました")
        return
    
    print("\n🎉 全てのテストが成功しました！")
    print("システムは正常に動作しています。")

if __name__ == "__main__":
    main()
