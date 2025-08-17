"""
UserApprovalUI - ユーザー承認のUI処理
相棒らしい自然な承認インターフェース

設計思想:
- 相棒らしい自然な言葉での承認要求
- 分かりやすい操作詳細の表示
- 適切なリスク警告
- 簡単な操作（y/n）での応答
"""

import time
from typing import Optional
from datetime import datetime

from codecrafter.ui.rich_ui import rich_ui
from .approval_system import (
    ApprovalRequest, ApprovalResponse, OperationInfo, RiskLevel,
    ApprovalTimeoutError, ApprovalUIError
)


class UserApprovalUI:
    """ユーザー承認のUI処理クラス
    
    相棒らしい自然な対話で承認要求を行う
    """
    
    def __init__(self, timeout_seconds: int = 30):
        """初期化
        
        Args:
            timeout_seconds: 承認要求のタイムアウト時間（秒）
        """
        self.timeout_seconds = timeout_seconds
        
        # 相棒らしい表現のバリエーション
        self.thinking_expressions = [
            "🤔 ちょっと相談があるのですが...",
            "🤔 お聞きしたいことがあります...",
            "🤔 確認させてください...",
        ]
        
        self.approval_expressions = [
            "実行してもよろしいでしょうか？",
            "進めても大丈夫でしょうか？",
            "やってもいいですか？",
        ]
        
        self.thanks_expressions = [
            "ありがとうございます！",
            "分かりました！",
            "了解です！",
        ]
        
        self.understanding_expressions = [
            "承知しました。",
            "分かりました。",
            "了解です。",
        ]
    
    def show_approval_request(self, request: ApprovalRequest) -> ApprovalResponse:
        """承認要求をユーザーに表示し、応答を取得
        
        Args:
            request: 承認要求
            
        Returns:
            ApprovalResponse: ユーザーの応答
            
        Raises:
            ApprovalTimeoutError: タイムアウトした場合
            ApprovalUIError: UI関連のエラー
        """
        try:
            # 相棒らしい導入
            import random
            thinking_msg = random.choice(self.thinking_expressions)
            rich_ui.print_message(thinking_msg, "info")
            time.sleep(0.5)
            
            # 操作詳細を表示
            formatted_details = self.format_operation_details(request.operation_info)
            rich_ui.print_panel(formatted_details, "🔍 操作の詳細", "cyan")
            
            # リスク警告を表示
            self.show_risk_warning(request.operation_info.risk_level, request.operation_info.description)
            
            # プレビューがある場合は表示
            if request.operation_info.preview:
                self._show_preview(request.operation_info.preview)
            
            # 承認要求
            approval_msg = random.choice(self.approval_expressions)
            rich_ui.print_message(f"\n{approval_msg}", "warning")
            
            # ユーザー応答を取得
            start_time = datetime.now()
            user_response = self._get_user_response()
            end_time = datetime.now()
            
            # 応答時間をチェック
            response_time = (end_time - start_time).total_seconds()
            if response_time > self.timeout_seconds:
                raise ApprovalTimeoutError(f"承認要求がタイムアウトしました（{self.timeout_seconds}秒）")
            
            # 応答に応じたメッセージ
            if user_response:
                thanks_msg = random.choice(self.thanks_expressions)
                rich_ui.print_message(f"✅ {thanks_msg}", "success")
            else:
                understanding_msg = random.choice(self.understanding_expressions)
                rich_ui.print_message(f"🙅 {understanding_msg}", "info")
            
            return ApprovalResponse(
                approved=user_response,
                timestamp=end_time
            )
            
        except ApprovalTimeoutError:
            # タイムアウトは再発生
            raise
        except KeyboardInterrupt:
            # Ctrl+Cは拒否として扱う
            rich_ui.print_message("\n🙅 操作をキャンセルしました。", "warning")
            return ApprovalResponse(
                approved=False,
                reason="ユーザーによりキャンセルされました"
            )
        except Exception as e:
            # その他のエラー
            raise ApprovalUIError(f"承認UI処理中にエラーが発生しました: {str(e)}")
    
    def format_operation_details(self, operation_info: OperationInfo) -> str:
        """操作詳細を分かりやすく整形
        
        Args:
            operation_info: 操作情報
            
        Returns:
            str: 整形された操作詳細
        """
        details = f"**操作内容:** {operation_info.description}\n"
        details += f"**対象:** {operation_info.target}\n"
        details += f"**リスクレベル:** {self._format_risk_level(operation_info.risk_level)}\n"
        
        # 追加詳細情報があれば表示
        if operation_info.details:
            important_details = []
            
            # 重要な詳細情報を抽出
            if 'content' in operation_info.details and operation_info.details['content']:
                content = operation_info.details['content']
                if len(content) > 100:
                    content = content[:100] + "..."
                important_details.append(f"内容: {content}")
            
            if 'command' in operation_info.details and operation_info.details['command']:
                important_details.append(f"コマンド: {operation_info.details['command']}")
            
            if 'size' in operation_info.details:
                important_details.append(f"サイズ: {operation_info.details['size']} bytes")
            
            if important_details:
                details += f"**追加情報:** {', '.join(important_details)}\n"
        
        return details.strip()
    
    def show_risk_warning(self, risk_level: RiskLevel, description: str) -> None:
        """リスク警告を表示
        
        Args:
            risk_level: リスクレベル
            description: 操作説明
        """
        if risk_level == RiskLevel.LOW_RISK:
            rich_ui.print_message("💚 この操作は安全です。システムに変更を加えません。", "success")
        
        elif risk_level == RiskLevel.HIGH_RISK:
            rich_ui.print_message("⚠️ この操作はファイルやシステムに変更を加える可能性があります。", "warning")
            rich_ui.print_message("   慎重に検討してから実行してください。", "warning")
        
        elif risk_level == RiskLevel.CRITICAL_RISK:
            rich_ui.print_message("🚨 この操作はシステムに重大な影響を与える可能性があります！", "error")
            rich_ui.print_message("   十分注意して、本当に必要な場合のみ実行してください。", "error")
            
            # 重要リスクの場合は追加の確認
            rich_ui.print_message("   この操作を実行すると、以下のリスクがあります:", "error")
            rich_ui.print_message("   - システムファイルの破損", "muted")
            rich_ui.print_message("   - セキュリティの脆弱性", "muted")
            rich_ui.print_message("   - データの損失", "muted")
    
    def _show_preview(self, preview: str) -> None:
        """プレビューを表示
        
        Args:
            preview: プレビュー内容
        """
        rich_ui.print_panel(preview, "📄 プレビュー", "blue")
    
    def _get_user_response(self) -> bool:
        """ユーザーの応答を取得
        
        Returns:
            bool: 承認の場合True、拒否の場合False
        """
        while True:
            try:
                # rich_uiのget_confirmationを使用
                response = rich_ui.get_confirmation("実行しますか？", default=False)
                return response
                
            except KeyboardInterrupt:
                # Ctrl+Cは拒否として扱う
                return False
            except Exception as e:
                rich_ui.print_error(f"入力エラー: {e}")
                rich_ui.print_message("もう一度お答えください。", "info")
                continue
    
    def _format_risk_level(self, risk_level: RiskLevel) -> str:
        """リスクレベルを分かりやすく整形
        
        Args:
            risk_level: リスクレベル
            
        Returns:
            str: 整形されたリスクレベル
        """
        risk_formats = {
            RiskLevel.LOW_RISK: "🟢 低リスク",
            RiskLevel.HIGH_RISK: "🟡 高リスク", 
            RiskLevel.CRITICAL_RISK: "🔴 重要リスク"
        }
        
        return risk_formats.get(risk_level, f"❓ 不明 ({risk_level.value})")
    
    def show_approval_summary(self, approved_count: int, rejected_count: int, 
                            total_time: float) -> None:
        """承認セッションのサマリーを表示
        
        Args:
            approved_count: 承認された操作数
            rejected_count: 拒否された操作数
            total_time: 総時間（秒）
        """
        total_operations = approved_count + rejected_count
        
        if total_operations == 0:
            return
        
        summary = f"""
**承認セッション サマリー**

総操作数: {total_operations}
✅ 承認: {approved_count}
🙅 拒否: {rejected_count}
⏱️ 総時間: {total_time:.1f}秒

承認率: {(approved_count / total_operations * 100):.1f}%
        """
        
        rich_ui.print_panel(summary.strip(), "📊 セッション結果", "cyan")
    
    def show_bypass_warning(self, attempt_count: int, max_attempts: int) -> None:
        """バイパス試行警告を表示
        
        Args:
            attempt_count: 現在の試行回数
            max_attempts: 最大試行回数
        """
        remaining = max_attempts - attempt_count
        
        warning_msg = f"""
🚨 **セキュリティ警告**

承認システムのバイパス試行を検出しました。

現在の試行回数: {attempt_count}/{max_attempts}
残り試行回数: {remaining}

これ以上のバイパス試行が検出された場合、
セキュリティのため操作が完全に拒否されます。
        """
        
        rich_ui.print_panel(warning_msg.strip(), "⚠️ セキュリティ警告", "error")
    
    def show_timeout_warning(self, timeout_seconds: int) -> None:
        """タイムアウト警告を表示
        
        Args:
            timeout_seconds: タイムアウト時間（秒）
        """
        warning_msg = f"""
⏰ **タイムアウト警告**

承認要求は {timeout_seconds} 秒でタイムアウトします。
時間内に応答がない場合、操作は自動的に拒否されます。

安全のため、十分検討してから応答してください。
        """
        
        rich_ui.print_panel(warning_msg.strip(), "⏰ タイムアウト警告", "warning")
    
    def show_error_message(self, error_message: str, suggestion: Optional[str] = None) -> None:
        """エラーメッセージを相棒らしく表示
        
        Args:
            error_message: エラーメッセージ
            suggestion: 提案（オプション）
        """
        rich_ui.print_message("😅 あれ？何かうまくいかなかったようです...", "error")
        rich_ui.print_message(f"エラー: {error_message}", "error")
        
        if suggestion:
            rich_ui.print_message(f"💡 提案: {suggestion}", "info")
        
        rich_ui.print_message("もう一度試してみましょうか？", "info") 
   
    def _format_risk_level(self, risk_level: RiskLevel) -> str:
        """リスクレベルを表示用にフォーマット
        
        Args:
            risk_level: リスクレベル
            
        Returns:
            str: フォーマットされたリスクレベル文字列
        """
        risk_formats = {
            RiskLevel.LOW_RISK: "🟢 低リスク",
            RiskLevel.MEDIUM_RISK: "🟡 中リスク", 
            RiskLevel.HIGH_RISK: "🟠 高リスク",
            RiskLevel.CRITICAL_RISK: "🔴 重要リスク"
        }
        
        return risk_formats.get(risk_level, "❓ 不明なリスク")


class NonInteractiveApprovalUI:
    """非対話型の承認UI

    - 対話入力ができない環境向けに、自動で承認/拒否を決定する
    - 既定: 低リスクは自動承認、高リスク以上は拒否
    - 環境変数で緩和可能:
        - APPROVAL_AUTO_APPROVE_ALL=1 → すべて承認
        - APPROVAL_AUTO_APPROVE_HIGH=1 → 高リスクも承認（CRITICALは拒否）
    """

    def __init__(self, auto_low: bool = True, auto_high: bool = False, auto_all: bool = False):
        self.auto_low = auto_low
        self.auto_high = auto_high
        self.auto_all = auto_all

    def show_approval_request(self, request: ApprovalRequest) -> ApprovalResponse:
        import os
        risk = request.operation_info.risk_level
        # 環境変数で上書き可能
        env_all = os.getenv("APPROVAL_AUTO_APPROVE_ALL") == "1"
        env_high = os.getenv("APPROVAL_AUTO_APPROVE_HIGH") == "1"

        approved = False
        reason = None

        if self.auto_all or env_all:
            approved = True
            reason = "AUTO_APPROVE_ALL"
        elif risk == RiskLevel.LOW_RISK and self.auto_low:
            approved = True
            reason = "LOW_RISK_AUTO_APPROVE"
        elif risk == RiskLevel.HIGH_RISK and (self.auto_high or env_high):
            approved = True
            reason = "HIGH_RISK_AUTO_APPROVE"
        else:
            approved = False
            reason = f"non_interactive_reject:{getattr(risk, 'value', str(risk))}"

        return ApprovalResponse(approved=approved, reason=reason)
