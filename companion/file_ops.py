"""
SimpleFileOps - シンプルなファイル操作
Phase 1.5: 基本的なファイル操作機能

設計思想:
- 複雑な機能を排除し、基本的な操作のみ
- エラーメッセージは自然で分かりやすく
- 相棒らしい対話的な操作
"""

import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime
from dataclasses import dataclass, field
import hashlib
import uuid
import asyncio

from .ui import rich_ui
from .config.config_manager import ConfigManager
from companion.security.file_protector import FileProtector

# 新しいシンプル承認システム
from .simple_approval import SimpleApprovalGate, ApprovalRequest, RiskLevel, ApprovalResult, ApprovalMode


class FileOperationError(Exception):
    """ファイル操作エラー"""
    pass


@dataclass
class FileOpOutcome:
    """ファイル操作の結果（V2 仕様）"""
    ok: bool
    op: Literal["create", "write", "read", "delete", "mkdir", "move", "copy"]
    path: str
    reason: Optional[str] = None
    before_hash: Optional[str] = None
    after_hash: Optional[str] = None
    changed: bool = False
    content: Optional[str] = None


class SimpleFileOps:
    """シンプルなファイル操作クラス"""
    
    def __init__(self, approval_mode: ApprovalMode = ApprovalMode.STANDARD, llm_enabled: bool = True):
        """初期化
        
        Args:
            approval_mode: 承認モード
            llm_enabled: LLM強化承認を有効にするか
        """
        self.current_directory = Path.cwd()
        self.approval_gate = SimpleApprovalGate(mode_override=approval_mode, llm_enabled=llm_enabled)
        self.llm_enabled = llm_enabled
        try:
            import os as _os
            from .config.config_manager import ConfigManager as _CM
            self.debug = _os.getenv("FILE_OPS_DEBUG") == "1" or _CM().is_debug_mode()
        except Exception:
            self.debug = False
        # Phase 1: initialize FileProtector from config
        try:
            cm = ConfigManager()
            cfg = cm.load_config()
            p1 = getattr(cfg, 'phase1', None)
            work_dir = p1.get('work_dir') if isinstance(p1, dict) else '.'
            safe_ext = p1.get('safe_extensions', [".txt", ".md", ".py", ".json", ".yaml", ".yml", ".csv"]) if isinstance(p1, dict) else [".txt", ".md", ".py", ".json", ".yaml", ".yml", ".csv"]
            from pathlib import Path as _Path
            base = _Path.cwd() if work_dir == "." else _Path(work_dir)
            self.file_protector = FileProtector(str(base.resolve()), safe_ext)
        except Exception:
            # Fail-safe default: repo root
            from pathlib import Path as _Path
            self.file_protector = FileProtector(str(_Path.cwd().resolve()), [".txt", ".md", ".py", ".json", ".yaml", ".yml", ".csv"])

    def _assess_write_risk(self, file_path: str) -> RiskLevel:
        """書き込みリスク評価"""
        if file_path.startswith('.') or 'config' in file_path.lower():
            return RiskLevel.HIGH
        elif file_path.endswith(('.py', '.js', '.ts', '.sh', '.bat')):
            return RiskLevel.MEDIUM
        elif file_path.endswith(('.txt', '.md', '.json', '.yaml', '.yml')):
            return RiskLevel.LOW
        else:
            return RiskLevel.MEDIUM

    def write_file_with_approval(self, file_path: str, content: str) -> FileOpOutcome:
        """承認付きファイル書き込み"""
        # Phase 1 safety: allow writes only inside work_dir and safe extensions
        if not self.file_protector.check_operation("write", file_path):
            return FileOpOutcome(
                ok=False,
                op="write",
                path=file_path,
                reason="安全ポリシーによりブロックされました（作業フォルダ外または拡張子が安全でない）"
            )
        request = ApprovalRequest(
            operation="ファイル書き込み",
            description=f"ファイル '{file_path}' に内容を書き込みます",
            target=file_path,
            risk_level=self._assess_write_risk(file_path),
            details=f"サイズ: {len(content)}文字\n内容プレビュー:\n{content[:200]}{'...' if len(content) > 200 else ''}"
        )
        
        approval = self.approval_gate.request_approval(request)
        
        if not approval.approved:
            return FileOpOutcome(
                ok=False,
                op="write",
                path=file_path,
                reason=f"ユーザーによる拒否: {approval.reason}"
            )
        
        path = Path(file_path)
        before_hash = self._hash_file_if_exists(path)
        try:
            if not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            after_hash = self._hash_file_if_exists(path)
            return FileOpOutcome(
                ok=True,
                op="write",
                path=str(path),
                before_hash=before_hash,
                after_hash=after_hash,
                changed=(before_hash != after_hash)
            )
        except Exception as e:
            return FileOpOutcome(ok=False, op="write", path=str(path), reason=str(e))
    
    async def write_file_with_llm_approval(self, file_path: str, content: str) -> FileOpOutcome:
        """LLM強化承認付きファイル書き込み"""
        # Phase 1 safety gate
        if not self.file_protector.check_operation("write", file_path):
            return FileOpOutcome(
                ok=False,
                op="write",
                path=file_path,
                reason="安全ポリシーによりブロックされました（作業フォルダ外または拡張子が安全でない）"
            )
        request = ApprovalRequest(
            operation="ファイル書き込み",
            description=f"ファイル '{file_path}' に内容を書き込みます",
            target=file_path,
            risk_level=self._assess_write_risk(file_path),
            details=f"サイズ: {len(content)}文字\n内容プレビュー:\n{content[:200]}{'...' if len(content) > 200 else ''}"
        )
        
        # LLM強化承認を使用
        if self.llm_enabled and hasattr(self.approval_gate, 'request_approval_llm_enhanced'):
            approval = await self.approval_gate.request_approval_llm_enhanced(request)
        else:
            # フォールバック: 標準承認
            approval = self.approval_gate.request_approval(request)
        
        if not approval.approved:
            return FileOpOutcome(
                ok=False,
                op="write",
                path=file_path,
                reason=f"ユーザーによる拒否: {approval.reason}"
            )
        
        path = Path(file_path)
        before_hash = self._hash_file_if_exists(path)
        try:
            if not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            after_hash = self._hash_file_if_exists(path)
            return FileOpOutcome(
                ok=True,
                op="write",
                path=str(path),
                before_hash=before_hash,
                after_hash=after_hash,
                changed=(before_hash != after_hash)
            )
        except Exception as e:
            return FileOpOutcome(ok=False, op="write", path=str(path), reason=str(e))

    @staticmethod
    def _hash_file_if_exists(path: Path) -> Optional[str]:
        try:
            if path.exists() and path.is_file():
                return hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception:
            return None
        return None

    def create_file(self, file_path: str, content: str = "") -> Dict[str, Any]:
        """ファイルを作成"""
        outcome = self.write_file_with_approval(file_path, content)
        if not outcome.ok:
            return {"success": False, "message": outcome.reason or "unknown_error", "path": outcome.path}
        size = Path(outcome.path).stat().st_size if Path(outcome.path).exists() else 0
        return {
            "success": True,
            "message": f"ファイル {file_path} を作成しました",
            "path": outcome.path,
            "size": size,
            "created": datetime.now().isoformat(),
        }

    def write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """ファイルに書き込み"""
        outcome = self.write_file_with_approval(file_path, content)
        if not outcome.ok:
            return {"success": False, "message": outcome.reason or "unknown_error", "path": outcome.path}
        size = Path(outcome.path).stat().st_size if Path(outcome.path).exists() else 0
        lines = len(content.split('\n'))
        return {
            "success": True,
            "message": f"ファイル {file_path} に書き込みました",
            "path": outcome.path,
            "size": size,
            "lines": lines,
            "modified": datetime.now().isoformat(),
        }
    
    async def write_file_llm(self, file_path: str, content: str) -> Dict[str, Any]:
        """LLM強化ファイル書き込み"""
        outcome = await self.write_file_with_llm_approval(file_path, content)
        if not outcome.ok:
            return {"success": False, "message": outcome.reason or "unknown_error", "path": outcome.path}
        size = Path(outcome.path).stat().st_size if Path(outcome.path).exists() else 0
        lines = len(content.split('\n'))
        return {
            "success": True,
            "message": f"ファイル {file_path} に書き込みました（LLM強化承認）",
            "path": outcome.path,
            "size": size,
            "lines": lines,
            "modified": datetime.now().isoformat(),
        }
    
    async def create_file_llm(self, file_path: str, content: str = "") -> Dict[str, Any]:
        """LLM強化ファイル作成"""
        outcome = await self.write_file_with_llm_approval(file_path, content)
        if not outcome.ok:
            return {"success": False, "message": outcome.reason or "unknown_error", "path": outcome.path}
        size = Path(outcome.path).stat().st_size if Path(outcome.path).exists() else 0
        return {
            "success": True,
            "message": f"ファイル {file_path} を作成しました（LLM強化承認）",
            "path": outcome.path,
            "size": size,
            "created": datetime.now().isoformat(),
        }

    def exists(self, file_path: str) -> bool:
        """ファイルまたはディレクトリの存在確認"""
        try:
            path = Path(file_path)
            return path.exists()
        except Exception:
            return False

    def read_file(self, file_path: str) -> str:
        """ファイルを読み取り"""
        path = Path(file_path)
        if not path.is_file():
            raise FileOperationError(f"ファイルが見つからないか、ファイルではありません: {file_path}")
        try:
            content = path.read_text(encoding="utf-8")
            
            # ファイル読み取りコンテキストを記録（EnhancedCompanionCore用）
            try:
                from companion.enhanced_core import EnhancedCompanionCore
                if hasattr(self, 'enhanced_core') and self.enhanced_core:
                    self.enhanced_core._record_file_operation("read", file_path, content[:200])
                elif hasattr(self, 'state') and hasattr(self.state, 'collected_context'):
                    # AgentStateに直接記録
                    if 'file_contents' not in self.state.collected_context:
                        self.state.collected_context['file_contents'] = {}
                    self.state.collected_context['file_contents'][file_path] = content[:1000]
            except Exception:
                pass  # コンテキスト記録に失敗しても読み取りは継続
            
            return content
        except Exception as e:
            raise FileOperationError(f"ファイル読み取り失敗: {e}")

    def list_files(self, directory_path: str = ".") -> List[Dict[str, Any]]:
        """ディレクトリ内のファイル一覧を取得"""
        try:
            path = Path(directory_path)
            if not path.is_dir():
                raise FileOperationError(f"これはディレクトリではありません: {directory_path}")
            
            files = []
            for item in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                try:
                    stat = item.stat()
                    files.append({
                        "name": item.name,
                        "path": str(item),
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size if item.is_file() else 0,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                except (PermissionError, OSError):
                    continue
            return files
        except Exception as e:
            raise FileOperationError(f"ファイル一覧の取得に失敗しました: {str(e)}")

    def create_directory(self, directory_path: str) -> Dict[str, Any]:
        """ディレクトリを作成"""
        # Phase 1 safety check
        if not self.file_protector.check_operation("mkdir", directory_path):
            return {"success": False, "message": "安全ポリシーによりブロックされました（作業フォルダ外）", "path": directory_path}
        request = ApprovalRequest(
            operation="ディレクトリ作成",
            description=f"ディレクトリ '{directory_path}' を作成します",
            target=directory_path,
            risk_level=RiskLevel.LOW
        )
        approval = self.approval_gate.request_approval(request)
        if not approval.approved:
            return {"success": False, "message": f"ユーザーによる拒否: {approval.reason}", "path": directory_path}

        try:
            path = Path(directory_path)
            path.mkdir(parents=True, exist_ok=True)
            return {"success": True, "message": f"ディレクトリ '{directory_path}' を作成しました", "path": str(path.absolute())}
        except Exception as e:
            raise FileOperationError(f"ディレクトリ作成に失敗しました: {directory_path} - {str(e)}")

    def search_content(self, file_path: str, pattern: str, context_lines: int = 2) -> Dict[str, Any]:
        """ripgrepベースの高速コンテンツ検索"""
        try:
            import subprocess
            import re
            
            path = Path(file_path)
            if not path.is_file():
                return {"error": f"ファイルが見つかりません: {file_path}"}
            
            # ripgrep (rg) コマンドを実行
            cmd = ["rg", pattern, str(path), "-C", str(context_lines), "-n", "--color", "never"]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    # マッチした結果を解析
                    matches = []
                    lines = result.stdout.split('\n')
                    
                    current_match = None
                    for line in lines:
                        if not line.strip():
                            continue
                        
                        # 行番号とコンテンツを解析
                        match = re.match(r'^(\d+)[:-](.*)$', line)
                        if match:
                            line_num = int(match.group(1))
                            content = match.group(2)
                            
                            if current_match is None or abs(line_num - current_match["line_number"]) > context_lines + 1:
                                # 新しいマッチグループ
                                current_match = {
                                    "line_number": line_num,
                                    "match": content.strip(),
                                    "context_lines": [content]
                                }
                                matches.append(current_match)
                            else:
                                # 既存のマッチに追加
                                current_match["context_lines"].append(content)
                    
                    return {
                        "operation": "高速コンテンツ検索",
                        "pattern": pattern,
                        "file_path": file_path,
                        "matches_found": len(matches),
                        "results": matches[:5],  # 最大5件
                        "tool_used": "ripgrep"
                    }
                else:
                    return {
                        "operation": "高速コンテンツ検索", 
                        "pattern": pattern,
                        "file_path": file_path,
                        "matches_found": 0,
                        "results": [],
                        "tool_used": "ripgrep"
                    }
                    
            except subprocess.TimeoutExpired:
                return {"error": "検索がタイムアウトしました"}
            except FileNotFoundError:
                # ripgrepが利用できない場合のフォールバック
                return self._fallback_search_content(file_path, pattern, context_lines)
                
        except Exception as e:
            return {"error": f"検索エラー: {str(e)}"}
    
    def _fallback_search_content(self, file_path: str, pattern: str, context_lines: int) -> Dict[str, Any]:
        """ripgrepが利用できない場合のフォールバック検索"""
        try:
            import re
            
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
            
            matches = []
            pattern_regex = re.compile(pattern, re.IGNORECASE)
            
            for i, line in enumerate(lines):
                if pattern_regex.search(line):
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    context = ''.join(lines[start:end])
                    
                    matches.append({
                        "line_number": i + 1,
                        "match": line.strip(),
                        "context_lines": [l.rstrip() for l in lines[start:end]]
                    })
            
            return {
                "operation": "コンテンツ検索（フォールバック）",
                "pattern": pattern,
                "file_path": file_path,
                "matches_found": len(matches),
                "results": matches[:5],
                "tool_used": "python_regex"
            }
            
        except Exception as e:
            return {"error": f"フォールバック検索エラー: {str(e)}"}
    
    def read_file_section(self, file_path: str, start_line: int = 1, line_count: int = 50) -> Dict[str, Any]:
        """効率的なセクション読み込み"""
        try:
            path = Path(file_path)
            if not path.is_file():
                return {"error": f"ファイルが見つかりません: {file_path}"}
            
            with open(path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
            
            total_lines = len(lines)
            start_idx = max(0, start_line - 1)  # 1-based to 0-based
            end_idx = min(total_lines, start_idx + line_count)
            
            section_lines = lines[start_idx:end_idx]
            content = ''.join(section_lines)
            
            return {
                "operation": "セクション読み込み",
                "file_path": file_path,
                "section_info": {
                    "start_line": start_line,
                    "end_line": start_idx + len(section_lines),
                    "requested_lines": line_count,
                    "actual_lines": len(section_lines),
                    "total_file_lines": total_lines
                },
                "content": content,
                "has_more": end_idx < total_lines,
                "tool_used": "optimized_read"
            }
            
        except Exception as e:
            return {"error": f"セクション読み込みエラー: {str(e)}"}
    
    def analyze_file_structure(self, file_path: str) -> Dict[str, Any]:
        """ファイル構造の効率的な分析"""
        try:
            path = Path(file_path)
            if not path.is_file():
                return {"error": f"ファイルが見つかりません: {file_path}"}
            
            with open(path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
            
            structure = {
                "operation": "構造分析",
                "file_path": file_path,
                "file_info": {
                    "total_lines": len(lines),
                    "total_chars": sum(len(line) for line in lines),
                    "encoding": "utf-8"
                },
                "headers": [],
                "sections": [],
                "code_blocks": [],
                "tool_used": "structure_analyzer"
            }
            
            current_section = None
            
            for i, line in enumerate(lines, 1):
                line_stripped = line.strip()
                
                # マークダウンヘッダーの検出
                if line_stripped.startswith('#'):
                    level = 0
                    for char in line_stripped:
                        if char == '#':
                            level += 1
                        else:
                            break
                    
                    header_text = line_stripped[level:].strip()
                    header_info = {
                        "line_number": i,
                        "level": level,
                        "text": header_text,
                        "full_line": line_stripped
                    }
                    
                    structure["headers"].append(header_info)
                    
                    # レベル2以上をセクションとして記録
                    if level >= 2:
                        if current_section:
                            current_section["end_line"] = i - 1
                        
                        current_section = {
                            "title": header_text,
                            "level": level,
                            "start_line": i,
                            "end_line": None
                        }
                        structure["sections"].append(current_section)
                
                # コードブロックの検出
                elif line_stripped.startswith('```'):
                    language = line_stripped[3:].strip()
                    structure["code_blocks"].append({
                        "line_number": i,
                        "language": language if language else "text",
                        "marker": line_stripped
                    })
            
            # 最後のセクションの終了行を設定
            if current_section:
                current_section["end_line"] = len(lines)
            
            return structure
            
        except Exception as e:
            return {"error": f"構造分析エラー: {str(e)}"}

    # === Phase 1 compatibility API (used by PlanExecutor/PlanTool) ===
    def apply_with_approval_write(self, file_path: str, content: str, session_id: str = "") -> FileOpOutcome:
        """Compatibility wrapper used by executors to perform an approved write with safety checks."""
        return self.write_file_with_approval(file_path, content)
