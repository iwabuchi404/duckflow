"""
安全なシェル実行ツール
ホワイトリストベースの制限されたコマンド実行
"""
import os
import subprocess
import shlex
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

from ..base.config import config_manager


class ShellExecutionError(Exception):
    """シェル実行エラー"""
    pass


class ShellSecurityError(Exception):
    """シェル実行セキュリティエラー"""
    pass


class ShellTools:
    """安全なシェル実行ツールクラス"""
    
    def __init__(self):
        """初期化"""
        self.config = config_manager.load_config()
        self.shell_config = self.config.tools.shell
        
        # 許可されるコマンド（ホワイトリスト）
        self.allowed_commands = self.shell_config.get('allowed_commands', [])
        
        # タイムアウト設定（秒）
        self.timeout_seconds = self.shell_config.get('timeout_seconds', 30)
        
        # セキュリティ設定
        self.security_config = self.config.security
        self.forbidden_patterns = self.security_config.forbidden_patterns
        
        # 実行ディレクトリの制限（プロジェクトディレクトリ内のみ）
        self.allowed_cwd = Path.cwd()
    
    def is_command_safe(self, command: str) -> Dict[str, Any]:
        """
        コマンドの安全性をチェック
        
        Args:
            command: 実行するコマンド文字列
            
        Returns:
            Dict[str, Any]: 安全性チェック結果
                - is_safe: bool - 安全かどうか
                - risks: List[str] - 検出された危険要素
                - reason: str - 判定理由
        """
        risks = []
        is_safe = True
        reason = "安全"
        
        try:
            # コマンドをパースしてベースコマンドを取得
            parsed_command = shlex.split(command)
            if not parsed_command:
                return {
                    'is_safe': False,
                    'risks': ['空のコマンド'],
                    'reason': 'コマンドが指定されていません'
                }
            
            base_command = parsed_command[0]
            
            # ホワイトリストチェック
            if base_command not in self.allowed_commands:
                risks.append(f'許可されていないコマンド: {base_command}')
                is_safe = False
                reason = f'コマンド "{base_command}" はホワイトリストに含まれていません'
            
            # 禁止パターンチェック
            for pattern in self.forbidden_patterns:
                if pattern in command:
                    risks.append(f'危険なパターン: {pattern}')
                    is_safe = False
                    reason = f'危険なパターン "{pattern}" が含まれています'
            
            # パイプやリダイレクトの制限チェック
            dangerous_operators = ['|', '>', '>>', '<', '&&', '||', ';', '`', '$()']
            for operator in dangerous_operators:
                if operator in command:
                    # 一部の安全なケースは許可
                    if operator == '|' and any(safe_pipe in command for safe_pipe in ['| grep', '| head', '| tail', '| wc']):
                        continue
                    risks.append(f'危険な演算子: {operator}')
                    is_safe = False
                    reason = f'危険な演算子 "{operator}" が含まれています'
            
            # パスの安全性チェック
            if '..' in command or '/etc/' in command or '/root/' in command:
                risks.append('危険なパスアクセス')
                is_safe = False
                reason = '危険なパスアクセスが含まれています'
            
            return {
                'is_safe': is_safe,
                'risks': risks,
                'reason': reason
            }
            
        except Exception as e:
            return {
                'is_safe': False,
                'risks': [f'コマンド解析エラー: {str(e)}'],
                'reason': f'コマンドの解析に失敗しました: {str(e)}'
            }
    
    def execute_command(
        self, 
        command: str, 
        cwd: Optional[str] = None,
        capture_output: bool = True,
        require_approval: bool = True
    ) -> Dict[str, Any]:
        """
        安全なコマンド実行
        
        Args:
            command: 実行するコマンド
            cwd: 実行ディレクトリ（デフォルト: 現在のディレクトリ）
            capture_output: 出力をキャプチャするかどうか
            require_approval: 人間の承認を必要とするか
            
        Returns:
            Dict[str, Any]: 実行結果
                - success: bool - 実行成功
                - stdout: str - 標準出力
                - stderr: str - 標準エラー出力
                - return_code: int - 終了コード
                - command: str - 実行されたコマンド
                - execution_time: float - 実行時間（秒）
        """
        start_time = datetime.now()
        
        try:
            # 安全性チェック
            safety_check = self.is_command_safe(command)
            if not safety_check['is_safe']:
                return {
                    'success': False,
                    'stdout': '',
                    'stderr': f"コマンド実行拒否: {safety_check['reason']}",
                    'return_code': -1,
                    'command': command,
                    'execution_time': 0.0,
                    'error': ShellSecurityError(safety_check['reason']),
                    'risks': safety_check['risks']
                }
            
            # 実行ディレクトリの設定と検証
            if cwd is None:
                cwd = str(self.allowed_cwd)
            else:
                cwd_path = Path(cwd).resolve()
                if not cwd_path.is_relative_to(self.allowed_cwd):
                    return {
                        'success': False,
                        'stdout': '',
                        'stderr': f"許可されていない実行ディレクトリ: {cwd}",
                        'return_code': -1,
                        'command': command,
                        'execution_time': 0.0,
                        'error': ShellSecurityError(f"実行ディレクトリが許可範囲外: {cwd}")
                    }
                cwd = str(cwd_path)
            
            # コマンド実行
            if capture_output:
                # Windows環境では適切なシェルを使用
                if os.name == 'nt':
                    result = subprocess.run(
                        command,
                        shell=True,
                        cwd=cwd,
                        capture_output=True,
                        text=True,
                        timeout=self.timeout_seconds,
                        encoding='utf-8',
                        errors='replace'
                    )
                else:
                    result = subprocess.run(
                        command,
                        shell=True,
                        cwd=cwd,
                        capture_output=True,
                        text=True,
                        timeout=self.timeout_seconds,
                        encoding='utf-8',
                        errors='replace'
                    )
                
                stdout = result.stdout or ''
                stderr = result.stderr or ''
                return_code = result.returncode
            else:
                # ライブ出力（インタラクティブコマンド用）
                process = subprocess.Popen(
                    command,
                    shell=True,
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                
                stdout_lines = []
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        stdout_lines.append(output.strip())
                        print(output.strip())  # リアルタイム出力
                
                stdout = '\n'.join(stdout_lines)
                stderr = ''
                return_code = process.poll()
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                'success': return_code == 0,
                'stdout': stdout,
                'stderr': stderr,
                'return_code': return_code,
                'command': command,
                'execution_time': execution_time,
                'cwd': cwd
            }
            
        except subprocess.TimeoutExpired:
            execution_time = (datetime.now() - start_time).total_seconds()
            return {
                'success': False,
                'stdout': '',
                'stderr': f"コマンドがタイムアウトしました（{self.timeout_seconds}秒）",
                'return_code': -1,
                'command': command,
                'execution_time': execution_time,
                'error': ShellExecutionError(f"タイムアウト: {self.timeout_seconds}秒")
            }
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return {
                'success': False,
                'stdout': '',
                'stderr': f"コマンド実行エラー: {str(e)}",
                'return_code': -1,
                'command': command,
                'execution_time': execution_time,
                'error': ShellExecutionError(str(e))
            }
    
    def run_tests(
        self, 
        test_path: Optional[str] = None, 
        verbose: bool = False,
        pattern: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        pytestを使用してテストを実行
        
        Args:
            test_path: テストファイル/ディレクトリのパス
            verbose: 詳細出力モード
            pattern: テストパターン（例: "test_*.py"）
            
        Returns:
            Dict[str, Any]: テスト実行結果
        """
        # デフォルトのテストパス
        if test_path is None:
            test_path = "tests/"
        
        # テストコマンドの構築
        cmd_parts = ["pytest"]
        
        if verbose:
            cmd_parts.append("-v")
        
        if pattern:
            cmd_parts.extend(["-k", pattern])
        
        # 出力形式設定
        cmd_parts.extend(["--tb=short", "--no-header"])
        
        cmd_parts.append(test_path)
        
        command = " ".join(cmd_parts)
        
        # テスト実行
        result = self.execute_command(
            command=command,
            capture_output=True,
            require_approval=False  # テスト実行は自動承認
        )
        
        # テスト結果の解析
        if result['success']:
            # 成功時の結果解析
            output = result['stdout']
            passed_match = re.search(r'(\d+) passed', output)
            failed_match = re.search(r'(\d+) failed', output)
            
            passed_count = int(passed_match.group(1)) if passed_match else 0
            failed_count = int(failed_match.group(1)) if failed_match else 0
            
            result.update({
                'test_status': 'PASSED' if failed_count == 0 else 'FAILED',
                'passed_count': passed_count,
                'failed_count': failed_count,
                'total_count': passed_count + failed_count
            })
        else:
            # 失敗時の結果
            result.update({
                'test_status': 'ERROR',
                'passed_count': 0,
                'failed_count': 0,
                'total_count': 0
            })
        
        return result
    
    def run_linter(
        self, 
        tool: str = "ruff",
        path: str = ".",
        fix: bool = False
    ) -> Dict[str, Any]:
        """
        リンタを実行
        
        Args:
            tool: リンターツール名 ("ruff", "black", "mypy")
            path: チェック対象のパス
            fix: 自動修正を実行するか
            
        Returns:
            Dict[str, Any]: リンター実行結果
        """
        if tool not in ["ruff", "black", "mypy"]:
            return {
                'success': False,
                'stdout': '',
                'stderr': f"サポートされていないリンター: {tool}",
                'return_code': -1,
                'command': '',
                'execution_time': 0.0,
                'error': ShellExecutionError(f"サポートされていないリンター: {tool}")
            }
        
        # コマンドの構築
        if tool == "ruff":
            cmd_parts = ["ruff", "check" if not fix else "check --fix", path]
        elif tool == "black":
            cmd_parts = ["black", "--check" if not fix else "", path]
        elif tool == "mypy":
            cmd_parts = ["mypy", path]
        
        command = " ".join(filter(None, cmd_parts))
        
        # リンター実行
        result = self.execute_command(
            command=command,
            capture_output=True,
            require_approval=False  # リンターは自動承認
        )
        
        # 結果にツール情報を追加
        result['linter_tool'] = tool
        result['auto_fix'] = fix
        
        return result
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        システム情報を取得
        
        Returns:
            Dict[str, Any]: システム情報
        """
        info = {}
        
        # 安全なシステム情報取得コマンド
        safe_commands = {
            'python_version': 'python --version',
            'pip_version': 'pip --version',
            'git_version': 'git --version',
            'current_directory': 'pwd' if os.name != 'nt' else 'cd',
            'disk_usage': 'df -h .' if os.name != 'nt' else 'dir /-c',
        }
        
        for info_type, command in safe_commands.items():
            try:
                result = self.execute_command(
                    command=command,
                    capture_output=True,
                    require_approval=False
                )
                
                if result['success']:
                    info[info_type] = result['stdout'].strip()
                else:
                    info[info_type] = f"取得失敗: {result['stderr']}"
                    
            except Exception as e:
                info[info_type] = f"エラー: {str(e)}"
        
        return {
            'success': True,
            'system_info': info,
            'timestamp': datetime.now().isoformat()
        }


# グローバルインスタンス
shell_tools = ShellTools()