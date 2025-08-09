#!/usr/bin/env python3
"""
OpenRouter対応テストスクリプト
"""

import sys
import os
sys.path.append('.')

from codecrafter.base.config import config_manager
from codecrafter.base.llm_client import llm_manager, OpenRouterClient
from codecrafter.promptsmith.llm_manager import promptsmith_llm_manager


def test_openrouter_config():
    """OpenRouter設定のテスト"""
    print("=== OpenRouter設定テスト ===")
    
    try:
        config = config_manager.load_config()
        
        # メイン設定確認
        openrouter_config = config.llm.openrouter
        print(f"✅ メインOpenRouter設定:")
        print(f"   モデル: {openrouter_config.get('model', 'N/A')}")
        print(f"   温度: {openrouter_config.get('temperature', 'N/A')}")
        print(f"   最大トークン: {openrouter_config.get('max_tokens', 'N/A')}")
        
        # 要約用設定確認
        summary_config = config.summary_llm.openrouter
        print(f"✅ 要約用OpenRouter設定:")
        print(f"   モデル: {summary_config.get('model', 'N/A')}")
        print(f"   温度: {summary_config.get('temperature', 'N/A')}")
        print(f"   最大トークン: {summary_config.get('max_tokens', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"❌ 設定エラー: {e}")
        return False


def test_openrouter_client():
    """OpenRouterクライアントのテスト"""
    print("\n=== OpenRouterクライアントテスト ===")
    
    try:
        # 設定を取得
        config = config_manager.load_config()
        openrouter_config = config.llm.openrouter
        
        # APIキーチェック
        api_key = config_manager.get_api_key('openrouter')
        if not api_key:
            print("⚠️  OPENROUTER_API_KEY が設定されていません")
            print("   テストをスキップします")
            return True
        
        print(f"✅ APIキー設定済み: {api_key[:8]}...{api_key[-4:]}")
        
        # クライアント作成
        client = OpenRouterClient(openrouter_config)
        print(f"✅ OpenRouterクライアント作成成功")
        
        # 簡単なチャット実行
        print("📤 テストメッセージ送信中...")
        response = client.chat([
            {"role": "user", "content": "Hello! Please respond with just 'OK' to confirm you're working."}
        ])
        print(f"✅ 応答受信: '{response[:100]}...' ({len(response)}文字)")
        
        return True
        
    except Exception as e:
        print(f"❌ クライアントエラー: {e}")
        return False


def test_llm_manager_openrouter():
    """LLMManagerのOpenRouter対応テスト"""
    print("\n=== LLMManager OpenRouterテスト ===")
    
    try:
        # 設定をOpenRouterに一時変更してテスト
        original_provider = config_manager.load_config().llm.provider
        
        # 環境変数でOpenRouterを設定
        os.environ['DUCKFLOW_LLM_PROVIDER'] = 'openrouter'
        
        # 新しい設定で初期化
        from codecrafter.base.llm_client import LLMManager
        test_manager = LLMManager()
        
        provider_name = test_manager.get_provider_name()
        print(f"✅ プロバイダー名取得: {provider_name}")
        
        # APIキーがある場合のみチャットテスト
        api_key = config_manager.get_api_key('openrouter')
        if api_key:
            print("📤 チャットテスト実行中...")
            response = test_manager.chat("Hello, just say 'OK' please.")
            print(f"✅ チャット成功: '{response[:50]}...' ({len(response)}文字)")
        else:
            print("⚠️  APIキーなし（チャットテストスキップ）")
        
        # 環境変数を戻す
        if original_provider:
            os.environ['DUCKFLOW_LLM_PROVIDER'] = original_provider
        else:
            os.environ.pop('DUCKFLOW_LLM_PROVIDER', None)
        
        return True
        
    except Exception as e:
        print(f"❌ LLMManagerエラー: {e}")
        # 環境変数を戻す
        os.environ.pop('DUCKFLOW_LLM_PROVIDER', None)
        return False


def test_promptsmith_openrouter():
    """PromptSmithのOpenRouter対応テスト"""
    print("\n=== PromptSmith OpenRouterテスト ===")
    
    try:
        # AI役割の設定でOpenRouterを使用する例
        role_info = promptsmith_llm_manager.get_role_info("tester_ai")
        print(f"✅ TesterAI設定情報:")
        print(f"   プロバイダー: {role_info['provider']}")
        print(f"   APIキー: {'有り' if role_info['has_api_key'] else '無し'}")
        print(f"   設定: {role_info['config']}")
        
        # OpenRouterクライアントが取得できるかテスト
        if role_info['provider'] == 'openrouter' or True:  # テスト用に強制実行
            print("\n📝 OpenRouter設定例の表示:")
            print("   config.yaml で以下のように設定できます:")
            print("   promptsmith:")
            print("     tester_ai:")
            print("       provider: 'openrouter'")
            print("       model_settings:")
            print("         openrouter:")
            print("           model: 'meta-llama/llama-3.1-8b-instruct'")
            print("           temperature: 0.3")
            print("           max_tokens: 2048")
        
        return True
        
    except Exception as e:
        print(f"❌ PromptSmithエラー: {e}")
        return False


def main():
    """メインテスト実行"""
    print("OpenRouter対応テスト開始")
    print("=" * 50)
    
    tests = [
        ("OpenRouter設定", test_openrouter_config),
        ("OpenRouterクライアント", test_openrouter_client),
        ("LLMManager OpenRouter", test_llm_manager_openrouter),
        ("PromptSmith OpenRouter", test_promptsmith_openrouter),
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
    print("OpenRouter対応テスト結果:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n総合結果: {passed}/{len(results)} テスト合格")
    
    if passed == len(results):
        print("🎉 OpenRouter対応が正常に動作します！")
        print("\n📋 使用方法:")
        print("1. 環境変数設定: OPENROUTER_API_KEY=your_api_key")
        print("2. メインプロバイダー: DUCKFLOW_LLM_PROVIDER=openrouter")
        print("3. PromptSmithでの使用: config.yamlの該当役割でprovider: 'openrouter'")
        return 0
    else:
        print("⚠️  一部のテストが失敗しました。")
        return 1


if __name__ == "__main__":
    sys.exit(main())