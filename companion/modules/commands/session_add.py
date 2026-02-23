from typing import Dict, List
from companion.modules.session_manager import SessionManager

async def handle_session_add(args: List[str], **kwargs) -> Dict:
    """
    /session add コマンドのハンドラ
    
    機能:
    - 新規セッションを追加する
    - セッションIDを自動生成して返す
    
    使用例:
    /session add
    """
    session_manager = kwargs.get("session_manager")
    if not session_manager:
        return {
            "status": "error",
            "message": "セッションマネージャーが利用できません"
        }
    
    # 新規セッション作成
    session_id = session_manager.create_session()
    return {
        "status": "success",
        "message": f"セッションを追加しました: {session_id}",
        "session_id": session_id
    }