#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
エンドツーエンド動作確認テスト（簡易版）
game_doc.md読み込み → LLM分析 → 応答のフローをテスト
"""

import sys
import os
import logging
sys.path.insert(0, os.path.dirname(__file__))

# ログレベル設定
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

async def test_e2e_simple():
    """簡単なエンドツーエンドテスト"""
    print("E2E 動作確認テスト開始")
    
    try:
        # 個別のコンポーネントをテスト
        from companion.state.agent_state import AgentState, Action
        from companion.enhanced_core import EnhancedCompanionCoreV7
        
        # モックのdual_loop_systemを作成
        class MockDualLoopSystem:
            def __init__(self):
                self.agent_state = AgentState(session_id="test_e2e")
                # 他の必要な属性を追加
                
        mock_system = MockDualLoopSystem()
        
        # EnhancedCompanionCoreを初期化
        print("コアシステム初期化中...")
        core = EnhancedCompanionCoreV7(mock_system)
        
        # game_doc.mdが存在するかチェック
        import os
        if not os.path.exists("game_doc.md"):
            print("game_doc.mdが見つかりません。テストファイルを作成します...")
            with open("game_doc.md", "w", encoding="utf-8") as f:
                f.write("""# ゲーム設計ドキュメント

## 概要
これはシンプルなRPGゲームです。

## 主要機能
- キャラクター管理
- バトルシステム
- アイテム管理
- レベルシステム

## 技術仕様
- Python 3.10+
- SQLite データベース
- Pygame UI

## 実装計画
1. データモデルの設計
2. キャラクタークラスの実装
3. バトルシステムの実装
4. UIの実装
""")
            print("テスト用game_doc.mdを作成しました")
        
        # テスト用のActionListを作成
        print("テスト用ActionList実行中...")
        action_list = [
            Action(
                operation="file_ops.read_file",
                args={"file_path": "game_doc.md"},
                reasoning="ゲーム設計文書を読み込み"
            ),
            Action(
                operation="response.echo",
                args={"message": "ファイル読み込み完了: {{@act_000_file_ops_read_file}}"},
                reasoning="ファイル内容を確認"
            )
        ]
        
        # ActionList実行
        results = await core._dispatch_action_list(action_list)
        
        print("実行結果:")
        for i, result in enumerate(results):
            print(f"  Action {i}: {str(result)[:150]}...")
        
        # AgentStateのActionResult確認
        action_results = core.agent_state.short_term_memory.get('action_results', [])
        print(f"保存されたActionResult数: {len(action_results)}")
        
        for ar in action_results:
            print(f"  {ar['action_id']} ({ar['operation']}) - {ar['timestamp']}")
        
        # ファイル内容がAgentStateに保存されているかチェック
        file_contents = core.agent_state.get_file_contents()
        print(f"AgentStateに保存されたファイル数: {len(file_contents)}")
        
        for file_path, content in file_contents.items():
            print(f"  {file_path}: {len(content)}文字")
        
        print("E2E テスト完了")
        return True
        
    except Exception as e:
        print(f"E2Eテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(test_e2e_simple())
    if success:
        print("✅ E2Eテスト成功")
    else:
        print("❌ E2Eテスト失敗")