# シンプル承認システム 再構築プラン

**バージョン:** 1.0  
**作成日:** 2025年8月17日  
**対象:** 現在の承認システム完全置換  

## 1. 現状分析と問題の特定

### 1.1. 現在の承認システムの重大な問題

#### **🚨 コード重複による動作不良**
```python
# approval_system.py で発見された重複
- ApprovalConfig クラス: 471行目と1197行目に重複定義
- _log_security_event メソッド: 916行目と1478行目に重複  
- _detect_bypass_attempt メソッド: 949行目と1511行目に重複
- _create_fail_safe_response メソッド: 1079行目と1641行目に重複
```

#### **⚙️ 設定と統合の問題**
- 設定参照エラー (`self.config.show_preview` 等)
- UI初期化の失敗
- ApprovalMode処理の不整合
- モジュール循環参照の可能性

#### **🔗 複雑な依存関係**
- 5つの主要ファイルに分散した実装
- Rich UI、ConfigManager、LLM統合への複雑な依存
- エラー時のフォールバック処理が不完全

### 1.2. 置換方針
**現在のシステムを完全削除し、最小限で確実に動作するシンプルな承認システムを実装**

## 2. シンプル承認システム設計

### 2.1. 設計原則

```yaml
設計原則:
  1. 最小限の機能: y/n承認のみ
  2. 依存関係最小化: Rich UIのみ依存
  3. フォールバック重視: 失敗時はデフォルト動作
  4. 拡張可能性: 将来の機能追加を考慮
  5. デバッグ容易性: 問題の特定が簡単
```

### 2.2. 核心コンポーネント設計

#### **SimpleApprovalGate** (単一ファイル実装)
```python
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime

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
    
    def __init__(self):
        # config.yamlから設定を読み込み
        self.config = self._load_config()
        self.approval_history: List[ApprovalResult] = []
        
        # Rich UI統合
        try:
            from codecrafter.ui.rich_ui import rich_ui
            self.ui = rich_ui
        except ImportError:
            self.ui = None  # フォールバック: 標準入力使用
    
    def _load_config(self) -> Dict[str, Any]:
        """config.yamlから承認設定を読み込み"""
        try:
            from codecrafter.base.config import config_manager
            return config_manager.config.get('approval', {})
        except Exception as e:
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
        
        # config.yamlの設定に基づく承認処理
        mode = self.config.get('mode', 'standard')
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
        if mode == 'trusted' and request.risk_level == RiskLevel.LOW:
            return self._auto_approve(request, "信頼モード - 低リスク自動承認")
        elif mode == 'strict':
            return self._strict_approval(request)
        else:  # standard
            return self._standard_approval(request)
    
    def _standard_approval(self, request: ApprovalRequest) -> ApprovalResult:
        """標準承認処理"""
        return self._manual_approval(request)
    
    def _strict_approval(self, request: ApprovalRequest) -> ApprovalResult:
        """厳格承認処理（詳細確認付き）"""
        # 厳格モードでは詳細情報を必須表示
        if not request.details:
            request.details = "詳細情報なし - 厳格モードでは特に注意が必要"
        
        result = self._manual_approval(request)
        
        # 厳格モードでは承認後に再確認
        if result.approved and request.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]:
            if self.ui:
                reconfirm = self.ui.get_confirmation("⚠️ 厳格モード: 本当に実行しますか？ (最終確認)")
            else:
                reconfirm_input = input("⚠️ 厳格モード: 本当に実行しますか？ (y/n): ").strip().lower()
                reconfirm = reconfirm_input in ['y', 'yes', 'はい']
            
            if not reconfirm:
                return ApprovalResult(
                    approved=False,
                    reason="厳格モード - 最終確認で拒否",
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
            return result
            
        except Exception as e:
            # エラー時は安全のため拒否
            return ApprovalResult(
                approved=False,
                reason=f"承認処理エラー: {e}",
                timestamp=datetime.now()
            )
    
    def _rich_ui_approval(self, request: ApprovalRequest) -> bool:
        """Rich UI承認"""
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
        
        # タイムアウト設定
        timeout = self.config.get('timeout_seconds', 30)
        
        return self.ui.get_confirmation("実行を承認しますか？")
    
    def _fallback_approval(self, request: ApprovalRequest) -> bool:
        """フォールバック承認（標準入力）"""
        print("\n" + "="*50)
        print("🔐 承認が必要です")
        print(f"操作: {request.operation}")
        print(f"対象: {request.target}")
        print(f"説明: {request.description}")
        if request.details:
            print(f"詳細: {request.details}")
        print(f"リスク: {request.risk_level}")
        print("="*50)
        
        while True:
            response = input("実行を承認しますか？ (y/n): ").strip().lower()
            if response in ['y', 'yes', 'はい']:
                return True
            elif response in ['n', 'no', 'いいえ']:
                return False
            else:
                print("y（はい）またはn（いいえ）を入力してください。")
    
    def _auto_approve(self, request: ApprovalRequest, reason: str) -> ApprovalResult:
        """自動承認"""
        result = ApprovalResult(
            approved=True,
            reason=reason,
            timestamp=datetime.now()
        )
        self.approval_history.append(result)
        return result
```

### 2.3. ファイル操作統合

#### **SimpleFileOpsの承認統合**
```python
class SimpleFileOps:
    """承認統合されたファイル操作"""
    
    def __init__(self):
        # 承認ゲートは設定から初期化
        self.approval_gate = SimpleApprovalGate()
    
    async def write_file_with_approval(self, file_path: str, content: str) -> FileOpOutcome:
        """承認付きファイル書き込み"""
        
        # 承認要求作成
        request = ApprovalRequest(
            operation="ファイル書き込み",
            description=f"ファイル '{file_path}' に内容を書き込みます",
            target=file_path,
            risk_level=self._assess_write_risk(file_path),
            details=f"サイズ: {len(content)}文字\n内容プレビュー:\n{content[:200]}{'...' if len(content) > 200 else ''}"
        )
        
        # 承認要求
        approval = self.approval_gate.request_approval(request)
        
        if not approval.approved:
            return FileOpOutcome(
                success=False,
                message=f"ユーザーによる拒否: {approval.reason}",
                path=file_path
            )
        
        # 実際のファイル書き込み
        return await self._execute_write(file_path, content)
    
    def _assess_write_risk(self, file_path: str) -> RiskLevel:
        """書き込みリスク評価"""
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
```

## 3. 実装ステップ

### 3.1. Phase 1: 現在システム削除・基盤実装 (1日)

#### **Step 1.1: 現在承認システムの削除**
```bash
# 削除対象ファイル
companion/approval_system.py          # → 完全削除
companion/approval_ui.py              # → 完全削除  
companion/approval_response_handler.py # → 完全削除

# 統合箇所のクリーンアップ
companion/core.py                     # → 承認関連import削除
companion/enhanced_dual_loop.py       # → 承認関連コード削除
companion/file_ops.py                 # → 承認関連import修正
```

#### **Step 1.2: SimpleApprovalGateの実装**
```python
# 新規作成: companion/simple_approval.py
class SimpleApprovalGate:
    # 上記設計の実装
```

#### **Step 1.3: 基本統合テスト**
```python
# tests/test_simple_approval.py
def test_simple_approval_basic():
    gate = SimpleApprovalGate(ApprovalMode.AUTO_APPROVE)
    request = ApprovalRequest(
        operation="テスト操作",
        description="テスト説明", 
        target="test.txt"
    )
    result = gate.request_approval(request)
    assert result.approved == True
```

### 3.2. Phase 2: ファイル操作統合 (1日)

#### **Step 2.1: SimpleFileOpsの承認統合**
```python
# companion/file_ops.py の改修
class SimpleFileOps:
    def __init__(self, approval_mode: ApprovalMode = ApprovalMode.MANUAL):
        self.approval_gate = SimpleApprovalGate(approval_mode)
    
    # write_file_with_approval メソッド実装
```

#### **Step 2.2: CompanionCoreとの統合**
```python
# companion/core.py の改修
from .simple_approval import SimpleApprovalGate, ApprovalMode

class CompanionCore:
    def __init__(self, approval_mode: ApprovalMode = ApprovalMode.MANUAL):
        self.file_ops = SimpleFileOps(approval_mode)
```

#### **Step 2.3: 統合動作テスト**
```python
async def test_file_operation_with_approval():
    core = CompanionCore(ApprovalMode.AUTO_APPROVE)
    result = await core.file_ops.write_file_with_approval("test.txt", "content")
    assert result.success == True
```

### 3.3. Phase 3: Enhanced Dual Loop統合 (0.5日)

#### **Step 3.1: DualLoopSystemの承認統合**
```python
# companion/enhanced_dual_loop.py の改修
class EnhancedDualLoopSystem:
    def __init__(self, approval_mode: ApprovalMode = ApprovalMode.MANUAL):
        self.approval_mode = approval_mode
        # CompanionCoreに承認モードを渡す
```

#### **Step 3.2: 設定ベース承認モード**
```python
# config/config.yaml に追加
approval:
  mode: "manual"          # manual | auto | deny
  timeout_seconds: 30
  show_details: true
```

### 3.4. Phase 4: テストと調整 (0.5日)

#### **Step 4.1: E2Eテスト**
```python
async def test_approval_e2e():
    """エンドツーエンド承認テスト"""
    # 実際のユーザーシナリオでテスト
    dual_loop = EnhancedDualLoopSystem(ApprovalMode.MANUAL)
    # ファイル作成要求をシミュレート
    result = await dual_loop.process_user_request("test.pyを作成してください")
    # 承認プロセスが正常に動作することを確認
```

#### **Step 4.2: エラーハンドリングテスト**
```python
def test_approval_error_handling():
    """承認エラーハンドリングテスト"""
    # UI初期化失敗のシミュレート
    # ネットワークエラーのシミュレート
    # ユーザー入力エラーのシミュレート
```

## 4. 削除と統合の詳細計画

### 4.1. 削除対象ファイルと代替

```yaml
削除ファイル:
  companion/approval_system.py:
    理由: "重複定義による動作不良"
    代替: "companion/simple_approval.py"
    
  companion/approval_ui.py:
    理由: "複雑な統合、保守困難"
    代替: "SimpleApprovalGateの内蔵UI"
    
  companion/approval_response_handler.py:
    理由: "過度に複雑、不要"
    代替: "SimpleApprovalGateの直接処理"
```

### 4.2. 既存ファイルの修正箇所

```python
# companion/core.py
- from .approval_system import ApprovalGate, ApprovalConfig, ApprovalMode
+ from .simple_approval import SimpleApprovalGate, ApprovalMode

# companion/enhanced_dual_loop.py  
- 複雑な承認統合コードを削除
+ シンプルな承認モード設定

# companion/file_ops.py
- from .approval_ui import NonInteractiveApprovalUI, UserApprovalUI
+ SimpleApprovalGateの直接使用
```

### 4.3. インポート関係の整理

```python
# 新しいインポート構造
companion/
├── simple_approval.py      # 単一ファイル承認システム
├── core.py                 # SimpleApprovalGate使用
├── file_ops.py             # SimpleApprovalGate統合
└── enhanced_dual_loop.py   # 承認モード設定
```

## 5. 設定とカスタマイズ

### 5.1. config.yaml設定例
```yaml
# config/config.yaml - 承認システム設定
approval:
  mode: "standard"           # strict | standard | trusted
  timeout_seconds: 30
  show_preview: true
  max_preview_length: 200
  ui:
    non_interactive: false   # 対話UIを使用
    auto_approve_low: false  # 低リスクの自動承認
    auto_approve_high: false # 高リスクの自動承認
    auto_approve_all: false  # 全自動承認（開発時のみ推奨）

# 開発時設定例
# approval:
#   mode: "trusted"
#   ui:
#     auto_approve_low: true    # 低リスクは自動承認
#     auto_approve_all: false

# 本番環境設定例  
# approval:
#   mode: "strict"
#   timeout_seconds: 60
#   ui:
#     auto_approve_low: false   # すべて手動承認
#     auto_approve_high: false
```

### 5.2. 設定ベース動作
```python
# 設定は初期化時に自動読み込み
approval_gate = SimpleApprovalGate()  # config.yamlから設定を読み込み

# 設定変更時は再起動が必要（シンプルな設計のため）
```

## 6. テスト戦略

### 6.1. 単体テスト
```python
test_simple_approval.py:
  - 基本承認機能
  - 自動承認/拒否モード
  - エラーハンドリング
  - UI統合

test_file_ops_approval.py:
  - ファイル操作承認統合
  - リスク評価
  - 承認拒否時の処理
```

### 6.2. 統合テスト
```python
test_approval_integration.py:
  - CompanionCore統合
  - DualLoop統合  
  - E2Eワークフロー
```

### 6.3. 手動テスト
```yaml
手動テストシナリオ:
  1. ファイル作成要求 → 承認プロンプト表示 → 承認 → 実行
  2. ファイル作成要求 → 承認プロンプト表示 → 拒否 → 中断
  3. 自動承認モード → プロンプトなし → 自動実行
  4. UI失敗時 → フォールバック → 標準入力承認
```

## 7. マイグレーション計画

### 7.1. 段階的移行
```
Day 1 Morning: 現在システム削除 + 基盤実装
Day 1 Afternoon: ファイル操作統合
Day 2 Morning: DualLoop統合 + テスト
Day 2 Afternoon: 動作確認 + 調整
```

### 7.2. ロールバック計画
```yaml
ロールバック対応:
  - 削除前にバックアップ作成
  - Git別ブランチでの実装
  - 問題時の即座復旧手順
```

## 8. 成功指標

### 8.1. 機能指標
- ✅ 承認プロンプトが正常表示される
- ✅ ユーザー選択（y/n）が正確に処理される  
- ✅ ファイル操作前に承認が要求される
- ✅ 自動承認モードが正常動作する

### 8.2. 信頼性指標
- ✅ 承認システム起動時のエラーゼロ
- ✅ UI失敗時のフォールバック動作
- ✅ 全テストケースのパス率100%

### 8.3. ユーザビリティ指標
- ✅ 承認プロンプトの表示が3秒以内
- ✅ 直感的な承認インターフェース
- ✅ エラーメッセージの分かりやすさ

## 9. 将来拡張計画

### 9.1. 短期拡張 (1ヶ月)
- 承認履歴の永続化
- リスクレベル別の承認ポリシー
- 承認タイムアウト処理

### 9.2. 中期拡張 (3ヶ月)  
- 複数ユーザー承認
- 承認ワークフロー
- 監査ログ機能

### 9.3. 長期拡張 (6ヶ月)
- Web UI承認
- リモート承認
- 機械学習リスク評価

---

このプランにより、現在の破損した承認システムを完全に置き換え、シンプルで確実に動作する承認システムを2日で実装できます。最小限の機能から開始し、段階的に拡張可能な設計となっています。