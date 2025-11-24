#!/usr/bin/env python3
"""
PromptSmith AI設定システムのテストスクリプト
役割別AI設定の動作確認を行う
"""

import sys
import os
sys.path.append('.')

from codecrafter.base.config import config_manager
from codecrafter.promptsmith.llm_manager import promptsmith_llm_manager
from codecrafter.promptsmith.ai_roles.tester_ai import TesterAI


def test_config_loading():
    """設定読み込みテスト"""
    print("=== 設定読み込みテスト ===")
    
    try:
        # メイン設定の読み込み
        config = config_manager.load_config()
        print(f"✅ メイン設定読み込み成功")
        print(f"   メインLLMプロバイダー: {config.llm.provider}")
        
        # PromptSmith設定の読み込み
        promptsmith_config = config_manager.get_promptsmith_config()
        if promptsmith_config:
            print(f"✅ PromptSmith設定読み込み成功")
            print(f"   評価システム有効: {promptsmith_config.evaluation.enabled}")
            print(f"   役割別AI使用: {promptsmith_config.evaluation.separate_ai_roles}")
            
            # 各AI役割の設定を確認
            roles = ["tester_ai", "evaluator_ai", "optimizer_ai", "conversation_analyzer", "target_ai"]
            for role in roles:
                provider = config_manager.get_promptsmith_provider(role)
                ai_config = config_manager.get_promptsmith_ai_config(role)
                print(f"   {role}: {provider} - {ai_config.get('model', 'N/A') if ai_config else 'N/A'}")
        else:
            print("❌ PromptSmith設定が見つかりません")
            
    except Exception as e:
        print(f"❌ 設定読み込みエラー: {e}")
        return False
    
    return True


def test_llm_manager():
    """LLM管理システムテスト"""
    print("\n=== LLM管理システムテスト ===")
    
    try:
        # 役割別設定が有効かどうかを確認
        is_separate_enabled = promptsmith_llm_manager.is_separate_roles_enabled()
        print(f"役割別AI設定: {'有効' if is_separate_enabled else '無効'}")
        
        # 全AI役割の情報を取得
        roles_info = promptsmith_llm_manager.get_all_roles_info()
        
        for role, info in roles_info.items():
            print(f"\n{role}:")
            print(f"  プロバイダー: {info['provider']}")
            print(f"  APIキー: {'有り' if info['has_api_key'] else '無し'}")
            print(f"  設定: {info['config']}")
        
        return True
        
    except Exception as e:
        print(f"❌ LLM管理システムエラー: {e}")
        return False


def test_ai_role_clients():
    """AI役割別クライアントテスト"""
    print("\n=== AI役割別クライアントテスト ===")
    
    test_roles = ["tester_ai", "evaluator_ai", "target_ai"]
    successful_tests = 0
    
    for role in test_roles:
        try:
            print(f"\n{role} テスト:")
            
            # クライアント取得
            client = promptsmith_llm_manager.get_ai_client(role)
            print(f"  クライアント取得: ✅ {type(client).__name__}")
            
            # 簡単なチャット実行（APIキーが有効な場合のみ）
            role_info = promptsmith_llm_manager.get_role_info(role)
            if role_info['has_api_key']:
                response = promptsmith_llm_manager.chat_with_role(
                    role, 
                    "こんにちは、テストメッセージです。'OK'と1単語で返答してください。"
                )
                print(f"  チャット実行: ✅ '{response[:50]}...' ({len(response)}文字)")
                successful_tests += 1
            else:
                print(f"  チャット実行: ⚠️  APIキーなし（スキップ）")
                # APIキーがない場合でもクライアント取得が成功していればカウント
                successful_tests += 1
                
        except Exception as e:
            print(f"  エラー: ❌ {e}")
    
    # 全役割でクライアント取得が成功していれば成功とみなす
    return successful_tests == len(test_roles)


def test_tester_ai_integration():
    """TesterAI統合テスト"""
    print("\n=== TesterAI統合テスト ===")
    
    try:
        # TesterAIインスタンスを作成
        tester = TesterAI()
        print("✅ TesterAI初期化成功")
        
        # 基本シナリオ生成
        scenario = tester.generate_challenging_scenario(difficulty="medium")
        print(f"✅ 基本シナリオ生成成功: {scenario.name}")
        
        # AI役割情報が利用可能かチェック
        role_info = promptsmith_llm_manager.get_role_info("tester_ai")
        if role_info['has_api_key']:
            print("✅ TesterAI用APIキー利用可能")
            
            # AIパワードシナリオ生成テスト
            try:
                ai_scenario = tester.generate_ai_powered_scenario(
                    context="Pythonウェブアプリケーション開発プロジェクト",
                    difficulty="medium"
                )
                print(f"✅ AI生成シナリオ成功: {ai_scenario.name}")
                print(f"   ユーザー要求: {ai_scenario.user_request[:100]}...")
                
            except Exception as e:
                print(f"⚠️  AI生成シナリオエラー: {e}")
        else:
            print("⚠️  TesterAI用APIキーなし（AI生成機能はスキップ）")
        
        return True
        
    except Exception as e:
        print(f"❌ TesterAI統合エラー: {e}")
        return False


def test_environment_variables():
    """環境変数テスト"""
    print("\n=== 環境変数テスト ===")
    
    api_keys = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY", 
        "GROQ_API_KEY",
        "GOOGLE_AI_API_KEY",
        "OPENROUTER_API_KEY"
    ]
    
    set_count = 0
    for key in api_keys:
        value = os.getenv(key)
        if value:
            masked = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***"
            print(f"  {key}: ✅ 設定済み ({masked})")
            set_count += 1
        else:
            print(f"  {key}: ⚠️  未設定")
    
    print(f"\nAPIキー設定状況: {set_count}/{len(api_keys)} 設定済み")
    # 少なくとも1つのAPIキーが設定されていれば成功とみなす
    return set_count > 0


def main():
    """メインテスト実行"""
    print("PromptSmith AI設定システム テスト開始")
    print("=" * 50)
    
    # 各テストを実行
    tests = [
        ("設定読み込み", test_config_loading),
        ("環境変数", test_environment_variables), 
        ("LLM管理システム", test_llm_manager),
        ("AI役割別クライアント", test_ai_role_clients),
        ("TesterAI統合", test_tester_ai_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}テストで予期しないエラー: {e}")
            results.append((test_name, False))
    
    # 結果サマリー
    print("\n" + "=" * 50)
    print("テスト結果サマリー:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n総合結果: {passed}/{len(results)} テスト合格")
    
    if passed == len(results):
        print("🎉 すべてのテストが成功しました！")
        return 0
    else:
        print("⚠️  一部のテストが失敗しました。設定を確認してください。")
        return 1


if __name__ == "__main__":
    sys.exit(main())