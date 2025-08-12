#!/usr/bin/env python3
"""
Duckflow v0.3.0-alpha 標準エントリーポイント
4ノード統合アーキテクチャ対応版
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
        print("🚀 Starting Duckflow v0.3.0-alpha (4-Node Architecture)")
        print("🧠 Revolutionary: Information transmission loss problem solved")
        print("⚡ 4-Node Flow: Understanding → Gathering → Execution → Evaluation")
        print()
        main()
        
except ImportError as e:
    print(f"[ERROR] Import error: {e}")
    print("Please ensure all dependencies are installed with: uv sync")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Startup error: {e}")
    sys.exit(1)