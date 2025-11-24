#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Duckflow メインエントリー
4ノード統合オーケストレーター
"""
import sys
import os

# プロジェクトルートを追加
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from codecrafter.main import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Duckflowを終了します")
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()