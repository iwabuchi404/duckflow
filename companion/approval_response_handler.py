"""
ApprovalResponseHandler - 承認応答の高度な処理
タイムアウト、代替案提案、確認ダイアログなどの処理

設計思想:
- ユーザーの拒否を自然に受け入れる
- 建設的な代替案を提案
- タイムアウトを適切に処理
- 相棒らしい継続的な関係性を維持
"""

import asyncio
import time
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from codecrafter.ui.rich_ui import rich_ui
from .approval_system import (
    ApprovalRequest, ApprovalResponse, OperationInfo, RiskLevel, OperationType,
    ApprovalTimeoutError, ApprovalUIError
)
from .approval_ui import UserApprovalUI


class ApprovalResponseHandler:
    """承認応答の高度な処理クラス
    
    タイムアウト、代替案提案、確認ダイアログなどを統合的に処理
    """
    
    def __init__(self, ui: UserApprovalUI, timeout_seconds: int = 30):
        """初期化
        
        Args:
            ui: UserApprovalUIインスタンス
            timeout_seconds: デフォルトタイムアウト時間（秒）
        """
        self.ui = ui
        self.default_timeout = timeout_seconds
        self.executor = ThreadPoolExecutor(max_workers=1)
        
        # 代替案生成のマッピング
        self.alternative_generators = {
            OperationType.CREATE_FILE: self._generate_file_creation_alternatives,
            OperationType.WRITE_FILE: self._generate_file_write_alternatives,
            OperationType.DELETE_FILE: self._generate_file_delete_alternatives,
            OperationType.EXECUTE_PYTHON: self._generate_code_execution_alternatives,
            OperationType.EXECUTE_COMMAND: self._generate_command_execution_alternatives,
        }
    
    def handle_approval_with_timeout(self, request: ApprovalRequest, 
                                   timeout_seconds: Optional[int] = None) -> ApprovalResponse:
        """タイムアウト付き承認処理
        
        Args:
            request: 承認要求
            timeout_seconds: タイムアウト時間（Noneの場合はデフォルト使用）
            
        Returns:
            ApprovalResponse: 承認応答
            
        Raises:
            ApprovalTimeoutError: タイムアウトした場合
        """
        timeout = timeout_seconds or self.default_timeout
        
        try:
            # タイムアウト警告を表示（長時間の場合）
            if timeout > 60:
                self.ui.show_timeout_warning(timeout)
            
            # 非同期でタイムアウト付き実行
            future = self.executor.submit(self.ui.show_approval_request, request)
            
            try:
                response = future.result(timeout=timeout)
                return response
                
            except FutureTimeoutError:
                # タイムアウト発生
                future.cancel()
                
                timeout_response = self._handle_timeout(request, timeout)
                raise ApprovalTimeoutError(
                    f"承認要求がタイムアウトしました（{timeout}秒）"
                )
                
        except ApprovalTimeoutError:
            # タイムアウトは再発生
            raise
        except Exception as e:
            # その他のエラー
            raise ApprovalUIError(f"承認処理中にエラーが発生しました: {str(e)}")
    
    def handle_rejection_with_alternatives(self, request: ApprovalRequest, 
                                         rejection_reason: str) -> ApprovalResponse:
        """拒否時の代替案提案処理
        
        Args:
            request: 承認要求
            rejection_reason: 拒否理由
            
        Returns:
            ApprovalResponse: 代替案を含む応答
        """
        try:
            # 相棒らしい理解の表現
            understanding_messages = [
                "分かりました。その操作は実行しません。",
                "承知しました。やめておきますね。",
                "了解です。別の方法を考えてみましょう。",
            ]
            
            import random
            understanding_msg = random.choice(understanding_messages)
            rich_ui.print_message(f"🙅 {understanding_msg}", "info")
            
            # 代替案を生成
            alternatives = self._generate_alternatives(request.operation_info)
            
            if alternatives:
                # 代替案を提示
                self._present_alternatives(alternatives)
                
                # ユーザーに代替案の選択を求める
                selected_alternative = self._get_alternative_selection(alternatives)
                
                if selected_alternative:
                    return ApprovalResponse(
                        approved=False,
                        reason=f"{understanding_msg} 代替案: {selected_alternative}",
                        alternative_suggested=True
                    )
            
            # 代替案がない、または選択されなかった場合
            encouragement_messages = [
                "他に何かお手伝いできることはありますか？",
                "別のことで何かサポートできることがあれば教えてください。",
                "何か他にやりたいことがあれば、遠慮なく言ってくださいね。",
            ]
            
            encouragement_msg = random.choice(encouragement_messages)
            rich_ui.print_message(f"💡 {encouragement_msg}", "info")
            
            return ApprovalResponse(
                approved=False,
                reason=f"{understanding_msg} {encouragement_msg}",
                alternative_suggested=len(alternatives) > 0
            )
            
        except Exception as e:
            # エラー時もポジティブに
            return ApprovalResponse(
                approved=False,
                reason=f"分かりました。エラーが発生しましたが、他の方法を試してみましょう: {str(e)}",
                alternative_suggested=False
            )
    
    def create_confirmation_dialog(self, message: str, risk_level: RiskLevel, 
                                 details: Optional[Dict[str, Any]] = None) -> bool:
        """確認ダイアログを作成
        
        Args:
            message: 確認メッセージ
            risk_level: リスクレベル
            details: 追加詳細情報
            
        Returns:
            bool: 確認された場合True
        """
        try:
            # リスクレベルに応じた確認の強度を調整
            if risk_level == RiskLevel.CRITICAL_RISK:
                return self._create_critical_confirmation_dialog(message, details)
            elif risk_level == RiskLevel.HIGH_RISK:
                return self._create_high_risk_confirmation_dialog(message, details)
            else:
                return self._create_standard_confirmation_dialog(message, details)
                
        except Exception as e:
            rich_ui.print_error(f"確認ダイアログでエラーが発生しました: {e}")
            # エラー時は安全のため拒否
            return False
    
    def _handle_timeout(self, request: ApprovalRequest, timeout_seconds: int) -> ApprovalResponse:
        """タイムアウト処理
        
        Args:
            request: 承認要求
            timeout_seconds: タイムアウト時間
            
        Returns:
            ApprovalResponse: タイムアウト応答
        """
        timeout_messages = [
            f"⏰ {timeout_seconds}秒間応答がなかったため、安全のため操作をキャンセルしました。",
            f"⏰ タイムアウト（{timeout_seconds}秒）により操作を中止しました。",
            f"⏰ {timeout_seconds}秒経過したため、操作を安全に停止しました。",
        ]
        
        import random
        timeout_msg = random.choice(timeout_messages)
        rich_ui.print_message(timeout_msg, "warning")
        
        # 再試行の提案
        retry_msg = "もう一度試したい場合は、同じ操作を再度実行してください。"
        rich_ui.print_message(f"💡 {retry_msg}", "info")
        
        return ApprovalResponse(
            approved=False,
            reason=f"{timeout_msg} {retry_msg}"
        )
    
    def _generate_alternatives(self, operation_info: OperationInfo) -> List[Dict[str, str]]:
        """代替案を生成
        
        Args:
            operation_info: 操作情報
            
        Returns:
            List[Dict[str, str]]: 代替案のリスト
        """
        generator = self.alternative_generators.get(operation_info.operation_type)
        if generator:
            return generator(operation_info)
        
        # デフォルトの汎用代替案
        return [
            {
                "title": "情報確認",
                "description": "操作の詳細情報を確認する",
                "action": "show_info"
            },
            {
                "title": "別の方法を相談",
                "description": "同じ目的を達成する別の方法を一緒に考える",
                "action": "discuss_alternatives"
            }
        ]
    
    def _generate_file_creation_alternatives(self, operation_info: OperationInfo) -> List[Dict[str, str]]:
        """ファイル作成の代替案を生成"""
        return [
            {
                "title": "内容をプレビューのみ表示",
                "description": "ファイルを作成せず、内容だけを確認する",
                "action": "preview_content"
            },
            {
                "title": "別の場所に作成",
                "description": "より安全な場所（例: tempディレクトリ）にファイルを作成する",
                "action": "create_in_safe_location"
            },
            {
                "title": "ファイル名を変更",
                "description": "既存ファイルと競合しない名前で作成する",
                "action": "create_with_different_name"
            }
        ]
    
    def _generate_file_write_alternatives(self, operation_info: OperationInfo) -> List[Dict[str, str]]:
        """ファイル書き込みの代替案を生成"""
        return [
            {
                "title": "変更内容をプレビュー",
                "description": "実際に書き込まず、変更内容だけを表示する",
                "action": "preview_changes"
            },
            {
                "title": "バックアップを作成してから変更",
                "description": "元のファイルのバックアップを作成してから変更する",
                "action": "backup_and_modify"
            },
            {
                "title": "新しいファイルとして保存",
                "description": "元のファイルを保持し、新しいファイルとして保存する",
                "action": "save_as_new_file"
            }
        ]
    
    def _generate_file_delete_alternatives(self, operation_info: OperationInfo) -> List[Dict[str, str]]:
        """ファイル削除の代替案を生成"""
        return [
            {
                "title": "ファイル内容を確認",
                "description": "削除前にファイルの内容を確認する",
                "action": "show_file_content"
            },
            {
                "title": "別の場所に移動",
                "description": "削除ではなく、別の場所に移動する",
                "action": "move_to_different_location"
            },
            {
                "title": "ファイル名を変更",
                "description": "削除ではなく、ファイル名を変更して保持する",
                "action": "rename_file"
            }
        ]
    
    def _generate_code_execution_alternatives(self, operation_info: OperationInfo) -> List[Dict[str, str]]:
        """コード実行の代替案を生成"""
        return [
            {
                "title": "コード内容を確認",
                "description": "実行せず、コードの内容だけを確認する",
                "action": "show_code_content"
            },
            {
                "title": "構文チェックのみ実行",
                "description": "実際の実行ではなく、構文エラーのチェックのみ行う",
                "action": "syntax_check_only"
            },
            {
                "title": "安全なサンドボックスで実行",
                "description": "制限された環境で安全に実行する",
                "action": "run_in_sandbox"
            }
        ]
    
    def _generate_command_execution_alternatives(self, operation_info: OperationInfo) -> List[Dict[str, str]]:
        """コマンド実行の代替案を生成"""
        return [
            {
                "title": "コマンドの説明を表示",
                "description": "コマンドを実行せず、何をするコマンドかを説明する",
                "action": "explain_command"
            },
            {
                "title": "ドライランモードで実行",
                "description": "実際の変更を行わず、何が起こるかをシミュレートする",
                "action": "dry_run"
            },
            {
                "title": "より安全なコマンドを提案",
                "description": "同じ目的を達成するより安全なコマンドを提案する",
                "action": "suggest_safer_command"
            }
        ]
    
    def _present_alternatives(self, alternatives: List[Dict[str, str]]) -> None:
        """代替案をユーザーに提示
        
        Args:
            alternatives: 代替案のリスト
        """
        if not alternatives:
            return
        
        rich_ui.print_message("💡 代わりに、以下のような方法はいかがでしょうか？", "info")
        
        for i, alt in enumerate(alternatives, 1):
            rich_ui.print_message(f"  {i}. {alt['title']}", "cyan")
            rich_ui.print_message(f"     {alt['description']}", "muted")
    
    def _get_alternative_selection(self, alternatives: List[Dict[str, str]]) -> Optional[str]:
        """代替案の選択を取得
        
        Args:
            alternatives: 代替案のリスト
            
        Returns:
            Optional[str]: 選択された代替案（選択されなかった場合はNone）
        """
        if not alternatives:
            return None
        
        try:
            # 選択肢を提示
            rich_ui.print_message("\n何か試してみますか？", "info")
            
            # 簡単な選択UI
            choice = rich_ui.get_user_input("番号を入力（何もしない場合はEnter）")
            
            if choice.strip():
                try:
                    index = int(choice.strip()) - 1
                    if 0 <= index < len(alternatives):
                        selected = alternatives[index]
                        rich_ui.print_message(f"✅ 「{selected['title']}」を選択しました。", "success")
                        return selected['title']
                    else:
                        rich_ui.print_message("無効な番号です。", "warning")
                except ValueError:
                    rich_ui.print_message("数字を入力してください。", "warning")
            
            return None
            
        except Exception as e:
            rich_ui.print_error(f"選択処理でエラーが発生しました: {e}")
            return None
    
    def _create_standard_confirmation_dialog(self, message: str, 
                                           details: Optional[Dict[str, Any]] = None) -> bool:
        """標準確認ダイアログ"""
        rich_ui.print_message(f"🤔 {message}", "info")
        
        if details:
            for key, value in details.items():
                rich_ui.print_message(f"  {key}: {value}", "muted")
        
        return rich_ui.get_confirmation("続行しますか？", default=False)
    
    def _create_high_risk_confirmation_dialog(self, message: str, 
                                            details: Optional[Dict[str, Any]] = None) -> bool:
        """高リスク確認ダイアログ"""
        rich_ui.print_message(f"⚠️ {message}", "warning")
        rich_ui.print_message("この操作はシステムに変更を加える可能性があります。", "warning")
        
        if details:
            rich_ui.print_message("詳細情報:", "info")
            for key, value in details.items():
                rich_ui.print_message(f"  {key}: {value}", "muted")
        
        # 2段階確認
        first_confirm = rich_ui.get_confirmation("本当に実行しますか？", default=False)
        if not first_confirm:
            return False
        
        rich_ui.print_message("⚠️ 最終確認です。", "warning")
        return rich_ui.get_confirmation("実行してもよろしいですか？", default=False)
    
    def _create_critical_confirmation_dialog(self, message: str, 
                                           details: Optional[Dict[str, Any]] = None) -> bool:
        """重要リスク確認ダイアログ"""
        rich_ui.print_message(f"🚨 {message}", "error")
        rich_ui.print_message("⚠️ この操作はシステムに重大な影響を与える可能性があります！", "error")
        
        # リスクの詳細説明
        risks = [
            "システムファイルの破損",
            "セキュリティの脆弱性",
            "データの損失",
            "システムの不安定化"
        ]
        
        rich_ui.print_message("想定されるリスク:", "error")
        for risk in risks:
            rich_ui.print_message(f"  - {risk}", "muted")
        
        if details:
            rich_ui.print_message("操作詳細:", "info")
            for key, value in details.items():
                rich_ui.print_message(f"  {key}: {value}", "muted")
        
        # 3段階確認
        rich_ui.print_message("🚨 重要な操作のため、3段階の確認を行います。", "error")
        
        # 第1段階
        if not rich_ui.get_confirmation("1/3: リスクを理解した上で続行しますか？", default=False):
            return False
        
        # 第2段階
        rich_ui.print_message("⚠️ 本当によろしいですか？この操作は取り消せません。", "warning")
        if not rich_ui.get_confirmation("2/3: 確実に実行しますか？", default=False):
            return False
        
        # 第3段階（最終確認）
        rich_ui.print_message("🚨 最終確認です。", "error")
        rich_ui.print_message("この操作により発生する問題について、全責任を負います。", "error")
        return rich_ui.get_confirmation("3/3: 最終確認 - 実行しますか？", default=False)
    
    def cleanup(self) -> None:
        """リソースのクリーンアップ"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)