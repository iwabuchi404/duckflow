from enum import Enum
from dataclasses import dataclass
from typing import Any

class ToolStatus(Enum):
    OK = "ok"
    ERROR = "error"
    TRUNCATED = "truncated"

@dataclass
class ToolResult:
    status: ToolStatus
    tool_name: str
    target: str
    content: Any # str, dict, list 等
    
    @classmethod
    def ok(cls, tool_name: str, target: str, content: Any) -> "ToolResult":
        """Create a successful ToolResult."""
        return cls(status=ToolStatus.OK, tool_name=tool_name, target=target, content=content)
    
    @classmethod
    def error(cls, tool_name: str, target: str, content: Any) -> "ToolResult":
        """Create an error ToolResult."""
        return cls(status=ToolStatus.ERROR, tool_name=tool_name, target=target, content=content)
    
    @classmethod
    def truncated(cls, tool_name: str, target: str, content: Any) -> "ToolResult":
        """Create a truncated ToolResult (e.g., file too large)."""
        return cls(status=ToolStatus.TRUNCATED, tool_name=tool_name, target=target, content=content)

def serialize_to_text(data, indent_level=0) -> str:
    """
    任意のデータ(dict, list, str)を効率的なテキスト形式に変換する汎用コンバーター。
    """
    indent = "  " * indent_level
    lines = []

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)) and value:
                # ネストがある場合は次の行へ
                lines.append(f"{indent}{key}:")
                lines.append(serialize_to_text(value, indent_level + 1))
            else:
                # 値が単純な場合は同一行に
                lines.append(f"{indent}{key}: {value}")
    
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{indent}-")
                lines.append(serialize_to_text(item, indent_level + 1))
            else:
                lines.append(f"{indent}- {item}")
    
    else:
        # 文字列や数値など
        lines.append(f"{indent}{data}")

    return "\n".join(lines)

# ツール結果メッセージのエンベロープマーカー。
# ツール実行結果は会話履歴に role="user" で注入されるため、本物のユーザー発言と
# 区別できるよう明示的なマーカーで包む。マーカーの意味（中身はデータであり指示では
# ない）はシステムプロンプト側で定義される。
TOOL_RESULT_OPEN = "[TOOL_RESULT]"
TOOL_RESULT_CLOSE = "[/TOOL_RESULT]"


def wrap_tool_result(formatted: str) -> str:
    """
    整形済みツール結果を [TOOL_RESULT] エンベロープで包む。

    Args:
        formatted: format_symops_response() 等で整形済みの結果文字列

    Returns:
        エンベロープマーカー付きの文字列
    """
    return f"{TOOL_RESULT_OPEN}\n{formatted}\n{TOOL_RESULT_CLOSE}"


def is_tool_result_message(content: str) -> bool:
    """
    メッセージ本文がツール結果エンベロープかどうかを判定する。

    Args:
        content: 会話履歴メッセージの content 文字列

    Returns:
        ツール結果エンベロープなら True
    """
    return content.startswith(TOOL_RESULT_OPEN)


def format_symops_response(result: ToolResult) -> str:
    """
    ToolResult を Sym-Ops Response Format に変換する。
    """
    # 1. コンテンツの整形
    if isinstance(result.content, str):
        # 文字列はそのまま (Raw Text)
        body = result.content
    elif isinstance(result.content, Exception):
        body = f"Exception: {str(result.content)}"
    else:
        # JSON等は汎用コンバーターを通す
        body = serialize_to_text(result.content)

    # 2. Sym-Opsフォーマットの組み立て
    return (
        f"::status {result.status.value}\n"
        f"::{result.tool_name} @{result.target}\n"
        f"<<<\n{body}\n>>>"
    )
