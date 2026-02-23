"""
セッション永続化モジュール。

会話履歴・エージェント状態をターンごとに自動保存し、
再起動後に前回セッションを復元する機能を提供する。

保存先: logs/sessions/{session_id}.json
インデックス: logs/sessions/index.json
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from companion.state.agent_state import AgentState

logger = logging.getLogger(__name__)


class SessionManager:
    """
    セッションの保存・読み込み・一覧管理を担当するクラス。

    保存形式:
        logs/sessions/{session_id}.json  ← AgentState 全体
        logs/sessions/index.json         ← セッション一覧メタデータ

    使用例:
        sm = SessionManager()
        sm.save(state)                   # ターン完了後に保存
        state = sm.load_latest()         # 最新セッションを復元
    """

    def __init__(self, session_dir: str = "logs/sessions") -> None:
        """
        Args:
            session_dir: セッションファイルの保存先ディレクトリ
        """
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.session_dir / "index.json"

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------

    def save(self, state: AgentState) -> None:
        """
        AgentState をJSONファイルに保存し、インデックスを更新する。
        ターン完了後に毎回呼ぶこと（上書き保存）。

        Args:
            state: 保存するエージェント状態
        """
        session_file = self.session_dir / f"{state.session_id}.json"
        try:
            data = state.to_session_dict()
            session_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            self._update_index(state)
            logger.debug(f"Session saved: {state.session_id} (turn={state.turn_count})")
        except Exception as e:
            # 保存エラーはログのみ（エージェント動作は止めない）
            logger.error(f"Failed to save session {state.session_id}: {e}")

    # ------------------------------------------------------------------
    # 読み込み
    # ------------------------------------------------------------------

    def load(self, session_id: str) -> Optional[AgentState]:
        """
        指定された session_id のセッションを AgentState として復元する。

        Args:
            session_id: 復元するセッションのID

        Returns:
            復元された AgentState。ファイルが存在しない場合は None。
        """
        session_file = self.session_dir / f"{session_id}.json"
        if not session_file.exists():
            logger.warning(f"Session file not found: {session_file}")
            return None
        try:
            data = json.loads(session_file.read_text(encoding='utf-8'))
            state = AgentState.from_session_dict(data)
            logger.info(
                f"Session loaded: {session_id} "
                f"({len(state.conversation_history)} messages, "
                f"turn={state.turn_count})"
            )
            return state
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None

    def load_latest(self) -> Optional[AgentState]:
        """
        最新セッションを AgentState として復元する。

        Returns:
            復元された AgentState。セッションが存在しない場合は None。
        """
        latest_id = self.get_latest_id()
        if not latest_id:
            return None
        return self.load(latest_id)

    # ------------------------------------------------------------------
    # 一覧・メタデータ
    # ------------------------------------------------------------------

    def list_sessions(self) -> List[dict]:
        """
        セッション一覧をメタデータで返す（最新順）。

        Returns:
            各セッションの辞書リスト。
            各要素: {session_id, created_at, last_active, turn_count}
        """
        index = self._read_index()
        return list(reversed(index.get("sessions", [])))

    def get_latest_id(self) -> Optional[str]:
        """
        最新セッションのIDを返す。存在しなければ None。

        Returns:
            session_id 文字列、またはセッションが無ければ None
        """
        index = self._read_index()
        return index.get("latest")

    # ------------------------------------------------------------------
    # 内部ヘルパー
    # ------------------------------------------------------------------

    def _update_index(self, state: AgentState) -> None:
        """
        index.json を更新する。session_id が既存なら上書き、新規なら追加。

        Args:
            state: 保存済みの AgentState
        """
        index = self._read_index()
        sessions: List[dict] = index.get("sessions", [])

        meta = {
            "session_id": state.session_id,
            "created_at": state.created_at.isoformat(),
            "last_active": state.last_active.isoformat(),
            "turn_count": state.turn_count,
        }

        # 既存エントリを更新 or 追加
        existing_ids = [s["session_id"] for s in sessions]
        if state.session_id in existing_ids:
            idx = existing_ids.index(state.session_id)
            sessions[idx] = meta
        else:
            sessions.append(meta)

        index["sessions"] = sessions
        index["latest"] = state.session_id

        try:
            self.index_path.write_text(
                json.dumps(index, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        except Exception as e:
            logger.error(f"Failed to update session index: {e}")

    def _read_index(self) -> dict:
        """
        index.json を読み込む。存在しなければ空のインデックスを返す。

        Returns:
            インデックス辞書 {"sessions": [...], "latest": "..."}
        """
        if not self.index_path.exists():
            return {"sessions": [], "latest": None}
        try:
            return json.loads(self.index_path.read_text(encoding='utf-8'))
        except Exception as e:
            logger.error(f"Failed to read session index: {e}")
            return {"sessions": [], "latest": None}
