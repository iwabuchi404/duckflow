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
