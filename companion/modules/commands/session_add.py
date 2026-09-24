from typing import Protocol, cast


class SessionManagerLike(Protocol):
    """Session manager operations required by the session-add command."""

    def create_session(self) -> str:
        """Create and return a new session identifier.

        Returns:
            The newly created session identifier.
        """
        ...


async def handle_session_add(args: list[str], **kwargs: object) -> dict[str, str]:
    """
    /session add コマンドのハンドラ

    機能:
    - 新規セッションを追加する
    - セッションIDを自動生成して返す

    使用例:
    /session add
    """
    session_manager_value = kwargs.get("session_manager")
    if not session_manager_value:
        return {"status": "error", "message": "セッションマネージャーが利用できません"}

    # 新規セッション作成
    session_manager = cast(SessionManagerLike, session_manager_value)
    session_id = session_manager.create_session()
    return {
        "status": "success",
        "message": f"セッションを追加しました: {session_id}",
        "session_id": session_id,
    }
