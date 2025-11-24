#!/usr/bin/env python3
"""
Phase 4: ConversationGate - 会話内承認システム

設計ドキュメントに従って、以下の機能を実装:
- 5点の情報提供（意図、根拠、影響、代替、差分プレビュー）
- リスクレベルの自動判定
- 承認履歴の記録と分析
- 会話内での自然な承認フロー
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path

from .specialized_prompt_generator import SpecializedPromptGenerator
from .llm_call_manager import LLMCallManager
from ..config.config_manager import config_manager
from ..ui import print_table, print_panel


class RiskLevel(Enum):
    """リスクレベルの定義"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(Enum):
    """承認ステータスの定義"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ApprovalContext:
    """承認コンテキスト"""
    user_id: str
    session_id: str
    timestamp: datetime
    operation_type: str
    target_path: Optional[str] = None
    description: str = ""
    estimated_impact: str = ""


@dataclass
class ApprovalRequest:
    """承認リクエスト"""
    request_id: str
    context: ApprovalContext
    risk_level: RiskLevel
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = None
    expires_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.expires_at is None:
            # 5分後の時刻を計算（timedeltaを使用）
            from datetime import timedelta
            self.expires_at = self.created_at + timedelta(minutes=5)


@dataclass
class ApprovalResponse:
    """承認レスポンス"""
    request_id: str
    user_response: str
    approved: bool
    timestamp: datetime
    reasoning: str = ""
    additional_notes: str = ""


@dataclass
class ApprovalHistory:
    """承認履歴"""
    request_id: str
    context: ApprovalContext
    risk_level: RiskLevel
    approval_status: ApprovalStatus
    user_response: str
    reasoning: str
    created_at: datetime
    completed_at: datetime
    processing_time_seconds: float


class ConversationGate:
    """会話内承認システム - Phase 4実装"""
    
    def __init__(self, work_dir: str = "./work", max_history: int = 100):
        self.logger = logging.getLogger(__name__)
        # 設定反映
        cfg = config_manager.get_config()
        configured_work_dir = getattr(cfg, 'work_directory', work_dir)
        self.work_dir = Path(configured_work_dir or work_dir)
        self.max_history = max_history
        
        # 承認履歴の保存ディレクトリ
        self.history_dir = self.work_dir / "approval_history"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        
        # システムコンポーネント
        self.specialized_generator = SpecializedPromptGenerator()
        self.llm_manager = LLMCallManager()
        
        # 承認履歴
        self.approval_history: List[ApprovalHistory] = []
        self.pending_requests: Dict[str, ApprovalRequest] = {}
        
        # 設定
        self.auto_approval_threshold = RiskLevel.LOW
        self.require_explicit_approval = [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        self.timeout_seconds = 300  # 5分

        try:
            approval_cfg = getattr(cfg, 'approval', {}) or {}
            if isinstance(approval_cfg, dict):
                # タイムアウト
                self.timeout_seconds = int(approval_cfg.get('timeout_seconds', self.timeout_seconds))
                # 自動承認しきい値（UI設定から導出）
                ui_cfg = approval_cfg.get('ui', {}) or {}
                if ui_cfg.get('auto_approve_all', False):
                    self.auto_approval_threshold = RiskLevel.CRITICAL
                elif ui_cfg.get('auto_approve_high', False):
                    self.auto_approval_threshold = RiskLevel.HIGH
                elif ui_cfg.get('auto_approve_low', False):
                    self.auto_approval_threshold = RiskLevel.LOW
                else:
                    # 明示設定が無ければ安全側に寄せる
                    self.auto_approval_threshold = RiskLevel.LOW
        except Exception as e:
            self.logger.warning(f"ConversationGate設定の適用に失敗: {e}")
        
        self.logger.info("ConversationGate初期化完了")
    
    def request_approval(self, 
                        user_input: str, 
                        operation_type: str,
                        target_path: Optional[str] = None,
                        user_id: str = "default",
                        session_id: str = "default") -> ApprovalRequest:
        """承認リクエストを作成"""
        try:
            # リスクレベルを自動判定
            risk_level = self._assess_risk_level(user_input, operation_type, target_path)
            
            # 自動承認の判定
            risk_levels = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
            current_index = risk_levels.index(risk_level)
            threshold_index = risk_levels.index(self.auto_approval_threshold)
            
            if current_index <= threshold_index:
                self.logger.info(f"自動承認: リスクレベル {risk_level.value} <= {self.auto_approval_threshold.value}")
                return self._create_auto_approved_request(
                    user_input, operation_type, target_path, user_id, session_id, risk_level
                )
            
            # 手動承認が必要
            return self._create_manual_approval_request(
                user_input, operation_type, target_path, user_id, session_id, risk_level
            )
            
        except Exception as e:
            self.logger.error(f"承認リクエスト作成に失敗: {e}")
            raise
    
    def _assess_risk_level(self, user_input: str, operation_type: str, target_path: Optional[str]) -> RiskLevel:
        """リスクレベルを自動判定"""
        try:
            # 基本リスク判定
            base_risk = self._get_base_risk(operation_type)
            
            # パスベースのリスク判定
            path_risk = self._assess_path_risk(target_path) if target_path else RiskLevel.LOW
            
            # 入力内容のリスク判定
            content_risk = self._assess_content_risk(user_input)
            
            # 総合リスク判定（RiskLevelの順序を使用）
            risk_levels = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
            base_index = risk_levels.index(base_risk)
            path_index = risk_levels.index(path_risk)
            content_index = risk_levels.index(content_risk)
            
            # 最も高いリスクレベルを返す
            max_index = max(base_index, path_index, content_index)
            return risk_levels[max_index]
                
        except Exception as e:
            self.logger.warning(f"リスク判定に失敗、デフォルト値を使用: {e}")
            return RiskLevel.MEDIUM
    
    def _get_base_risk(self, operation_type: str) -> RiskLevel:
        """操作タイプ別の基本リスク"""
        risk_map = {
            'read': RiskLevel.LOW,
            'list': RiskLevel.LOW,
            'info': RiskLevel.LOW,
            'help': RiskLevel.LOW,
            'create': RiskLevel.MEDIUM,
            'edit': RiskLevel.MEDIUM,
            'update': RiskLevel.MEDIUM,
            'delete': RiskLevel.HIGH,
            'execute': RiskLevel.HIGH,
            'system': RiskLevel.CRITICAL,
            'config': RiskLevel.HIGH
        }
        return risk_map.get(operation_type.lower(), RiskLevel.MEDIUM)
    
    def _assess_path_risk(self, target_path: str) -> RiskLevel:
        """パスベースのリスク判定"""
        try:
            path = Path(target_path)
            
            # システムディレクトリの保護
            system_paths = ['/etc', '/usr', '/bin', '/sbin', 'C:\\Windows', 'C:\\System32']
            if any(str(path).startswith(sys_path) for sys_path in system_paths):
                return RiskLevel.CRITICAL
            
            # 作業ディレクトリ外の操作
            if not path.is_relative_to(self.work_dir):
                return RiskLevel.HIGH
            
            # 隠しファイル・ディレクトリ
            if any(part.startswith('.') for part in path.parts):
                return RiskLevel.MEDIUM
            
            return RiskLevel.LOW
            
        except Exception:
            return RiskLevel.MEDIUM
    
    def _assess_content_risk(self, user_input: str) -> RiskLevel:
        """入力内容のリスク判定"""
        input_lower = user_input.lower()
        
        # 危険なキーワード
        dangerous_keywords = ['delete', 'remove', 'rm', 'format', 'wipe', 'clear', 'reset']
        if any(keyword in input_lower for keyword in dangerous_keywords):
            return RiskLevel.HIGH
        
        # システム操作
        system_keywords = ['sudo', 'admin', 'root', 'system', 'config']
        if any(keyword in input_lower for keyword in system_keywords):
            return RiskLevel.MEDIUM
        
        return RiskLevel.LOW
    
    def _create_auto_approved_request(self, 
                                    user_input: str, 
                                    operation_type: str,
                                    target_path: Optional[str],
                                    user_id: str,
                                    session_id: str,
                                    risk_level: RiskLevel) -> ApprovalRequest:
        """自動承認リクエストを作成"""
        context = ApprovalContext(
            user_id=user_id,
            session_id=session_id,
            timestamp=datetime.now(),
            operation_type=operation_type,
            target_path=target_path,
            description=user_input[:100],
            estimated_impact="低リスク操作のため自動承認"
        )
        
        request = ApprovalRequest(
            request_id=f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            context=context,
            risk_level=risk_level,
            approval_status=ApprovalStatus.APPROVED
        )
        
        # 履歴に記録
        self._record_approval_history(request, "自動承認", "低リスク操作")
        
        return request
    
    def _create_manual_approval_request(self, 
                                      user_input: str, 
                                      operation_type: str,
                                      target_path: Optional[str],
                                      user_id: str,
                                      session_id: str,
                                      risk_level: RiskLevel) -> ApprovalRequest:
        """手動承認リクエストを作成"""
        context = ApprovalContext(
            user_id=user_id,
            session_id=session_id,
            timestamp=datetime.now(),
            operation_type=operation_type,
            target_path=target_path,
            description=user_input[:100],
            estimated_impact=self._estimate_operation_impact(operation_type, target_path)
        )
        
        request = ApprovalRequest(
            request_id=f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            context=context,
            risk_level=risk_level
        )
        
        # 保留中リクエストに追加
        self.pending_requests[request.request_id] = request
        
        return request
    
    def _estimate_operation_impact(self, operation_type: str, target_path: Optional[str]) -> str:
        """操作の影響を推定"""
        if operation_type == 'delete':
            return f"ファイル '{target_path}' の完全削除"
        elif operation_type == 'edit':
            return f"ファイル '{target_path}' の内容変更"
        elif operation_type == 'create':
            return f"新規ファイル '{target_path}' の作成"
        elif operation_type == 'execute':
            return "コードの実行（システムへの影響の可能性）"
        else:
            return "低影響の操作"
    
    def generate_approval_prompt(self, request: ApprovalRequest) -> str:
        """承認プロンプトを生成（5点の情報提供）"""
        try:
            # 専門的プロンプト生成器を使用
            specialized_prompt = self.specialized_generator.generate("REVIEW", {
                'operation_type': request.context.operation_type,
                'target_path': request.context.target_path,
                'risk_level': request.risk_level.value
            })
            
            # 5点の情報を構築
            five_points = self._build_five_points(request)
            
            prompt = f"""
{specialized_prompt}

🛡️ **承認が必要な操作について確認をお願いします**

📋 **操作の詳細**
- 操作タイプ: {request.context.operation_type.upper()}
- 対象: {request.context.target_path or '指定なし'}
- リスクレベル: {request.risk_level.value.upper()}
- 説明: {request.context.description}

{five_points}

⏰ **承認期限**: {request.expires_at.strftime('%H:%M:%S')} まで

**承認する場合は「承認」または「yes」、拒否する場合は「拒否」または「no」と入力してください。**

💡 **詳細情報が必要な場合は「詳細」と入力してください。**
"""
            return prompt.strip()
            
        except Exception as e:
            self.logger.error(f"承認プロンプト生成に失敗: {e}")
            return self._generate_fallback_prompt(request)
    
    def _build_five_points(self, request: ApprovalRequest) -> str:
        """5点の情報を構築"""
        try:
            # LLMを使用して5点の情報を生成
            llm_prompt = f"""
以下の操作について、承認判断に必要な5点の情報を生成してください：

操作: {request.context.operation_type}
対象: {request.context.target_path or '指定なし'}
説明: {request.context.description}
リスクレベル: {request.risk_level.value}

以下の形式で回答してください：
1. 意図: [操作の目的と意図]
2. 根拠: [この操作が必要な理由]
3. 影響: [操作による影響範囲]
4. 代替: [代替手段の有無]
5. 差分: [変更前後の差分予測]
"""
            
            response = self.llm_manager.call_llm(llm_prompt, expected_format="text")
            llm_content = response.get('content', '')
            
            if llm_content and len(llm_content) > 50:
                return llm_content
            
        except Exception as e:
            self.logger.warning(f"LLMによる5点情報生成に失敗、フォールバック使用: {e}")
        
        # フォールバック: 基本的な5点情報
        return self._generate_fallback_five_points(request)
    
    def _generate_fallback_five_points(self, request: ApprovalRequest) -> str:
        """フォールバック用の5点情報生成"""
        operation_type = request.context.operation_type
        target_path = request.context.target_path or "指定なし"
        
        five_points = f"""
🔍 **承認判断のための5点情報**

1. **意図**: {operation_type}操作の実行
   - ユーザーの要求: {request.context.description}

2. **根拠**: ユーザーからの明示的な要求
   - 操作タイプ: {operation_type}
   - 対象パス: {target_path}

3. **影響**: {self._estimate_operation_impact(operation_type, target_path)}
   - リスクレベル: {request.risk_level.value.upper()}

4. **代替**: 操作の実行を延期または変更
   - より安全な方法の検討
   - 段階的な実行

5. **差分**: 操作前後の状態変化
   - 実行前: 現在の状態
   - 実行後: 要求された変更が適用された状態
"""
        return five_points
    
    def _generate_fallback_prompt(self, request: ApprovalRequest) -> str:
        """フォールバック用の承認プロンプト"""
        return f"""
🛡️ **承認が必要な操作**

操作: {request.context.operation_type}
対象: {request.context.target_path or '指定なし'}
リスクレベル: {request.risk_level.value.upper()}

この操作を実行してもよろしいですか？

承認: 「承認」または「yes」
拒否: 「拒否」または「no」
詳細: 「詳細」

⏰ 期限: {request.expires_at.strftime('%H:%M:%S')}
"""
    
    def process_approval_response(self, request_id: str, user_response: str) -> ApprovalResponse:
        """承認レスポンスを処理"""
        try:
            if request_id not in self.pending_requests:
                raise ValueError(f"承認リクエスト {request_id} が見つかりません")
            
            request = self.pending_requests[request_id]
            
            # タイムアウトチェック
            if datetime.now() > request.expires_at:
                request.approval_status = ApprovalStatus.EXPIRED
                self._record_approval_history(request, "タイムアウト", "承認期限切れ")
                return ApprovalResponse(
                    request_id=request_id,
                    user_response=user_response,
                    approved=False,
                    timestamp=datetime.now(),
                    reasoning="承認期限切れ"
                )
            
            # ユーザー応答の解析
            approved, reasoning = self._parse_user_response(user_response)
            
            # 承認ステータスを更新
            request.approval_status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            
            # レスポンスを作成
            response = ApprovalResponse(
                request_id=request_id,
                user_response=user_response,
                approved=approved,
                timestamp=datetime.now(),
                reasoning=reasoning
            )
            
            # 履歴に記録
            self._record_approval_history(request, user_response, reasoning)
            
            # 保留中リクエストから削除
            del self.pending_requests[request_id]
            
            return response
            
        except Exception as e:
            self.logger.error(f"承認レスポンス処理に失敗: {e}")
            raise
    
    def _parse_user_response(self, user_response: str) -> Tuple[bool, str]:
        """ユーザー応答を解析"""
        response_lower = user_response.lower().strip()
        
        # 承認キーワード
        approve_keywords = ['承認', 'yes', 'y', 'ok', '実行', '許可', '承認する']
        if any(keyword in response_lower for keyword in approve_keywords):
            return True, "ユーザーによる明示的な承認"
        
        # 拒否キーワード
        reject_keywords = ['拒否', 'no', 'n', 'キャンセル', '中止', '拒否する']
        if any(keyword in response_lower for keyword in reject_keywords):
            return False, "ユーザーによる明示的な拒否"
        
        # デフォルト: 拒否（安全性重視）
        return False, "不明確な応答のため拒否（安全性重視）"
    
    def _record_approval_history(self, request: ApprovalRequest, user_response: str, reasoning: str):
        """承認履歴を記録"""
        try:
            completed_at = datetime.now()
            processing_time = (completed_at - request.created_at).total_seconds()
            
            history = ApprovalHistory(
                request_id=request.request_id,
                context=request.context,
                risk_level=request.risk_level,
                approval_status=request.approval_status,
                user_response=user_response,
                reasoning=reasoning,
                created_at=request.created_at,
                completed_at=completed_at,
                processing_time_seconds=processing_time
            )
            
            self.approval_history.append(history)
            
            # 履歴ファイルに保存
            self._save_approval_history(history)
            
            # 最大履歴数を超えた場合、古い履歴を削除
            if len(self.approval_history) > self.max_history:
                self.approval_history = self.approval_history[-self.max_history:]
                
        except Exception as e:
            self.logger.error(f"承認履歴の記録に失敗: {e}")
    
    def _save_approval_history(self, history: ApprovalHistory):
        """承認履歴をファイルに保存"""
        try:
            # 日付別ディレクトリ
            date_dir = self.history_dir / history.created_at.strftime('%Y%m%d')
            date_dir.mkdir(exist_ok=True)
            
            # 履歴ファイル
            history_file = date_dir / f"{history.request_id}.json"
            
            # 履歴データを辞書に変換
            history_dict = asdict(history)
            history_dict['created_at'] = history.created_at.isoformat()
            history_dict['completed_at'] = history.completed_at.isoformat()
            history_dict['context']['timestamp'] = history.context.timestamp.isoformat()
            
            # JSONファイルに保存
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history_dict, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(f"承認履歴のファイル保存に失敗: {e}")
    
    def get_approval_statistics(self) -> Dict[str, Any]:
        """承認統計を取得"""
        try:
            total_requests = len(self.approval_history)
            if total_requests == 0:
                return {
                    'total_requests': 0,
                    'approval_rate': 0.0,
                    'average_processing_time': 0.0,
                    'risk_level_distribution': {},
                    'status_distribution': {}
                }
            
            # 承認率
            approved_count = sum(1 for h in self.approval_history if h.approval_status == ApprovalStatus.APPROVED)
            approval_rate = (approved_count / total_requests) * 100
            
            # 平均処理時間
            total_processing_time = sum(h.processing_time_seconds for h in self.approval_history)
            average_processing_time = total_processing_time / total_requests
            
            # リスクレベル分布
            risk_level_distribution = {}
            for risk_level in RiskLevel:
                count = sum(1 for h in self.approval_history if h.risk_level == risk_level)
                risk_level_distribution[risk_level.value] = count
            
            # ステータス分布
            status_distribution = {}
            for status in ApprovalStatus:
                count = sum(1 for h in self.approval_history if h.approval_status == status)
                status_distribution[status.value] = count
            
            return {
                'total_requests': total_requests,
                'approval_rate': round(approval_rate, 2),
                'average_processing_time': round(average_processing_time, 2),
                'risk_level_distribution': risk_level_distribution,
                'status_distribution': status_distribution,
                'pending_requests': len(self.pending_requests)
            }
            
        except Exception as e:
            self.logger.error(f"承認統計の取得に失敗: {e}")
            return {}

    def print_statistics(self):
        """承認統計をUIに表示"""
        stats = self.get_approval_statistics()
        headers = ["項目", "値"]
        rows = [
            ["総リクエスト", stats.get('total_requests', 0)],
            ["承認率(%)", stats.get('approval_rate', 0.0)],
            ["平均処理時間(s)", stats.get('average_processing_time', 0.0)],
            ["保留中", stats.get('pending_requests', 0)],
        ]
        print_table(headers, rows, title="ConversationGate 統計")
        # リスク分布とステータス分布
        rl = stats.get('risk_level_distribution', {})
        sd = stats.get('status_distribution', {})
        rl_rows = [[k, v] for k, v in rl.items()]
        sd_rows = [[k, v] for k, v in sd.items()]
        if rl_rows:
            print_table(["リスク", "件数"], rl_rows, title="リスクレベル分布")
        if sd_rows:
            print_table(["ステータス", "件数"], sd_rows, title="ステータス分布")
    
    def get_pending_requests(self) -> List[ApprovalRequest]:
        """保留中の承認リクエストを取得"""
        return list(self.pending_requests.values())
    
    def cleanup_expired_requests(self) -> int:
        """期限切れの承認リクエストをクリーンアップ"""
        try:
            current_time = datetime.now()
            expired_ids = []
            
            for request_id, request in self.pending_requests.items():
                if current_time > request.expires_at:
                    expired_ids.append(request_id)
                    request.approval_status = ApprovalStatus.EXPIRED
                    self._record_approval_history(request, "システム", "期限切れによる自動拒否")
            
            # 期限切れリクエストを削除
            for request_id in expired_ids:
                del self.pending_requests[request_id]
            
            self.logger.info(f"期限切れリクエスト {len(expired_ids)} 件をクリーンアップ")
            return len(expired_ids)
            
        except Exception as e:
            self.logger.error(f"期限切れリクエストのクリーンアップに失敗: {e}")
            return 0
    
    def to_dict(self) -> Dict[str, Any]:
        """システム状態を辞書形式で取得"""
        return {
            'work_dir': str(self.work_dir),
            'max_history': self.max_history,
            'auto_approval_threshold': self.auto_approval_threshold.value,
            'timeout_seconds': self.timeout_seconds,
            'pending_requests_count': len(self.pending_requests),
            'total_history_count': len(self.approval_history),
            'statistics': self.get_approval_statistics()
        }
