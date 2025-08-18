"""
SimpleApprovalGate - シンプル承認システム
現在の複雑な承認システムを置き換える、設定ベースのシンプルな承認機能
LLM強化承認: 自然言語での承認回答処理をサポート
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)


class ApprovalMode(Enum):
    """承認モード"""
    STANDARD = "standard"       # 標準承認
    STRICT = "strict"          # 厳格承認
    TRUSTED = "trusted"        # 信頼モード（低リスクは自動承認）


class RiskLevel(Enum):
    """リスクレベル"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ApprovalRequest:
    """承認要求"""
    operation: str              # 操作名
    description: str            # 操作説明
    target: str                 # 対象（ファイルパス等）
    risk_level: RiskLevel = RiskLevel.MEDIUM  # リスクレベル
    details: Optional[str] = None  # 詳細情報


@dataclass 
class ApprovalResult:
    """承認結果"""
    approved: bool
    reason: str
    timestamp: datetime


class SimpleApprovalGate:
    """シンプル承認ゲート"""
    
    def __init__(self, mode_override: Optional[ApprovalMode] = None, llm_enabled: bool = True):
        # config.yamlから設定を読み込み
        self.config = self._load_config()
        self.approval_history: List[ApprovalResult] = []
        self.llm_enabled = llm_enabled

        # mode_overrideがあればconfigを上書き
        if mode_override:
            self.config['mode'] = mode_override.value
        
        # Rich UI統合
        try:
            from codecrafter.ui.rich_ui import rich_ui
            self.ui = rich_ui
            logger.info("Rich UI統合成功")
        except ImportError as e:
            self.ui = None  # フォールバック: 標準入力使用
            logger.warning(f"Rich UI読み込み失敗、フォールバックモード: {e}")
        
        # LLM承認ハンドラーの初期化
        self.llm_handler = None
        if self.llm_enabled:
            try:
                from .llm_choice.approval_response_handler import LLMApprovalResponseHandler
                self.llm_handler = LLMApprovalResponseHandler()
                logger.info("LLM承認ハンドラー初期化成功")
            except ImportError as e:
                logger.warning(f"LLM承認ハンドラー読み込み失敗: {e}")
                self.llm_enabled = False
    
    def _load_config(self) -> Dict[str, Any]:
        """config.yamlから承認設定を読み込み"""
        try:
            from codecrafter.base.config import config_manager
            config = config_manager.config.get('approval', {})
            logger.info(f"承認設定読み込み成功: {config}")
            return config
        except Exception as e:
            logger.warning(f"設定読み込み失敗、フォールバック設定使用: {e}")
            # フォールバック設定
            return {
                'mode': 'standard',
                'timeout_seconds': 30,
                'show_preview': True,
                'max_preview_length': 200,
                'ui': {
                    'non_interactive': False,
                    'auto_approve_low': False,
                    'auto_approve_high': False,
                    'auto_approve_all': False
                }
            }
    
    def request_approval(self, request: ApprovalRequest) -> ApprovalResult:
        """承認要求処理"""
        logger.info(f"承認要求: {request.operation} (リスク: {request.risk_level.value})")
        
        try:
            mode = ApprovalMode(self.config.get('mode', 'standard'))
        except ValueError:
            mode = ApprovalMode.STANDARD # 不正な値の場合はデフォルト
        
        ui_config = self.config.get('ui', {})
        
        # 全自動承認が有効な場合
        if ui_config.get('auto_approve_all', False):
            return self._auto_approve(request, "全自動承認設定")
        
        # リスクレベル別自動承認
        if request.risk_level == RiskLevel.LOW and ui_config.get('auto_approve_low', False):
            return self._auto_approve(request, "低リスク自動承認")
        
        if request.risk_level == RiskLevel.HIGH and ui_config.get('auto_approve_high', False):
            return self._auto_approve(request, "高リスク自動承認")
        
        # 承認モード別処理
        if mode == ApprovalMode.TRUSTED and request.risk_level == RiskLevel.LOW:
            return self._auto_approve(request, "信頼モード - 低リスク自動承認")
        elif mode == ApprovalMode.STRICT:
            return self._strict_approval(request)
        else:  # STANDARD
            return self._standard_approval(request)
    
    async def request_approval_llm_enhanced(self, request: ApprovalRequest) -> ApprovalResult:
        """LLM強化承認要求処理
        
        Args:
            request: 承認要求
            
        Returns:
            ApprovalResult: 承認結果（LLM解釈含む）
        """
        logger.info(f"LLM強化承認要求: {request.operation} (リスク: {request.risk_level.value})")
        
        try:
            mode = ApprovalMode(self.config.get('mode', 'standard'))
        except ValueError:
            mode = ApprovalMode.STANDARD
        
        ui_config = self.config.get('ui', {})
        
        # 自動承認ロジックは既存と同じ
        if ui_config.get('auto_approve_all', False):
            return self._auto_approve(request, "全自動承認設定")
        
        if request.risk_level == RiskLevel.LOW and ui_config.get('auto_approve_low', False):
            return self._auto_approve(request, "低リスク自動承認")
        
        if request.risk_level == RiskLevel.HIGH and ui_config.get('auto_approve_high', False):
            return self._auto_approve(request, "高リスク自動承認")
        
        if mode == ApprovalMode.TRUSTED and request.risk_level == RiskLevel.LOW:
            return self._auto_approve(request, "信頼モード - 低リスク自動承認")
        
        # 手動承認はLLM強化版を使用
        if mode == ApprovalMode.STRICT:
            return await self._strict_approval_llm_enhanced(request)
        else:  # STANDARD
            return await self._standard_approval_llm_enhanced(request)
    
    def _standard_approval(self, request: ApprovalRequest) -> ApprovalResult:
        """標準承認処理"""
        return self._manual_approval(request)
    
    async def _standard_approval_llm_enhanced(self, request: ApprovalRequest) -> ApprovalResult:
        """LLM強化標準承認処理"""
        return await self._manual_approval_llm_enhanced(request)
    
    def _strict_approval(self, request: ApprovalRequest) -> ApprovalResult:
        """厳格承認処理（詳細確認付き）"""
        # 厳格モードでは詳細情報を必須表示
        if not request.details:
            request.details = "詳細情報なし - 厳格モードでは特に注意が必要"
        
        result = self._manual_approval(request)
        
        # 厳格モードでは承認後に再確認
        if result.approved and request.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]:
            logger.info("厳格モード: 最終確認実行")
            try:
                if self.ui:
                    reconfirm = self.ui.get_confirmation("⚠️ 厳格モード: 本当に実行しますか？ (最終確認)")
                else:
                    reconfirm_input = input("⚠️ 厳格モード: 本当に実行しますか？ (y/n): ").strip().lower()
                    reconfirm = reconfirm_input in ['y', 'yes', 'はい']
                
                if not reconfirm:
                    logger.info("厳格モード: 最終確認で拒否")
                    return ApprovalResult(
                        approved=False,
                        reason="厳格モード - 最終確認で拒否",
                        timestamp=datetime.now()
                    )
            except Exception as e:
                logger.error(f"最終確認エラー: {e}")
                return ApprovalResult(
                    approved=False,
                    reason=f"最終確認エラー: {e}",
                    timestamp=datetime.now()
                )
        
        return result
    
    async def _strict_approval_llm_enhanced(self, request: ApprovalRequest) -> ApprovalResult:
        """LLM強化厳格承認処理（詳細確認付き）"""
        # 厳格モードでは詳細情報を必須表示
        if not request.details:
            request.details = "詳細情報なし - 厳格モードでは特に注意が必要"
        
        result = await self._manual_approval_llm_enhanced(request)
        
        # 厳格モードでは承認後に再確認
        if result.approved and request.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]:
            logger.info("厳格モード: 最終確認実行")
            try:
                if self.ui:
                    reconfirm = self.ui.get_confirmation("⚠️ 厳格モード: 本当に実行しますか？ (最終確認)")
                else:
                    reconfirm_input = input("⚠️ 厳格モード: 本当に実行しますか？ (y/n): ").strip().lower()
                    reconfirm = reconfirm_input in ['y', 'yes', 'はい']
                
                if not reconfirm:
                    logger.info("厳格モード: 最終確認で拒否")
                    return ApprovalResult(
                        approved=False,
                        reason="厳格モード - 最終確認で拒否",
                        timestamp=datetime.now()
                    )
            except Exception as e:
                logger.error(f"最終確認エラー: {e}")
                return ApprovalResult(
                    approved=False,
                    reason=f"最終確認エラー: {e}",
                    timestamp=datetime.now()
                )
        
        return result
    
    def _manual_approval(self, request: ApprovalRequest) -> ApprovalResult:
        """手動承認処理"""
        try:
            # 非対話UIモードの確認
            ui_config = self.config.get('ui', {})
            if ui_config.get('non_interactive', False):
                # 非対話モードでは自動拒否（安全のため）
                logger.info("非対話モード: 自動拒否")
                return ApprovalResult(
                    approved=False,
                    reason="非対話モード - 手動承認が必要な操作は拒否",
                    timestamp=datetime.now()
                )
            
            # Rich UI使用
            if self.ui:
                approved = self._rich_ui_approval(request)
            else:
                approved = self._fallback_approval(request)
            
            result = ApprovalResult(
                approved=approved,
                reason="ユーザー判断" if approved else "ユーザー拒否",
                timestamp=datetime.now()
            )
            
            self.approval_history.append(result)
            logger.info(f"手動承認結果: {approved} ({result.reason})")
            return result
            
        except Exception as e:
            # エラー時は安全のため拒否
            logger.error(f"承認処理エラー: {e}")
            return ApprovalResult(
                approved=False,
                reason=f"承認処理エラー: {e}",
                timestamp=datetime.now()
            )
    
    async def _manual_approval_llm_enhanced(self, request: ApprovalRequest) -> ApprovalResult:
        """LLM強化手動承認処理"""
        try:
            # 非対話UIモードの確認
            ui_config = self.config.get('ui', {})
            if ui_config.get('non_interactive', False):
                # 非対話モードでは自動拒否（安全のため）
                logger.info("非対話モード: 自動拒否")
                return ApprovalResult(
                    approved=False,
                    reason="非対話モード - 手動承認が必要な操作は拒否",
                    timestamp=datetime.now()
                )
            
            # LLMハンドラーが利用可能かつ有効な場合
            if self.llm_enabled and self.llm_handler:
                approved = await self._llm_enhanced_approval(request)
            else:
                # フォールバック: 通常の承認処理
                logger.info("LLM無効またはハンドラー無し、通常承認にフォールバック")
                if self.ui:
                    approved = self._rich_ui_approval(request)
                else:
                    approved = self._fallback_approval(request)
            
            result = ApprovalResult(
                approved=approved,
                reason="LLM強化ユーザー判断" if approved else "LLM強化ユーザー拒否",
                timestamp=datetime.now()
            )
            
            self.approval_history.append(result)
            logger.info(f"LLM強化手動承認結果: {approved} ({result.reason})")
            return result
            
        except Exception as e:
            # エラー時は安全のため拒否
            logger.error(f"LLM強化承認処理エラー: {e}")
            return ApprovalResult(
                approved=False,
                reason=f"LLM強化承認処理エラー: {e}",
                timestamp=datetime.now()
            )
    
    async def _llm_enhanced_approval(self, request: ApprovalRequest) -> bool:
        """LLM強化承認処理
        
        Args:
            request: 承認要求
            
        Returns:
            bool: 承認結果
        """
        try:
            # OperationInfoを構築
            from .llm_choice.approval_response_handler import OperationInfo
            
            operation_info = OperationInfo(
                operation_type=request.operation,
                description=request.description,
                target=request.target,
                risk_level=request.risk_level.value,
                details=request.details or "",
                alternatives=[]  # 現在は代替案サポートなし
            )
            
            # 承認UIを表示
            if self.ui:
                self._display_llm_approval_ui(request)
            else:
                self._display_fallback_approval_ui(request)
            
            # ユーザー入力を取得
            if self.ui:
                user_response = self.ui.get_user_input("承認回答を入力してください (自然な表現で):")
            else:
                user_response = input("承認回答を入力してください: ").strip()
            
            # LLMで解釈
            interpretation = await self.llm_handler.interpret_approval_response(
                user_response, operation_info
            )
            
            # 確認が必要な場合
            if interpretation.clarification_needed or interpretation.confidence < 0.7:
                logger.info(f"承認解釈の確認が必要: 確信度={interpretation.confidence:.2f}")
                
                # 解釈確認メッセージを表示
                confirmation_msg = self.llm_handler.format_approval_confirmation(
                    interpretation, operation_info
                )
                
                if self.ui:
                    self.ui.print_message(confirmation_msg, "question")
                    confirmed = self.ui.get_confirmation("この解釈で正しいですか？")
                else:
                    print(confirmation_msg)
                    confirmed_input = input("この解釈で正しいですか？ (y/n): ").strip().lower()
                    confirmed = confirmed_input in ['y', 'yes', 'はい']
                
                if not confirmed:
                    logger.info("ユーザーが解釈を拒否、承認拒否")
                    return False
            
            # 承認結果を返す
            approved = interpretation.approved
            logger.info(f"LLM承認解釈結果: {interpretation.decision.value} (承認: {approved})")
            
            return approved
            
        except Exception as e:
            logger.error(f"LLM強化承認エラー: {e}")
            # エラー時はフォールバック
            logger.info("LLMエラー、標準承認にフォールバック")
            if self.ui:
                return self._rich_ui_approval(request)
            else:
                return self._fallback_approval(request)
    
    def _display_llm_approval_ui(self, request: ApprovalRequest):
        """LLM承認用のUI表示"""
        try:
            self.ui.print_header("🤖 LLM強化承認が必要です")
            self.ui.print_message(f"操作: {request.operation}", "info")
            self.ui.print_message(f"対象: {request.target}", "info") 
            self.ui.print_message(f"説明: {request.description}", "info")
            
            # config.yamlの設定に基づくプレビュー表示
            if self.config.get('show_preview', True) and request.details:
                max_length = self.config.get('max_preview_length', 200)
                details_preview = request.details[:max_length]
                if len(request.details) > max_length:
                    details_preview += "...(省略)"
                self.ui.print_message(f"詳細: {details_preview}", "muted")
            
            # リスクレベル表示（色分け）
            risk_color = {
                RiskLevel.LOW: "info",
                RiskLevel.MEDIUM: "warning",
                RiskLevel.HIGH: "error"
            }.get(request.risk_level, "info")
            
            self.ui.print_message(f"リスク: {request.risk_level.value.upper()}", risk_color)
            
            # LLM機能の説明
            self.ui.print_message("\n💡 自然な言葉で回答できます:", "muted")
            self.ui.print_message("例: 「はい」「実行して」「やめておく」「安全に実行」など", "muted")
            
        except Exception as e:
            logger.error(f"LLM承認UI表示エラー: {e}")
    
    def _display_fallback_approval_ui(self, request: ApprovalRequest):
        """フォールバック承認用のUI表示"""
        try:
            print("\n" + "="*60)
            print("🤖 LLM強化承認が必要です")
            print(f"操作: {request.operation}")
            print(f"対象: {request.target}")
            print(f"説明: {request.description}")
            if request.details:
                max_length = self.config.get('max_preview_length', 200)
                details_preview = request.details[:max_length]
                if len(request.details) > max_length:
                    details_preview += "...(省略)"
                print(f"詳細: {details_preview}")
            print(f"リスク: {request.risk_level.value.upper()}")
            print("\n💡 自然な言葉で回答できます:")
            print("例: 「はい」「実行して」「やめておく」「安全に実行」など")
            print("="*60)
            
        except Exception as e:
            logger.error(f"フォールバック承認UI表示エラー: {e}")
    
    def _rich_ui_approval(self, request: ApprovalRequest) -> bool:
        """Rich UI承認"""
        try:
            self.ui.print_header("🔐 承認が必要です")
            self.ui.print_message(f"操作: {request.operation}", "info")
            self.ui.print_message(f"対象: {request.target}", "info")
            self.ui.print_message(f"説明: {request.description}", "info")
            
            # config.yamlの設定に基づくプレビュー表示
            if self.config.get('show_preview', True) and request.details:
                max_length = self.config.get('max_preview_length', 200)
                details_preview = request.details[:max_length]
                if len(request.details) > max_length:
                    details_preview += "...(省略)"
                self.ui.print_message(f"詳細: {details_preview}", "muted")
            
            # リスクレベル表示（色分け）
            risk_color = {
                RiskLevel.LOW: "info",
                RiskLevel.MEDIUM: "warning", 
                RiskLevel.HIGH: "error"
            }.get(request.risk_level, "info")
            
            self.ui.print_message(f"リスク: {request.risk_level.value.upper()}", risk_color)
            
            # タイムアウト設定（現在のRich UIは未対応のため参考値として取得）
            timeout = self.config.get('timeout_seconds', 30)
            
            return self.ui.get_confirmation("実行を承認しますか？")
            
        except Exception as e:
            logger.error(f"Rich UI承認エラー: {e}")
            # Rich UIエラー時はフォールバック
            return self._fallback_approval(request)
    
    def _fallback_approval(self, request: ApprovalRequest) -> bool:
        """フォールバック承認（標準入力）"""
        try:
            print("\n" + "="*50)
            print("🔐 承認が必要です")
            print(f"操作: {request.operation}")
            print(f"対象: {request.target}")
            print(f"説明: {request.description}")
            if request.details:
                max_length = self.config.get('max_preview_length', 200)
                details_preview = request.details[:max_length]
                if len(request.details) > max_length:
                    details_preview += "...(省略)"
                print(f"詳細: {details_preview}")
            print(f"リスク: {request.risk_level.value.upper()}")
            print("="*50)
            
            while True:
                response = input("実行を承認しますか？ (y/n): ").strip().lower()
                if response in ['y', 'yes', 'はい']:
                    return True
                elif response in ['n', 'no', 'いいえ']:
                    return False
                else:
                    print("y（はい）またはn（いいえ）を入力してください。")
                    
        except Exception as e:
            logger.error(f"フォールバック承認エラー: {e}")
            # 最終的なエラー時は安全のため拒否
            return False
    
    def _auto_approve(self, request: ApprovalRequest, reason: str) -> ApprovalResult:
        """自動承認"""
        result = ApprovalResult(
            approved=True,
            reason=reason,
            timestamp=datetime.now()
        )
        self.approval_history.append(result)
        logger.info(f"自動承認: {reason}")
        return result
    
    def get_approval_history(self) -> List[ApprovalResult]:
        """承認履歴取得"""
        return self.approval_history.copy()
    
    def clear_history(self):
        """承認履歴クリア"""
        self.approval_history.clear()
        logger.info("承認履歴をクリアしました")


# 便利関数
def create_approval_request(operation: str, target: str, description: str, 
                          risk_level: RiskLevel = RiskLevel.MEDIUM,
                          details: Optional[str] = None) -> ApprovalRequest:
    """承認要求作成のヘルパー関数"""
    return ApprovalRequest(
        operation=operation,
        description=description,
        target=target,
        risk_level=risk_level,
        details=details
    )


def assess_file_risk(file_path: str) -> RiskLevel:
    """ファイル操作リスク評価のヘルパー関数"""
    # 設定ファイルやシステムファイル
    if file_path.startswith('.') or 'config' in file_path.lower():
        return RiskLevel.HIGH
    
    # 実行可能ファイル
    elif file_path.endswith(('.py', '.js', '.ts', '.sh', '.bat')):
        return RiskLevel.MEDIUM
    
    # ドキュメントファイル
    elif file_path.endswith(('.txt', '.md', '.json', '.yaml', '.yml')):
        return RiskLevel.LOW
    
    # その他
    else:
        return RiskLevel.MEDIUM


# LLM統合用ヘルパー関数
async def create_llm_enhanced_approval_gate(mode_override: Optional[ApprovalMode] = None) -> SimpleApprovalGate:
    """LLM強化承認ゲートの作成ヘルパー"""
    return SimpleApprovalGate(mode_override=mode_override, llm_enabled=True)


def create_standard_approval_gate(mode_override: Optional[ApprovalMode] = None) -> SimpleApprovalGate:
    """標準承認ゲートの作成ヘルパー（LLM無効）"""
    return SimpleApprovalGate(mode_override=mode_override, llm_enabled=False)