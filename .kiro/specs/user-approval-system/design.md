# Design Document: User Approval System

## Overview

Duckflow Companionにユーザー承認システムを実装し、リスクの高い操作（ファイル作成、編集、コード実行）を実行する前にユーザーの明示的な許可を求める。このシステムは、AIの自律性とユーザーの安全性のバランスを取り、相棒らしい自然な対話を維持しながらセキュリティを確保する。

## Architecture

### システム構成図

```
[CompanionCore] 
       ↓
[OperationAnalyzer] → [RiskClassifier]
       ↓
[ApprovalGate] → [UserApprovalUI]
       ↓
[OperationExecutor] (SimpleFileOps, CodeRunner)
```

### データフロー

1. **操作検出**: CompanionCoreが実行予定の操作を検出
2. **リスク分析**: OperationAnalyzerが操作のリスクレベルを判定
3. **承認ゲート**: ApprovalGateが必要に応じてユーザー承認を要求
4. **実行制御**: 承認された操作のみが実際に実行される

## Components and Interfaces

### 1. RiskLevel (Enum)

```python
class RiskLevel(Enum):
    LOW_RISK = "low_risk"      # ファイル読み取り、一覧表示
    HIGH_RISK = "high_risk"    # ファイル作成、編集、コード実行
    CRITICAL_RISK = "critical_risk"  # システム操作（将来拡張用）
```

### 2. OperationInfo (Data Class)

```python
@dataclass
class OperationInfo:
    operation_type: str        # "create_file", "execute_code", etc.
    target: str               # ファイル名、コマンド等
    description: str          # 操作の説明
    risk_level: RiskLevel     # リスクレベル
    details: Dict[str, Any]   # 追加詳細情報
    preview: Optional[str]    # 内容のプレビュー
```

### 3. ApprovalRequest (Data Class)

```python
@dataclass
class ApprovalRequest:
    operation_info: OperationInfo
    message: str              # ユーザーへの説明メッセージ
    timestamp: datetime
    session_id: str
```

### 4. ApprovalResponse (Data Class)

```python
@dataclass
class ApprovalResponse:
    approved: bool
    reason: Optional[str]     # 拒否理由（オプション）
    timestamp: datetime
    alternative_suggested: bool
```

### 5. OperationAnalyzer (Class)

```python
class OperationAnalyzer:
    """操作の分析とリスク判定を行う"""
    
    def analyze_operation(self, operation_type: str, params: Dict[str, Any]) -> OperationInfo:
        """操作を分析してOperationInfoを生成"""
        
    def classify_risk(self, operation_type: str, target: str) -> RiskLevel:
        """操作のリスクレベルを判定"""
        
    def generate_description(self, operation_info: OperationInfo) -> str:
        """ユーザー向けの操作説明を生成"""
```

### 6. ApprovalGate (Class)

```python
class ApprovalGate:
    """承認ゲート - すべての危険操作はここを通る"""
    
    def __init__(self, approval_ui: 'UserApprovalUI', config: ApprovalConfig):
        self.approval_ui = approval_ui
        self.config = config
        
    def request_approval(self, operation_info: OperationInfo) -> ApprovalResponse:
        """承認を要求し、結果を返す"""
        
    def is_approval_required(self, operation_info: OperationInfo) -> bool:
        """承認が必要かどうかを判定"""
        
    def handle_rejection(self, operation_info: OperationInfo, reason: str) -> str:
        """拒否時の対応（代替案提案等）"""
```

### 7. UserApprovalUI (Class)

```python
class UserApprovalUI:
    """ユーザー承認のUI処理"""
    
    def show_approval_request(self, request: ApprovalRequest) -> ApprovalResponse:
        """承認要求をユーザーに表示し、応答を取得"""
        
    def format_operation_details(self, operation_info: OperationInfo) -> str:
        """操作詳細を分かりやすく整形"""
        
    def show_risk_warning(self, risk_level: RiskLevel, details: str) -> None:
        """リスク警告を表示"""
```

### 8. ApprovalConfig (Class)

```python
class ApprovalConfig:
    """承認システムの設定"""
    
    def __init__(self):
        self.mode: ApprovalMode = ApprovalMode.STANDARD
        self.auto_approve_read: bool = True
        self.require_confirmation_for_overwrite: bool = True
        self.show_content_preview: bool = True
        self.max_preview_length: int = 200
```

### 9. ApprovalMode (Enum)

```python
class ApprovalMode(Enum):
    STRICT = "strict"      # すべてのファイル操作で承認
    STANDARD = "standard"  # HIGH_RISK操作のみ承認
    TRUSTED = "trusted"    # 承認なし（デバッグ用）
```

## Data Models

### 承認ログ

```python
@dataclass
class ApprovalLog:
    timestamp: datetime
    operation_info: OperationInfo
    approved: bool
    user_response_time: float  # 応答時間（秒）
    session_id: str
```

### 設定データ

```yaml
approval_system:
  mode: "standard"  # strict, standard, trusted
  auto_approve_read: true
  require_confirmation_for_overwrite: true
  show_content_preview: true
  max_preview_length: 200
  timeout_seconds: 30  # 承認要求のタイムアウト
```

## Error Handling

### 1. 承認タイムアウト

```python
class ApprovalTimeoutError(Exception):
    """承認要求がタイムアウトした場合"""
    pass
```

**対応**: デフォルトで操作を拒否し、ユーザーに再試行を促す

### 2. 承認システム無効化試行

```python
class ApprovalBypassAttemptError(Exception):
    """承認システムのバイパス試行を検出"""
    pass
```

**対応**: 操作を即座に停止し、警告メッセージを表示

### 3. UI応答エラー

```python
class ApprovalUIError(Exception):
    """承認UI関連のエラー"""
    pass
```

**対応**: フェイルセーフとして操作を拒否

## Testing Strategy

### 1. 単体テスト

- **OperationAnalyzer**: 各操作タイプの正確な分類
- **ApprovalGate**: 承認ロジックの正確性
- **RiskClassifier**: リスクレベル判定の精度

### 2. 統合テスト

- **承認フロー**: 要求→表示→応答→実行の完全なフロー
- **拒否処理**: 拒否時の適切な代替案提案
- **設定変更**: 各モードでの動作確認

### 3. セキュリティテスト

- **バイパス試行**: 承認システムの迂回試行を検出
- **権限昇格**: 不正な権限取得の防止
- **フェイルセーフ**: エラー時の安全な動作

### 4. ユーザビリティテスト

- **応答時間**: 承認要求の表示速度
- **理解しやすさ**: 操作説明の明確性
- **会話継続**: 承認後の自然な対話継続

## Implementation Plan

### Phase 1: 基本承認システム

1. **RiskLevel, OperationInfo等の基本データ構造**
2. **OperationAnalyzer**: 基本的な操作分析
3. **ApprovalGate**: シンプルな承認ゲート
4. **UserApprovalUI**: 基本的な承認UI

### Phase 2: 高度な機能

1. **ApprovalConfig**: 設定可能な承認システム
2. **承認ログ**: 操作履歴の記録
3. **代替案提案**: 拒否時の自動提案

### Phase 3: セキュリティ強化

1. **バイパス検出**: 不正な迂回試行の検出
2. **フェイルセーフ**: エラー時の安全な動作
3. **監査ログ**: セキュリティイベントの記録

## Security Considerations

### 1. 承認システムの完全性

- 承認ゲートは全ての危険操作の単一通過点
- AIが承認システムを無効化する手段を提供しない
- フェイルセーフ設計（エラー時は操作拒否）

### 2. ユーザー認証

- 承認要求は実際のユーザーからの応答のみ受け入れ
- タイムアウト機能で無人状態での実行を防止

### 3. 操作の透明性

- すべての操作詳細をユーザーに明示
- 隠れた副作用や追加操作の防止
- 実行前の内容プレビュー表示

## Performance Considerations

### 1. 応答性

- 承認要求の表示は1秒以内
- リスク分析は軽量な処理で実装
- UI応答の非同期処理

### 2. メモリ使用量

- 承認ログの適切なローテーション
- 大きなファイル内容のプレビュー制限

### 3. 設定の永続化

- 承認設定の効率的な保存・読み込み
- 設定変更の即座反映