#!/usr/bin/env python3
"""
Duckflow v0.2.1-alpha テスト用エントリーポイント
ステップ2b（RAG機能）対応版のテスト起動スクリプト
"""
import sys
import os

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 文字エンコーディング問題回避のため環境変数を設定
os.environ['PYTHONIOENCODING'] = 'utf-8'

try:
    from codecrafter.main_v2 import main
    
    if __name__ == "__main__":
        print("🚀 Starting Duckflow v0.2.1-alpha (Step 2b - RAG enabled)")
        print("📚 New features: Project-wide code search, RAG-enhanced prompts")
        print("⚡ Commands: index, search, index-status, graph")
        print()
        main()
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please ensure all dependencies are installed with: uv sync")
    sys.exit(1)
except Exception as e:
    print(f"❌ Startup error: {e}")
    sys.exit(1)