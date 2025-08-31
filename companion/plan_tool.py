"""
PlanTool - プラン管理の明示的ツールAPI

設計原則:
- 単一真実源: プラン状態はPlanToolのみが正とする
- 明示性: プランの保存・承認・実行はすべてAPI経由
- 承認必須: 実行は承認済みActionSpecのみに限定
- 安全性: リスク評価・プレフライト・差分プレビューを標準化
"""

import json
import re
import threading
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal, Union
from dataclasses import dataclass, asdict
from enum import Enum

from .collaborative_planner import ActionSpec
from .file_ops import SimpleFileOps


class PlanStatus(Enum):
    """プランの状態"""
    PROPOSED = "proposed"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    EXECUTING = "executing"
    COMPLETED = "completed"
    ABORTED = "aborted"


class RiskLevel(Enum):
    """リスクレベル"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class MessageRef:
    """メッセージ参照"""
    message_id: str
    timestamp: str


@dataclass
class SpecSelection:
    """ActionSpec選択"""
    all: bool = True
    ids: List[str] = None
    
    def __post_init__(self):
        if self.ids is None:
            self.ids = []


@dataclass
class PreflightInfo:
    """プレフライト情報"""
    exists: bool = False
    overwrite: bool = False
    diff_summary: str = ""


@dataclass
class ActionSpecExt:
    """拡張ActionSpec"""
    id: str
    base: ActionSpec
    risk: RiskLevel = RiskLevel.LOW
    validated: bool = False
    preflight: PreflightInfo = None
    notes: str = ""
    
    def __post_init__(self):
        if self.preflight is None:
            self.preflight = PreflightInfo()


@dataclass
class Step:
    """プランのステップ"""
    step_id: str
    name: str
    description: str
    depends_on: List[str]
    status: str = "pending"
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

@dataclass
class Plan:
    """プラン本体"""
    id: str
    title: str
    content: str
    sources: List[MessageRef]
    rationale: str
    tags: List[str]
    created_at: str
    version: int = 1
    steps: List[Step] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if self.steps is None:
            self.steps = []


@dataclass
class ApprovalRecord:
    """承認記録"""
    approver: str
    timestamp: str
    selection: SpecSelection
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class PlanPreview:
    """プランプレビュー"""
    files: List[str]
    diffs: List[Dict[str, str]]  # DiffSummary
    risk_score: float


@dataclass
class PlanState:
    """プラン状態"""
    status: PlanStatus
    action_specs: List[ActionSpecExt]
    selection: SpecSelection
    approvals: List[ApprovalRecord]
    previews: Optional[PlanPreview] = None
    
    def __post_init__(self):
        if self.selection is None:
            self.selection = SpecSelection()
        if self.previews is None:
            self.previews = PlanPreview(files=[], diffs=[], risk_score=0.0)


@dataclass
class ValidationReport:
    """バリデーションレポート"""
    ok: bool
    issues: List[str]
    normalized: List[ActionSpecExt]


@dataclass
class ExecutionResult:
    """実行結果"""
    overall_success: bool
    results: List[Dict[str, Any]]  # FileOpOutcome
    started_at: str
    finished_at: str
    
    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.now().isoformat()
        if not self.finished_at:
            self.finished_at = datetime.now().isoformat()


class PlanTool:
    """プラン管理ツール"""
    
    def __init__(self, logs_dir: str = "logs", file_ops: Optional[SimpleFileOps] = None, 
                 llm_client=None, allow_external_paths: bool = False):
        """初期化
        
        Args:
            logs_dir: ログディレクトリ
            file_ops: ファイル操作インスタンス
            llm_client: LLMクライアント（ステップ生成用）
            allow_external_paths: 外部パスを許可するか（テスト用）
        """
        self.logs_dir = Path(logs_dir)
        self.plans_dir = self.logs_dir / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        
        self.file_ops = file_ops or SimpleFileOps()
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)
        self.allow_external_paths = allow_external_paths
        # スレッド安全のためのロック
        self._lock = threading.RLock()
        
        # インメモリ状態
        self._plans: Dict[str, Plan] = {}
        self._plan_states: Dict[str, PlanState] = {}
        self._current_plan_id: Optional[str] = None
        
        # 起動時にインデックスを読み込み
        self._load_index()
        # ディープデバッグログ（外部から有効化）
        self.enable_deep_plan_logging = False
        try:
            self.logger.info(f"PlanTool init: id={id(self)} logs_dir={self.logs_dir} plans_dir={self.plans_dir} llm_client={llm_client is not None}")
        except Exception:
            pass

    def debug_state(self) -> Dict[str, Any]:
        """現在のPlanTool状態をダンプ（診断用）"""
        try:
            plans_summary = []
            for pid, plan in self._plans.items():
                st = self._plan_states.get(pid)
                plans_summary.append({
                    'id': pid,
                    'title': plan.title,
                    'status': st.status.value if st else 'unknown',
                    'action_count': len(st.action_specs) if st else 0,
                    'created_at': plan.created_at
                })
            state = {
                'self_id': id(self),
                'logs_dir': str(self.logs_dir),
                'plans_dir': str(self.plans_dir),
                'plans_dir_exists': self.plans_dir.exists(),
                'index_exists': (self.plans_dir / 'index.json').exists(),
                'current_plan_id': self._current_plan_id,
                'plans_total': len(self._plans),
                'plans': plans_summary,
            }
            return state
        except Exception as e:
            return {'error': str(e)}

    def _log_debug_state(self, where: str):
        """ディープログが有効な場合に内部状態を出力"""
        try:
            if getattr(self, 'enable_deep_plan_logging', False):
                state = self.debug_state()
                self.logger.info(f"[PlanTool debug] {where}: {state}")
        except Exception:
            pass
    
    def _load_index(self):
        """インデックスファイルから既存プランを読み込み"""
        index_file = self.plans_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
                    
                # 各プランを読み込み
                for plan_ref in index_data.get('plans', []):
                    plan_id = plan_ref['id']
                    self._load_plan(plan_id)
                    
                # 現在のプランIDを復元
                self._current_plan_id = index_data.get('current_plan_id')
                
            except Exception as e:
                self.logger.warning(f"インデックス読み込みエラー: {e}")
    
    def _load_plan(self, plan_id: str):
        """個別プランを読み込み"""
        plan_file = self.plans_dir / plan_id / "plan.json"
        if plan_file.exists():
            try:
                with open(plan_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Planオブジェクトを復元
                plan_data = data['plan']
                plan_data['sources'] = [MessageRef(**src) for src in plan_data['sources']]
                self._plans[plan_id] = Plan(**plan_data)
                
                # PlanStateオブジェクトを復元
                state_data = data['state']
                state_data['status'] = PlanStatus(state_data['status'])
                state_data['selection'] = SpecSelection(**state_data['selection'])
                state_data['approvals'] = [ApprovalRecord(**app) for app in state_data['approvals']]
                
                # ActionSpecExtを復元
                action_specs = []
                for spec_data in state_data['action_specs']:
                    base_spec = ActionSpec(**spec_data['base'])
                    preflight = PreflightInfo(**spec_data['preflight'])
                    action_specs.append(ActionSpecExt(
                        id=spec_data['id'],
                        base=base_spec,
                        risk=RiskLevel(spec_data['risk']),
                        validated=spec_data['validated'],
                        preflight=preflight,
                        notes=spec_data['notes']
                    ))
                state_data['action_specs'] = action_specs
                
                if state_data.get('previews'):
                    state_data['previews'] = PlanPreview(**state_data['previews'])
                
                self._plan_states[plan_id] = PlanState(**state_data)
                
            except Exception as e:
                self.logger.error(f"プラン読み込みエラー {plan_id}: {e}")   
 
    def _save_plan(self, plan_id: str):
        """プランを永続化"""
        plan_dir = self.plans_dir / plan_id
        plan_dir.mkdir(exist_ok=True)
        
        plan_file = plan_dir / "plan.json"
        
        try:
            # データを辞書形式に変換
            plan_data = asdict(self._plans[plan_id])
            state_data = asdict(self._plan_states[plan_id])
            
            # Enumを文字列に変換
            state_data['status'] = state_data['status'].value
            for spec in state_data['action_specs']:
                spec['risk'] = spec['risk'].value
            
            data = {
                'plan': plan_data,
                'state': state_data,
                'updated_at': datetime.now().isoformat()
            }
            
            with open(plan_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            # インデックスを更新
            self._update_index()
            
        except Exception as e:
            self.logger.error(f"プラン保存エラー {plan_id}: {e}")
            raise
    
    def _update_index(self):
        """インデックスファイルを更新"""
        index_file = self.plans_dir / "index.json"
        
        try:
            plans_list = []
            for plan_id, plan in self._plans.items():
                state = self._plan_states.get(plan_id)
                plans_list.append({
                    'id': plan_id,
                    'title': plan.title,
                    'status': state.status.value if state else 'unknown',
                    'created_at': plan.created_at,
                    'tags': plan.tags
                })
            
            # 作成日時でソート（新しい順）
            plans_list.sort(key=lambda x: x['created_at'], reverse=True)
            
            index_data = {
                'plans': plans_list,
                'current_plan_id': self._current_plan_id,
                'updated_at': datetime.now().isoformat()
            }
            
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(f"インデックス更新エラー: {e}")
    
    # === Public API ===
    
    async def propose(self, content: str, sources: List[MessageRef], 
                rationale: str, tags: List[str]) -> str:
        """プランを提案（非同期版、LLMによるステップ自動生成対応）
        
        Args:
            content: プラン本文
            sources: ソースメッセージ参照
            rationale: 目的/前提
            tags: タグ
            
        Returns:
            str: プランID
        """
        plan_id = str(uuid.uuid4())
        
        # タイトルを自動生成（最初の行または要約）
        title = self._generate_title(content)
        
        plan = Plan(
            id=plan_id,
            title=title,
            content=content,
            sources=sources,
            rationale=rationale,
            tags=tags,
            created_at=datetime.now().isoformat()
        )
        
        # LLMを使用してステップを自動生成
        if self.llm_client:
            try:
                steps_data = await self._generate_steps_for_goal(content)
                for i, step_data in enumerate(steps_data):
                    step_id = f"step_{i+1:03d}"
                    step = Step(
                        step_id=step_id,
                        name=step_data.get("name", f"ステップ{i+1}"),
                        description=step_data.get("description", ""),
                        depends_on=step_data.get("depends_on", [])
                    )
                    plan.steps.append(step)
                
                self.logger.info(f"LLMにより{len(plan.steps)}個のステップを自動生成: {plan_id}")
            except Exception as e:
                self.logger.warning(f"ステップ自動生成に失敗（プランは作成されます）: {e}")
        
        state = PlanState(
            status=PlanStatus.PROPOSED,
            action_specs=[],
            selection=SpecSelection(),
            approvals=[]
        )
        
        with self._lock:
            self._plans[plan_id] = plan
            self._plan_states[plan_id] = state
            self._current_plan_id = plan_id
        
        # 永続化
        self._save_plan(plan_id)
        
        self.logger.info(f"プラン提案: {plan_id} - {title} (ステップ数: {len(plan.steps)})")
        self._log_debug_state("after_propose")
        return plan_id
    
    def _generate_title(self, content: str) -> str:
        """コンテンツからタイトルを生成"""
        lines = content.strip().split('\n')
        
        # 最初の見出し行を探す
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                return line.lstrip('#').strip()
            elif line and not line.startswith(' '):
                # 最初の非空行を使用（50文字まで）
                return line[:50] + ('...' if len(line) > 50 else '')
        
        return "新しいプラン"
    
    async def _generate_steps_for_goal(self, goal: str) -> List[Dict[str, Any]]:
        """LLMを使用して目標からステップを生成する"""
        try:
            prompt = f"""あなたは優秀なプロジェクトプランナーです。
以下の【目標】を達成するための具体的なステップを、JSON配列形式で提案してください。
各ステップには name (短い名前), description (詳細), depends_on (依存するステップIDのリスト) を含めてください。

【目標】
{goal}

【出力形式】
[
    {{
        "name": "ステップ1の名前",
        "description": "ステップ1の詳細な説明",
        "depends_on": []
    }},
    {{
        "name": "ステップ2の名前",
        "description": "ステップ2の詳細な説明",
        "depends_on": ["step_001"]
    }}
]
"""
            if self.llm_client and hasattr(self.llm_client, 'chat'):
                response = await self.llm_client.chat(prompt=prompt, tools=False, tool_choice="none")
                if response and response.content:
                    # LLMの応答からJSON部分を抽出してパース
                    json_str = self._extract_json_from_response(response.content)
                    try:
                        steps_data = json.loads(json_str)
                        if isinstance(steps_data, list):
                            self.logger.info(f"LLMから{len(steps_data)}個のステップを生成")
                            return steps_data
                        else:
                            self.logger.warning("LLMの応答がリスト形式ではありません")
                    except json.JSONDecodeError as e:
                        self.logger.error(f"ステップ生成のJSONパースエラー: {e}")
                        self.logger.debug(f"パース対象文字列: {json_str}")
                else:
                    self.logger.warning("LLMからの応答が空です")
            else:
                self.logger.warning("LLMクライアントが利用できません")
        except Exception as e:
            self.logger.error(f"ステップ生成エラー: {e}")
        return []
    
    def _extract_json_from_response(self, text: str) -> str:
        """LLMの応答からJSONコードブロックを抽出する補助関数"""
        try:
            # JSONコードブロックを探す
            match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
            if match:
                return match.group(1).strip()
            
            # コードブロックなしのJSONを探す
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                return match.group(0)
            
            # 最後の手段として、全体を返す
            return text
        except Exception as e:
            self.logger.error(f"JSON抽出エラー: {e}")
            return text
    
    def set_action_specs(self, plan_id: str, specs: List[ActionSpec]) -> ValidationReport:
        """ActionSpecを設定
        
        Args:
            plan_id: プランID
            specs: ActionSpecリスト
            
        Returns:
            ValidationReport: バリデーション結果
        """
        if plan_id not in self._plans:
            raise ValueError(f"プランが見つかりません: {plan_id}")
        
        # バリデーション実行
        validation_result = self._validate_specs(specs)
        
        if validation_result.ok:
            # 正規化されたActionSpecExtを設定
            self._plan_states[plan_id].action_specs = validation_result.normalized
            self._plan_states[plan_id].status = PlanStatus.PENDING_REVIEW
            
            # 永続化
            self._save_plan(plan_id)
            
            self.logger.info(f"ActionSpec設定完了: {plan_id} ({len(specs)}件)")
            self._log_debug_state("after_set_action_specs")
        else:
            self.logger.warning(f"ActionSpecバリデーション失敗: {plan_id}")
        
        return validation_result
    
    def _validate_specs(self, specs: List[ActionSpec]) -> ValidationReport:
        """ActionSpecをバリデーション"""
        issues = []
        normalized = []
        
        for i, spec in enumerate(specs):
            spec_id = str(uuid.uuid4())
            
            # パス正規化とセキュリティチェック
            path_issues = self._validate_path(spec.path) if spec.path else []
            issues.extend([f"Spec {i}: {issue}" for issue in path_issues])
            
            # リスク評価
            risk = self._assess_risk(spec)
            
            # プレフライト情報収集
            preflight = self._collect_preflight_info(spec)
            
            # 拡張ActionSpec作成
            ext_spec = ActionSpecExt(
                id=spec_id,
                base=spec,
                risk=risk,
                validated=len(path_issues) == 0,
                preflight=preflight,
                notes=""
            )
            
            normalized.append(ext_spec)
        
        return ValidationReport(
            ok=len(issues) == 0,
            issues=issues,
            normalized=normalized
        )
    
    def _validate_path(self, path: str) -> List[str]:
        """パスのバリデーション"""
        issues = []
        
        try:
            # pathlib で正規化
            normalized_path = Path(path).resolve()
            
            # 相対パス（..）チェック
            if '..' in Path(path).parts:
                issues.append("相対パス（..）は使用できません")
            
            # 絶対パスの場合、ワークスペース外への参照をチェック（設定で無効化可能）
            if not self.allow_external_paths:
                workspace = Path.cwd()
                try:
                    normalized_path.relative_to(workspace)
                except ValueError:
                    issues.append("ワークスペース外のパスは使用できません")
            
        except Exception as e:
            issues.append(f"パス解析エラー: {e}")
        
        return issues
    
    def _assess_risk(self, spec: ActionSpec) -> RiskLevel:
        """リスク評価"""
        if spec.kind == 'run':
            return RiskLevel.HIGH
        
        if spec.path:
            path = Path(spec.path)
            
            # 重要なファイルの上書き
            important_files = {'.env', 'config.yaml', 'requirements.txt', 'pyproject.toml'}
            if path.name in important_files:
                return RiskLevel.HIGH
            
            # 大きなファイルの上書き
            if path.exists() and path.stat().st_size > 100000:  # 100KB
                return RiskLevel.MEDIUM
            
            # システムディレクトリ
            system_dirs = {'.git', '.venv', '__pycache__', 'node_modules'}
            if any(part in system_dirs for part in path.parts):
                return RiskLevel.HIGH
        
        return RiskLevel.LOW
    
    def _collect_preflight_info(self, spec: ActionSpec) -> PreflightInfo:
        """プレフライト情報収集"""
        if not spec.path:
            return PreflightInfo()
        
        path = Path(spec.path)
        exists = path.exists()
        overwrite = exists and spec.kind in ['create', 'write']
        
        diff_summary = ""
        if overwrite and spec.content:
            # 簡単な差分サマリー
            try:
                current_content = path.read_text(encoding='utf-8')
                if current_content != spec.content:
                    diff_summary = f"変更: {len(current_content)} → {len(spec.content)} 文字"
            except Exception:
                diff_summary = "差分計算不可"
        
        return PreflightInfo(
            exists=exists,
            overwrite=overwrite,
            diff_summary=diff_summary
        )
    
    def preview(self, plan_id: str) -> PlanPreview:
        """プランをプレビュー
        
        Args:
            plan_id: プランID
            
        Returns:
            PlanPreview: プレビュー情報
        """
        if plan_id not in self._plans:
            raise ValueError(f"プランが見つかりません: {plan_id}")
        
        state = self._plan_states[plan_id]
        
        # ファイル一覧
        files = []
        diffs = []
        total_risk = 0.0
        
        for spec_ext in state.action_specs:
            spec = spec_ext.base
            
            if spec.path and spec.path not in files:
                files.append(spec.path)
                
                # 差分情報
                if spec_ext.preflight.diff_summary:
                    diffs.append({
                        'file': spec.path,
                        'summary': spec_ext.preflight.diff_summary,
                        'risk': spec_ext.risk.value
                    })
                
                # リスクスコア計算
                risk_weights = {RiskLevel.LOW: 1, RiskLevel.MEDIUM: 3, RiskLevel.HIGH: 9}
                total_risk += risk_weights[spec_ext.risk]
        
        # リスクスコアを正規化（0-1）
        max_possible_risk = len(state.action_specs) * 9
        risk_score = total_risk / max_possible_risk if max_possible_risk > 0 else 0.0
        
        preview = PlanPreview(
            files=files,
            diffs=diffs,
            risk_score=risk_score
        )
        
        # プレビューをキャッシュ
        state.previews = preview
        self._save_plan(plan_id)
        
        return preview
    
    def request_approval(self, plan_id: str, selection: SpecSelection) -> str:
        """承認を要求
        
        Args:
            plan_id: プランID
            selection: 実行対象選択
            
        Returns:
            str: 承認要求ID
        """
        if plan_id not in self._plans:
            raise ValueError(f"プランが見つかりません: {plan_id}")
        
        state = self._plan_states[plan_id]
        
        # 選択されたActionSpecが有効かチェック
        if not selection.all and selection.ids:
            valid_ids = {spec.id for spec in state.action_specs}
            invalid_ids = set(selection.ids) - valid_ids
            if invalid_ids:
                raise ValueError(f"無効なActionSpec ID: {invalid_ids}")
        
        # 承認要求IDを生成
        approval_request_id = str(uuid.uuid4())
        
        # 状態を更新
        with self._lock:
            state.selection = selection
            state.status = PlanStatus.PENDING_REVIEW
        
        self._save_plan(plan_id)
        
        self.logger.info(f"承認要求: {plan_id} (要求ID: {approval_request_id})")
        self._log_debug_state("after_request_approval")
        return approval_request_id
    
    def approve(self, plan_id: str, approver: str, selection: SpecSelection) -> Dict[str, Any]:
        """プランを承認
        
        Args:
            plan_id: プランID
            approver: 承認者
            selection: 承認対象選択
            
        Returns:
            Dict[str, Any]: 承認済みプラン情報
        """
        if plan_id not in self._plans:
            raise ValueError(f"プランが見つかりません: {plan_id}")
        
        state = self._plan_states[plan_id]
        
        # 承認記録を追加
        approval = ApprovalRecord(
            approver=approver,
            timestamp=datetime.now().isoformat(),
            selection=selection
        )
        with self._lock:
            state.approvals.append(approval)
            # 状態を承認済みに変更
            state.status = PlanStatus.APPROVED
            state.selection = selection
        
        self._save_plan(plan_id)
        
        # 承認済みプラン情報を返す
        approved_plan = {
            'plan_id': plan_id,
            'title': self._plans[plan_id].title,
            'approved_at': approval.timestamp,
            'approver': approver,
            'selection': asdict(selection),
            'action_count': len(self._get_selected_specs(plan_id, selection))
        }
        
        self.logger.info(f"プラン承認: {plan_id} by {approver}")
        self._log_debug_state("after_approve")
        return approved_plan
    
    def _get_selected_specs(self, plan_id: str, selection: SpecSelection) -> List[ActionSpecExt]:
        """選択されたActionSpecを取得"""
        state = self._plan_states[plan_id]
        
        if selection.all:
            return state.action_specs
        else:
            return [spec for spec in state.action_specs if spec.id in selection.ids]
    
    def execute(self, plan_id: str) -> ExecutionResult:
        """プランを実行
        
        Args:
            plan_id: プランID
            
        Returns:
            ExecutionResult: 実行結果
        """
        if plan_id not in self._plans:
            raise ValueError(f"プランが見つかりません: {plan_id}")
        
        state = self._plan_states[plan_id]
        
        # 承認チェック
        if state.status != PlanStatus.APPROVED:
            raise ValueError(f"未承認のプランは実行できません: {state.status.value}")
        
        # 実行開始
        started_at = datetime.now().isoformat()
        with self._lock:
            state.status = PlanStatus.EXECUTING
        self._save_plan(plan_id)
        
        self.logger.info(f"プラン実行開始: {plan_id}")
        
        # 選択されたActionSpecを実行
        selected_specs = self._get_selected_specs(plan_id, state.selection)
        results = []
        overall_success = True
        
        try:
            for spec_ext in selected_specs:
                spec = spec_ext.base
                
                # プレフライト再チェック（競合検出）
                current_preflight = self._collect_preflight_info(spec)
                # いずれかの preflight 情報が変化した場合は再承認へ
                if (current_preflight.exists != spec_ext.preflight.exists or
                    current_preflight.overwrite != spec_ext.preflight.overwrite or
                    current_preflight.diff_summary != spec_ext.preflight.diff_summary):
                    with self._lock:
                        state.status = PlanStatus.PENDING_REVIEW
                    self._save_plan(plan_id)
                    raise RuntimeError(f"preflight 変化検出: {spec.path}。再承認が必要です")
                
                # ActionSpecを実行
                try:
                    result = self._execute_single_spec(spec)
                    results.append(result)
                    
                    if not result.get('success', False):
                        overall_success = False
                        
                except Exception as e:
                    self.logger.error(f"ActionSpec実行エラー {spec.path}: {e}")
                    results.append({
                        'spec_id': spec_ext.id,
                        'path': spec.path,
                        'success': False,
                        'error': str(e)
                    })
                    overall_success = False
            
            # 実行完了
            finished_at = datetime.now().isoformat()
            with self._lock:
                state.status = PlanStatus.COMPLETED if overall_success else PlanStatus.ABORTED
            
        except Exception as e:
            # 実行中断
            finished_at = datetime.now().isoformat()
            with self._lock:
                state.status = PlanStatus.ABORTED
            overall_success = False
            self.logger.error(f"プラン実行中断: {plan_id} - {e}")
        
        # 結果を保存
        execution_result = ExecutionResult(
            overall_success=overall_success,
            results=results,
            started_at=started_at,
            finished_at=finished_at
        )
        
        self._save_plan(plan_id)
        
        self.logger.info(f"プラン実行完了: {plan_id} (成功: {overall_success})")
        return execution_result
    
    def _execute_single_spec(self, spec: ActionSpec) -> Dict[str, Any]:
        """単一ActionSpecを実行（承認済みなので SimpleFileOps を使用）"""
        try:
            if spec.kind in ('create', 'write'):
                outcome = self.file_ops.apply_with_approval_write(
                    spec.path, spec.content or "", session_id="plan_tool_execute"
                )
                return {
                    'path': spec.path,
                    'kind': spec.kind,
                    'success': outcome.ok,
                    'message': outcome.reason if outcome.ok else '',
                    'error': None if outcome.ok else outcome.reason
                }
            elif spec.kind == 'mkdir':
                res = self._direct_create_directory(spec.path)
                return {
                    'path': spec.path,
                    'kind': spec.kind,
                    'success': res.get('success', False),
                    'message': res.get('message', ''),
                    'error': res.get('error', '')
                }
            elif spec.kind == 'read':
                try:
                    content = self.file_ops.read_file(spec.path)
                    return {
                        'path': spec.path,
                        'kind': spec.kind,
                        'success': True,
                        'message': f'ファイル読み取り成功: {spec.path}',
                        'error': '',
                        'content': content,
                        'size': len(content)
                    }
                except Exception as e:
                    return {'path': spec.path, 'kind': spec.kind, 'success': False, 'error': str(e)}
            elif spec.kind == 'analyze':
                return {
                    'path': spec.path,
                    'kind': spec.kind,
                    'success': True,
                    'message': f'分析完了: {spec.path}',
                    'error': ''
                }
            elif spec.kind == 'run':
                return {
                    'path': spec.path,
                    'kind': spec.kind,
                    'success': False,
                    'error': 'コマンド実行は未実装'
                }
            else:
                return {'path': spec.path, 'kind': spec.kind, 'success': False, 'error': f'未知のActionSpec種別: {spec.kind}'}
        except Exception as e:
            return {'path': spec.path, 'kind': spec.kind, 'success': False, 'error': str(e)}
    
    def _direct_create_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """直接ファイル作成（承認済み）"""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            
            return {
                'success': True,
                'message': f'ファイル作成成功: {file_path}',
                'size': len(content)
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'ファイル作成失敗: {e}'
            }
    
    def _direct_write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """直接ファイル書き込み（承認済み）"""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            
            return {
                'success': True,
                'message': f'ファイル書き込み成功: {file_path}',
                'size': len(content)
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'ファイル書き込み失敗: {e}'
            }
    
    def _direct_create_directory(self, dir_path: str) -> Dict[str, Any]:
        """直接ディレクトリ作成（承認済み）"""
        try:
            path = Path(dir_path)
            path.mkdir(parents=True, exist_ok=True)
            
            return {
                'success': True,
                'message': f'ディレクトリ作成成功: {dir_path}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'ディレクトリ作成失敗: {e}'
            }
    
    def _direct_read_file(self, file_path: str) -> Dict[str, Any]:
        """直接ファイル読み取り（承認済み）"""
        try:
            path = Path(file_path)
            if not path.exists():
                return {
                    'success': False,
                    'error': f'ファイルが存在しません: {file_path}'
                }
            
            content = path.read_text(encoding='utf-8')
            return {
                'success': True,
                'message': f'ファイル読み取り成功: {file_path}',
                'content': content,
                'size': len(content)
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'ファイル読み取り失敗: {e}'
            }
    
    # === 状態取得API ===
    
    def get_state(self, plan_id: str) -> Dict[str, Any]:
        """プラン状態を取得
        
        Args:
            plan_id: プランID
            
        Returns:
            Dict[str, Any]: プラン状態
        """
        if plan_id not in self._plans:
            raise ValueError(f"プランが見つかりません: {plan_id}")
        
        plan = self._plans[plan_id]
        state = self._plan_states[plan_id]
        
        return {
            'plan': asdict(plan),
            'state': {
                'status': state.status.value,
                'action_count': len(state.action_specs),
                'approved_count': len(state.approvals),
                'selection': asdict(state.selection),
                'risk_score': state.previews.risk_score if state.previews else 0.0
            }
        }
    
    def get_current(self) -> Optional[Dict[str, str]]:
        """現在のプランを取得
        
        Returns:
            Optional[Dict[str, str]]: プラン参照情報
        """
        if not self._current_plan_id or self._current_plan_id not in self._plans:
            return None
        
        plan = self._plans[self._current_plan_id]
        state = self._plan_states[self._current_plan_id]
        
        return {
            'id': self._current_plan_id,
            'title': plan.title,
            'status': state.status.value
        }
    
    def list(self) -> List[Dict[str, Any]]:
        """プラン一覧を取得
        
        Returns:
            List[Dict[str, Any]]: プラン参照リスト
        """
        plans_list = []
        
        for plan_id, plan in self._plans.items():
            state = self._plan_states.get(plan_id)
            plans_list.append({
                'id': plan_id,
                'title': plan.title,
                'status': state.status.value if state else 'unknown',
                'created_at': plan.created_at,
                'tags': plan.tags,
                'action_count': len(state.action_specs) if state else 0
            })
        
        # 作成日時でソート（新しい順）
        plans_list.sort(key=lambda x: x['created_at'], reverse=True)
        return plans_list
    
    def mark_pending(self, plan_id: str, pending: bool) -> Dict[str, Any]:
        """プランのpending状態を設定
        
        Args:
            plan_id: プランID
            pending: pending状態
            
        Returns:
            Dict[str, Any]: 更新後の状態
        """
        if plan_id not in self._plans:
            raise ValueError(f"プランが見つかりません: {plan_id}")
        
        # この機能は既存のPlanContextとの互換性のため
        # 実際の状態管理はstatusで行う
        self.logger.info(f"プランpending設定: {plan_id} = {pending}")
        
        return self.get_state(plan_id)
    
    def clear_current(self):
        """現在のプランをクリア"""
        with self._lock:
            self._current_plan_id = None
        self._update_index()
        self.logger.info("現在のプランをクリア")
    
    # === LLM選択処理統合メソッド ===
    
    async def process_user_selection_enhanced(self, user_input: str, plan_id: str) -> Dict[str, Any]:
        """LLM強化ユーザー選択処理
        
        Args:
            user_input: ユーザーの入力テキスト
            plan_id: プランID
            
        Returns:
            Dict[str, Any]: 選択処理結果
        """
        if plan_id not in self._plans:
            raise ValueError(f"プランが見つかりません: {plan_id}")
        
        # LLMPlanApprovalHandlerをインポート（循環インポート回避）
        from companion.llm_choice.plan_approval_handler import (
            LLMPlanApprovalHandler, PlanApprovalContext
        )
        
        # プランコンテキストを構築
        plan = self._plans[plan_id]
        plan_state = self._plan_states[plan_id]
        
        # ActionSpecをavailable_actionsに変換（簡略化）
        available_actions = [spec.base for spec in plan_state.action_specs]
        
        plan_context = PlanApprovalContext(
            plan=plan,
            plan_state=plan_state,
            available_actions=available_actions,
            risk_level=self._assess_plan_risk_level(plan_state),
            preview_summary=self._generate_preview_summary(plan_state)
        )
        
        # LLM処理を実行
        handler = LLMPlanApprovalHandler()
        approval_result = await handler.process_plan_response(user_input, plan_context)
        
        # 結果を処理してPlanToolの形式に変換
        return self._convert_approval_result_to_selection(approval_result, plan_id)
    
    def _assess_plan_risk_level(self, plan_state: PlanState) -> str:
        """プランのリスクレベルを評価
        
        Args:
            plan_state: プラン状態
            
        Returns:
            str: リスクレベル ("low", "medium", "high")
        """
        if plan_state.previews and plan_state.previews.risk_score:
            if plan_state.previews.risk_score >= 0.8:
                return "high"
            elif plan_state.previews.risk_score >= 0.5:
                return "medium"
            else:
                return "low"
        
        # ActionSpecの内容に基づく簡易評価
        high_risk_operations = {"write", "create", "mkdir"}
        risky_spec_count = sum(
            1 for spec in plan_state.action_specs
            if spec.base.kind in high_risk_operations
        )
        
        total_specs = len(plan_state.action_specs)
        if total_specs == 0:
            return "low"
        
        risk_ratio = risky_spec_count / total_specs
        if risk_ratio >= 0.7:
            return "high"
        elif risk_ratio >= 0.3:
            return "medium"
        else:
            return "low"
    
    def _generate_preview_summary(self, plan_state: PlanState) -> str:
        """プレビューサマリーを生成
        
        Args:
            plan_state: プラン状態
            
        Returns:
            str: プレビューサマリー
        """
        if plan_state.previews and plan_state.previews.files:
            files_summary = f"{len(plan_state.previews.files)}個のファイル"
            if plan_state.previews.diffs:
                files_summary += f"、{len(plan_state.previews.diffs)}箇所の変更"
            return files_summary
        
        # ActionSpecベースの簡易サマリー
        operation_counts = {}
        for spec in plan_state.action_specs:
            op = spec.base.kind
            operation_counts[op] = operation_counts.get(op, 0) + 1
        
        summary_parts = []
        for op, count in operation_counts.items():
            summary_parts.append(f"{op}: {count}件")
        
        return ", ".join(summary_parts) if summary_parts else "アクションなし"
    
    def _convert_approval_result_to_selection(self, approval_result, plan_id: str) -> Dict[str, Any]:
        """承認結果をPlanToolの選択結果に変換
        
        Args:
            approval_result: LLM承認結果
            plan_id: プランID
            
        Returns:
            Dict[str, Any]: 選択結果
        """
        from companion.llm_choice.plan_approval_handler import ApprovalAction
        
        result = {
            "plan_id": plan_id,
            "action": approval_result.action.value,
            "confidence": approval_result.confidence,
            "reasoning": approval_result.reasoning,
            "approved_spec_ids": approval_result.approved_spec_ids,
            "clarification_needed": approval_result.clarification_needed,
            "user_message": approval_result.user_message
        }
        
        # アクションに応じた具体的な処理
        if approval_result.action == ApprovalAction.APPROVE_ALL:
            result["should_approve"] = True
            result["selection"] = SpecSelection(all=True)
        elif approval_result.action == ApprovalAction.APPROVE_PARTIAL:
            result["should_approve"] = True
            result["selection"] = SpecSelection(all=False, ids=approval_result.approved_spec_ids)
        elif approval_result.action == ApprovalAction.REJECT:
            result["should_approve"] = False
            result["selection"] = SpecSelection(all=False, ids=[])
        else:  # REQUEST_MODIFICATION or REQUEST_DETAILS
            result["should_approve"] = False
            result["needs_clarification"] = True
            result["modifications_requested"] = approval_result.modifications_requested
        
        return result
