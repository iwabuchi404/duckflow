"""
SimpleCodeRunner - Phase 1.6: コード実行機能
DuckFlowのコード実行機能を提供するシンプルなコードランナー
"""

import os
import sys
import subprocess
import tempfile
import traceback
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging


class SimpleCodeRunner:
    """シンプルなコード実行システム
    
    Phase 1.6の目標:
    - Pythonファイルの実行
    - 実行結果の表示
    - エラー時の自然な対応
    - 実行中の対話継続
    """
    
    def __init__(self, approval_mode: bool = True):
        """初期化
        
        Args:
            approval_mode: 実行前の承認が必要かどうか
        """
        self.approval_mode = approval_mode
        self.logger = logging.getLogger(__name__)
        
        # 安全な実行ディレクトリ
        self.safe_directories = [
            str(Path.cwd()),  # カレントディレクトリ
            str(Path.home() / "Desktop"),  # デスクトップ
            str(Path.home() / "Documents"),  # ドキュメント
        ]
    
    def run_python_file(self, file_path: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Pythonファイルを実行
        
        Args:
            file_path: 実行するPythonファイルのパス
            args: コマンドライン引数
            
        Returns:
            実行結果の辞書
        """
        try:
            # ファイルパスの検証
            file_path = Path(file_path).resolve()
            
            # 安全性チェック
            if not self._is_safe_to_execute(file_path):
                return {
                    "success": False,
                    "error": "セキュリティ上の理由で実行できません",
                    "file_path": str(file_path),
                    "output": "",
                    "exit_code": -1
                }
            
            # ファイルの存在確認
            if not file_path.exists():
                return {
                    "success": False,
                    "error": f"ファイルが見つかりません: {file_path}",
                    "file_path": str(file_path),
                    "output": "",
                    "exit_code": -1
                }
            
            # 承認確認
            if self.approval_mode:
                if not self._get_execution_approval(file_path):
                    return {
                        "success": False,
                        "error": "実行が承認されませんでした",
                        "file_path": str(file_path),
                        "output": "",
                        "exit_code": -1
                    }
            
            # 実行
            self.logger.info(f"Pythonファイルを実行中: {file_path}")
            
            # 引数の準備
            cmd = [sys.executable, str(file_path)]
            if args:
                cmd.extend(args)
            
            # 実行
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=file_path.parent,
                timeout=30  # 30秒タイムアウト
            )
            
            # 結果の整理
            output = result.stdout.strip()
            error_output = result.stderr.strip()
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "file_path": str(file_path),
                    "output": output,
                    "error_output": error_output,
                    "exit_code": result.returncode,
                    "execution_time": "完了"
                }
            else:
                return {
                    "success": False,
                    "file_path": str(file_path),
                    "output": output,
                    "error_output": error_output,
                    "exit_code": result.returncode,
                    "error": f"実行エラー (終了コード: {result.returncode})"
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "実行がタイムアウトしました（30秒）",
                "file_path": str(file_path),
                "output": "",
                "exit_code": -1
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"実行中にエラーが発生しました: {str(e)}",
                "file_path": str(file_path),
                "output": "",
                "exit_code": -1,
                "traceback": traceback.format_exc()
            }
    
    def run_command(self, command: str, cwd: Optional[str] = None) -> Dict[str, Any]:
        """コマンドを実行
        
        Args:
            command: 実行するコマンド
            cwd: 作業ディレクトリ
            
        Returns:
            実行結果の辞書
        """
        try:
            # 安全性チェック
            if not self._is_safe_command(command):
                return {
                    "success": False,
                    "error": "セキュリティ上の理由で実行できません",
                    "command": command,
                    "output": "",
                    "exit_code": -1
                }
            
            # 承認確認
            if self.approval_mode:
                if not self._get_command_approval(command):
                    return {
                        "success": False,
                        "error": "実行が承認されませんでした",
                        "command": command,
                        "output": "",
                        "exit_code": -1
                    }
            
            # 実行
            self.logger.info(f"コマンドを実行中: {command}")
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd or os.getcwd(),
                timeout=60  # コマンドは60秒タイムアウト
            )
            
            # 結果の整理
            output = result.stdout.strip()
            error_output = result.stderr.strip()
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "command": command,
                    "output": output,
                    "error_output": error_output,
                    "exit_code": result.returncode,
                    "execution_time": "完了"
                }
            else:
                return {
                    "success": False,
                    "command": command,
                    "output": output,
                    "error_output": error_output,
                    "exit_code": result.returncode,
                    "error": f"コマンド実行エラー (終了コード: {result.returncode})"
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "実行がタイムアウトしました（60秒）",
                "command": command,
                "output": "",
                "exit_code": -1
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"実行中にエラーが発生しました: {str(e)}",
                "command": command,
                "output": "",
                "exit_code": -1,
                "traceback": traceback.format_exc()
            }
    
    def _is_safe_to_execute(self, file_path: Path) -> bool:
        """ファイルが安全に実行できるかチェック"""
        try:
            # 絶対パスに変換
            abs_path = file_path.resolve()
            
            # 安全なディレクトリ内かチェック
            for safe_dir in self.safe_directories:
                if str(abs_path).startswith(safe_dir):
                    return True
            
            # 一時ディレクトリ内かチェック
            if str(abs_path).startswith(tempfile.gettempdir()):
                return True
            
            return False
            
        except Exception:
            return False
    
    def _is_safe_command(self, command: str) -> bool:
        """コマンドが安全かチェック"""
        # 危険なコマンドをブロック
        dangerous_commands = [
            "rm -rf", "del /s", "format", "fdisk", "dd",
            "shutdown", "reboot", "halt", "poweroff"
        ]
        
        command_lower = command.lower()
        for dangerous in dangerous_commands:
            if dangerous in command_lower:
                return False
        
        return True
    
    def _get_execution_approval(self, file_path: Path) -> bool:
        """ファイル実行の承認を取得"""
        try:
            from .ui import rich_ui
            
            rich_ui.print_message(f"⚠️  Pythonファイルの実行を要求されました", "warning")
            rich_ui.print_message(f"📁 ファイル: {file_path}", "info")
            
            # ファイル内容のプレビュー
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    preview = content[:200] + "..." if len(content) > 200 else content
                    rich_ui.print_message(f"📝 内容プレビュー:\n{preview}", "info")
            except Exception:
                rich_ui.print_message("📝 ファイル内容の読み取りに失敗しました", "warning")
            
            # 承認確認
            response = input("このファイルを実行しますか？ (y/N): ").strip().lower()
            return response in ['y', 'yes']
            
        except Exception:
            # UIが利用できない場合は安全のためFalse
            return False
    
    def _get_command_approval(self, command: str) -> bool:
        """コマンド実行の承認を取得"""
        try:
            from .ui import rich_ui
            
            rich_ui.print_message(f"⚠️  コマンドの実行を要求されました", "warning")
            rich_ui.print_message(f"💻 コマンド: {command}", "info")
            
            # 承認確認
            response = input("このコマンドを実行しますか？ (y/N): ").strip().lower()
            return response in ['y', 'yes']
            
        except Exception:
            # UIが利用できない場合は安全のためFalse
            return False
    
    def format_execution_result(self, result: Dict[str, Any]) -> str:
        """実行結果をユーザーフレンドリーな形式にフォーマット"""
        if result["success"]:
            output = f"✅ 実行完了！\n"
            output += f"📁 ファイル: {result.get('file_path', result.get('command', 'N/A'))}\n"
            
            if result.get("output"):
                output += f"📤 出力:\n{result['output']}\n"
            
            if result.get("error_output"):
                output += f"⚠️  警告/エラー出力:\n{result['error_output']}\n"
            
            output += f"🔢 終了コード: {result['exit_code']}"
            
        else:
            output = f"❌ 実行失敗\n"
            output += f"📁 ファイル: {result.get('file_path', result.get('command', 'N/A'))}\n"
            output += f"🚨 エラー: {result['error']}\n"
            
            if result.get("output"):
                output += f"📤 出力:\n{result['output']}\n"
            
            if result.get("error_output"):
                output += f"⚠️  エラー出力:\n{result['error_output']}\n"
            
            if result.get("traceback"):
                output += f"🔍 詳細:\n{result['traceback']}"
        
        return output
