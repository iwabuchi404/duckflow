# PromptCompiler記憶注入機能統合

## 概要

PromptCompilerに3層構造（Base/Main/Specialized）と記憶注入機能を統合し、3層にプロンプトを分けた意味を最大限に活かす設計を実装しました。

## 🏗️ アーキテクチャ

### 3層構造の設計思想

```
Base + Main + Specialized の3層構造
├── Base層: システム設定・制約・安全ルール（常に含む）
├── Main層: 会話履歴・固定5項目・短期記憶（標準版で含む）
└── Specialized層: 専門知識・手順書・長期記憶（完全版で含む）
```

### 記憶データの分類

- **Base層記憶**: セッション情報、作業ディレクトリ、現在の状態
- **Main層記憶**: 最近のファイル操作、会話履歴要約、処理履歴
- **Specialized層記憶**: ファイル内容キャッシュ、要約履歴、プラン履歴

## 🔧 実装されたコンポーネント

### 1. MemoryContextExtractor

記憶データを3層構造に適した形で抽出・分類するクラス

```python
class MemoryContextExtractor:
    def extract_for_pattern(self, pattern: str, agent_state: AgentState, 
                           target_file: Optional[str] = None) -> Dict[str, Any]:
        """パターンに基づいて記憶データを抽出"""
```

**特徴:**
- 3層構造に適した記憶データの分類
- パターン別の記憶データ抽出
- エラーハンドリングとフォールバック機能

### 2. Enhanced PromptCompiler

既存のPromptCompilerを拡張し、記憶注入機能を統合

```python
class PromptCompiler:
    def compile_with_memory(self, pattern: str, base_context: str, 
                           main_context: str = "", specialized_context: str = "",
                           agent_state: Optional[AgentState] = None, 
                           target_file: Optional[str] = None) -> str:
        """記憶データを統合した3層プロンプトを合成"""
```

**新機能:**
- 3層構造の記憶注入
- パターン別のトークン制限管理
- プロンプト長制限時の自動要約
- 既存機能との完全な互換性

### 3. Enhanced PromptContextService

PromptContextServiceとPromptCompilerの統合

```python
class PromptContextService:
    def compose_with_memory(self, pattern: PromptPattern, agent_state: AgentState,
                           target_file: Optional[str] = None) -> str:
        """記憶データを統合した3層プロンプトを合成"""
    
    def compose_enhanced(self, pattern: PromptPattern, agent_state: AgentState,
                         target_file: Optional[str] = None, 
                         use_memory_injection: bool = True) -> str:
        """拡張版プロンプト合成（記憶注入の有効/無効を選択可能）"""
```

**統合機能:**
- PromptCompilerとの完全統合
- 記憶注入の有効/無効選択
- パターンの自動最適化
- パターン比較・推奨機能

## 📋 利用可能なプロンプトパターン

### 1. BASE_SPECIALIZED（軽量版）
- **用途**: 高速処理、単純な専門処理
- **構成**: Base + Specialized
- **トークン制限**: 2,000
- **適用例**: ファイル要約、コード要約、エラー解析

### 2. BASE_MAIN（標準版）
- **用途**: 通常の対話応答、基本的なタスク実行
- **構成**: Base + Main
- **トークン制限**: 4,000
- **適用例**: ファイル操作、一般的な対話処理

### 3. BASE_MAIN_SPECIALIZED（完全版）
- **用途**: 複雑な計画立案、多段階タスク実行
- **構成**: Base + Main + Specialized
- **トークン制限**: 6,000
- **適用例**: プロジェクト計画、コードリファクタリング、複数ファイル処理

## 🚀 使用方法

### 基本的な使用例

```python
from companion.prompts.prompt_compiler import compile_with_memory
from companion.prompts.prompt_context_service import PromptContextService, PromptPattern

# PromptCompiler直接使用
result = compile_with_memory(
    pattern="base_main_specialized",
    base_context="システム設定",
    main_context="会話履歴",
    specialized_context="専門知識",
    agent_state=agent_state,
    target_file="target.py"
)

# PromptContextService経由での使用
service = PromptContextService()
result = service.compose_with_memory(
    PromptPattern.BASE_MAIN_SPECIALIZED,
    agent_state,
    "target.py"
)
```

### 記憶注入の制御

```python
# 記憶注入あり
result_with_memory = service.compose_enhanced(
    PromptPattern.BASE_MAIN_SPECIALIZED,
    agent_state,
    use_memory_injection=True
)

# 記憶注入なし（従来方式）
result_traditional = service.compose_enhanced(
    PromptPattern.BASE_MAIN_SPECIALIZED,
    agent_state,
    use_memory_injection=False
)
```

## 🔍 記憶データの詳細

### Base層記憶データ

```python
{
    "session_info": {
        "session_id": "session_001",
        "start_time": "2024-01-01T10:00:00",
        "duration": "30分"
    },
    "work_dir": "./work",
    "current_state": {
        "step": "EXECUTION",
        "status": "RUNNING",
        "retry_count": 0
    }
}
```

### Main層記憶データ

```python
{
    "recent_file_ops": [
        {
            "operation": "read",
            "file_path": "main.py",
            "timestamp": "2024-01-01T10:15:00"
        }
    ],
    "conversation_summary": {
        "total_messages": 5,
        "recent_topics": ["ファイル分析", "コード実行"],
        "summary": "ファイル分析とコード実行に関する会話",
        "last_message_time": "2024-01-01T10:20:00"
    },
    "operation_history": [
        {
            "type": "code_execution",
            "description": "Pythonスクリプトの実行",
            "timestamp": "2024-01-01T10:15:00"
        }
    ]
}
```

### Specialized層記憶データ

```python
{
    "file_cache": {
        "target_file": "main.py",
        "cached_content": "print('Hello World')",
        "cache_timestamp": "2024-01-01T10:00:00"
    },
    "summary_history": [
        {
            "type": "file_summary",
            "timestamp": "2024-01-01T10:10:00"
        }
    ],
    "plan_history": [
        {
            "type": "code_review",
            "status": "completed",
            "timestamp": "2024-01-01T10:05:00"
        }
    ]
}
```

## ⚙️ 設定とカスタマイズ

### トークン制限の調整

```python
# PromptCompilerでの設定
compiler = PromptCompiler()
compiler.layer_configs["base_main_specialized"]["token_limit"] = 8000
```

### 記憶データの分類カスタマイズ

```python
# MemoryContextExtractorでの設定
extractor = MemoryContextExtractor()
extractor.memory_categories["base"].append("custom_field")
```

## 🧪 テスト

### テストの実行

```bash
python test_prompt_compiler_memory_integration.py
```

### テスト内容

1. **MemoryContextExtractorテスト**: 記憶データ抽出の動作確認
2. **PromptCompiler記憶注入テスト**: 記憶注入機能の動作確認
3. **PromptContextService統合テスト**: 統合機能の動作確認
4. **記憶注入ワークフローテスト**: 実際の使用シナリオのテスト

## 🔄 既存システムとの統合

### 互換性

- 既存のPromptCompiler機能は完全に保持
- 既存のPromptContextService機能は完全に保持
- 段階的な移行が可能

### 統合ポイント

```python
# EnhancedCompanionCoreでの使用例
class EnhancedCompanionCore:
    def __init__(self):
        self.prompt_compiler = PromptCompiler()
        self.prompt_context_service = PromptContextService()
    
    async def generate_response(self, user_message: str, agent_state: AgentState):
        # 記憶注入版でのプロンプト生成
        system_prompt = self.prompt_context_service.compose_with_memory(
            PromptPattern.BASE_MAIN_SPECIALIZED,
            agent_state
        )
        # ... LLM呼び出し処理
```

## 📊 パフォーマンスと最適化

### 自動最適化機能

- **パターン最適化**: エージェント状態に基づく自動パターン選択
- **トークン制限**: 各パターンに適したトークン制限の自動適用
- **プロンプト要約**: 長すぎるプロンプトの自動要約

### キャッシュ機能

- コンパイル結果のキャッシュ
- 記憶データ抽出結果の最適化
- パターン情報のキャッシュ

## 🚨 エラーハンドリング

### フォールバック機能

- 記憶注入失敗時の従来方式への自動フォールバック
- パターン検証失敗時のデフォルトパターン使用
- エラー時の最小限プロンプト生成

### ログとモニタリング

- 詳細なログ出力
- 記憶注入の成功/失敗統計
- パフォーマンスメトリクス

## 🔮 今後の拡張予定

### Phase 2: 高度な記憶管理

- 長期記憶の実装
- 記憶の重要度スコアリング
- 記憶の自動要約・整理

### Phase 3: 動的パターン選択

- タスク複雑度に基づく自動パターン選択
- ユーザー設定によるパターンカスタマイズ
- A/Bテストによるパターン最適化

## 📝 まとめ

PromptCompilerの記憶注入機能統合により、3層構造の真の価値が実現されました：

1. **Base層**: システムの基本設定と制約を保持
2. **Main層**: 会話の文脈と短期記憶を管理
3. **Specialized層**: 専門知識と長期記憶を提供

この設計により、各層に適切な記憶データが配置され、プロンプトの品質と効率性が大幅に向上します。既存システムとの完全な互換性を保ちながら、新しい機能を段階的に活用できる柔軟なアーキテクチャとなっています。
