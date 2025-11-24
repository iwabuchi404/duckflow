#!/usr/bin/env python3
"""
Dual-Loop System デバッグ用スクリプト（V4アーキテクチャ対応）

TICKET-DUCKFLOW-V4-004対応:
- EnhancedCompanionCoreV8とAgentStateをセッション開始時に一度だけ初期化
- 会話履歴の永続化を確保
"""

import sys
import time
import asyncio
import uuid
import logging
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from companion.enhanced_core_v8 import EnhancedCompanionCoreV8
    from companion.state.agent_state import AgentState
except ImportError as e:
    print(f"❌ インポートエラー: {e}")
    sys.exit(1)


class MockDualLoopSystem:
    """デバッグ用のモックDualLoopSystem"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.agent_state = AgentState()
        self.llm_call_manager = None
        self.llm_service = None
        self.intent_analyzer = None
        self.prompt_context_service = None
        self.task_queue = None
        
        # ログ設定
        logging.basicConfig(
            level=logging.INFO,
            format=f'[{session_id}] %(levelname)s: %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"MockDualLoopSystem初期化完了: {session_id}")


async def main():
    """メイン関数（修正版：ライフサイクル問題を解決）"""
    session_id = f"debug_session_{uuid.uuid4().hex[:8]}"
    print(f"--- 新しいデバッグセッションを開始: {session_id} ---")
    
    # 修正: インスタンスを一度だけ作成（ループの外）
    dual_loop = MockDualLoopSystem(session_id)
    core = EnhancedCompanionCoreV8(dual_loop)
    
    print("✅ EnhancedCompanionCoreV8とAgentStateを初期化しました")
    print("💡 会話履歴はセッション中に永続化されます")
    print("💡 'exit' または 'quit' で終了できます")
    print("=" * 60)
    
    while True:
        try:
            user_message = input("👤 > ")
            if user_message.lower() in ["exit", "quit"]:
                print("👋 セッションを終了します")
                break
            
            if not user_message.strip():
                continue
            
            print(f"🔄 処理中...")
            
            # 修正: 既存のcoreインスタンスを再利用
            response = await core.process_user_message(user_message)
            print(f"🤖 < {response}")
            print("-" * 40)
            
        except KeyboardInterrupt:
            print("\n👋 セッションを終了します")
            break
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
            print("-" * 40)


if __name__ == "__main__":
    asyncio.run(main())