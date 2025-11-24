# Enhanced v2.0システム 設計原則

## 🎯 **設計哲学**

### **1. 単一責任の原則 (Single Responsibility Principle)**
- **EnhancedCompanionCore**: 統合コア機能のみ
- **EnhancedChatLoop**: ユーザー入力処理とAIタスクディスパッチ
- **EnhancedTaskLoop**: タスク実行と状態管理
- **AgentState**: 状態の単一ソース・オブ・トゥルース

### **2. 依存関係の方向性統一**
```
UI Layer (rich_ui)
    ↓
Enhanced Layer (enhanced_core, enhanced_dual_loop)
    ↓
Core Layer (agent_state, file_ops, code_runner)
    ↓
Base Layer (llm_client, validators)
```

### **3. 型安全性の確保**
- **ActionType**: 明示的な型定義
- **Step/Status**: 列挙型による状態管理
- **インターフェース**: 明確な契約定義

## 🔧 **実装ガイドライン**

### **1. エラーハンドリング**
- **フォールバック**: 機能が利用できない場合の適切な代替処理
- **ログ出力**: デバッグ可能な詳細ログ
- **ユーザー体験**: エラー時も適切なフィードバック

### **2. 状態管理**
- **AgentState**: 唯一の状態書き込み先
- **読み取り専用**: 他のコンポーネントは状態を読み取りのみ
- **状態同期**: 一方向の状態更新

### **3. 拡張性**
- **プラグイン方式**: 新機能の追加が容易
- **設定可能**: 動作パラメータの外部化
- **テスト可能**: 単体テストと統合テストの両立
