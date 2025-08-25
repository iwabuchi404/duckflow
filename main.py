#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Duckflow エントリーポイント
4ノード統合アーキテクチャ
"""
import sys
import os

# プロジェクトルートパス追加
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 文字コード設定の一元化されたモジュールをインポート
from companion.config.encoding_config import setup_encoding_once

# メインエントリーポイントでの環境変数設定を実行
setup_encoding_once()

if __name__ == "__main__":
    try:
        from codecrafter.main_v2 import main
        
        print("🦆 Duckflow v0.3.0-alpha - 4ノードAIコーディングエージェント")
        print("🎯 統合アーキテクチャによる高効率AI開発支援")
        print("🔄 4つのノード: 理解→収集→実行→評価")
        print()
        
        main()
        
    except ImportError as e:
        print(f"❌ インポートエラー: {e}")
        print("依存関係をインストール: uv sync")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 実行エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)