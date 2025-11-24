#!/usr/bin/env python
"""
Groq API エラーハンドリングのデバッグスクリプト
詳細なエラー情報を取得するためのテスト
"""

import os
import logging
import json
from typing import Dict, Any, List
from pathlib import Path

# ログレベルを最も詳細に設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 特定のライブラリのログレベルを設定
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("groq").setLevel(logging.DEBUG)
logging.getLogger("langchain").setLevel(logging.DEBUG)
logging.getLogger("langchain_groq").setLevel(logging.DEBUG)

# 環境変数の読み込み
from dotenv import load_dotenv
load_dotenv()

try:
    from langchain_groq import ChatGroq
    from langchain.schema import HumanMessage, SystemMessage
    GROQ_AVAILABLE = True
except ImportError as e:
    print(f"❌ LangChain Groq not available: {e}")
    GROQ_AVAILABLE = False


def test_groq_with_invalid_model():
    """無効なモデル名でGroq APIをテストし、詳細なエラー情報を取得"""
    
    if not GROQ_AVAILABLE:
        print("❌ Groq client not available")
        return
    
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        print("❌ GROQ_API_KEY not found in environment")
        return
    
    print("🔍 Groq APIの詳細エラー情報を調査中...")
    
    # 無効なモデル名でテスト
    invalid_model = "invalid-model-name-for-testing"
    
    try:
        print(f"📋 テスト設定:")
        print(f"   モデル: {invalid_model}")
        print(f"   API Key: {'*' * (len(api_key) - 4) + api_key[-4:]}")
        
        client = ChatGroq(
            model=invalid_model,  # 意図的に無効なモデル名
            temperature=0.1,
            max_tokens=100,
            groq_api_key=api_key,
        )
        
        messages = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="Hello, test message")
        ]
        
        print("\n📤 Groq APIにリクエストを送信中...")
        response = client.invoke(messages)
        
        print(f"✅ 予期しない成功: {response.content}")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました:")
        print(f"   エラータイプ: {type(e).__name__}")
        print(f"   エラーメッセージ: {str(e)}")
        
        # より詳細な情報を取得
        if hasattr(e, 'response'):
            print(f"\n📋 HTTPレスポンス詳細:")
            print(f"   ステータスコード: {getattr(e.response, 'status_code', 'N/A')}")
            print(f"   レスポンスヘッダー: {getattr(e.response, 'headers', 'N/A')}")
            
            if hasattr(e.response, 'text'):
                print(f"   レスポンスボディ: {e.response.text}")
            elif hasattr(e.response, 'content'):
                print(f"   レスポンスコンテンツ: {e.response.content}")
        
        # 詳細なスタックトレースを表示
        import traceback
        print(f"\n📜 詳細なスタックトレース:")
        traceback.print_exc()
        
        # 属性の詳細調査
        print(f"\n🔍 例外オブジェクトの属性:")
        for attr in dir(e):
            if not attr.startswith('_'):
                try:
                    value = getattr(e, attr)
                    if not callable(value):
                        print(f"   {attr}: {value}")
                except:
                    print(f"   {attr}: <アクセス不可>")


def test_groq_with_large_content():
    """大きすぎるコンテンツでGroq APIをテストし、詳細なエラー情報を取得"""
    
    if not GROQ_AVAILABLE:
        print("❌ Groq client not available")
        return
    
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        print("❌ GROQ_API_KEY not found in environment")
        return
    
    print("\n🔍 大きなコンテンツでのGroq APIエラー調査...")
    
    try:
        client = ChatGroq(
            model="llama-3.1-8b-instant",  # 有効なモデル名
            temperature=0.1,
            max_tokens=100,
            groq_api_key=api_key,
        )
        
        # 意図的に大きすぎるコンテンツを作成
        large_content = "This is a test message. " * 5000  # 非常に大きなメッセージ
        
        messages = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content=large_content)
        ]
        
        print(f"📋 大きなコンテンツテスト設定:")
        print(f"   コンテンツサイズ: {len(large_content)} 文字")
        
        print("\n📤 大きなコンテンツでGroq APIにリクエスト送信中...")
        response = client.invoke(messages)
        
        print(f"✅ 予期しない成功: {response.content[:100]}...")
        
    except Exception as e:
        print(f"\n❌ 大きなコンテンツでエラーが発生:")
        print(f"   エラータイプ: {type(e).__name__}")
        print(f"   エラーメッセージ: {str(e)}")
        
        # より詳細な情報を取得
        if hasattr(e, 'response'):
            print(f"\n📋 HTTPレスポンス詳細:")
            print(f"   ステータスコード: {getattr(e.response, 'status_code', 'N/A')}")
            
            if hasattr(e.response, 'text'):
                print(f"   レスポンスボディ: {e.response.text}")


def test_groq_with_empty_api_key():
    """空のAPIキーでテスト"""
    
    if not GROQ_AVAILABLE:
        print("❌ Groq client not available")
        return
    
    print("\n🔍 空のAPIキーでのGroq APIエラー調査...")
    
    try:
        client = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0.1,
            max_tokens=100,
            groq_api_key="",  # 空のAPIキー
        )
        
        messages = [HumanMessage(content="Hello")]
        
        print("\n📤 空のAPIキーでGroq APIにリクエスト送信中...")
        response = client.invoke(messages)
        
        print(f"✅ 予期しない成功: {response.content}")
        
    except Exception as e:
        print(f"\n❌ 空のAPIキーでエラーが発生:")
        print(f"   エラータイプ: {type(e).__name__}")
        print(f"   エラーメッセージ: {str(e)}")
        
        # APIエラーの詳細を調査
        if hasattr(e, 'response'):
            print(f"\n📋 HTTPレスポンス詳細:")
            print(f"   ステータスコード: {getattr(e.response, 'status_code', 'N/A')}")
            
            if hasattr(e.response, 'text'):
                print(f"   レスポンスボディ: {e.response.text}")


if __name__ == "__main__":
    print("🧪 Groq API エラーハンドリング詳細調査")
    print("=" * 50)
    
    # 各種エラーパターンをテスト
    test_groq_with_invalid_model()
    test_groq_with_large_content()
    test_groq_with_empty_api_key()
    
    print("\n" + "=" * 50)
    print("✅ 詳細調査完了")