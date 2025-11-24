# システム削除実行計画

**作成日**: 2025-08-20  
**対象**: v1.0 Standard & v4.0 Final削除  
**目的**: Enhanced v2.0への統一によるシステム簡素化

---

## 📋 **削除対象システム詳細**

### **🔴 v1.0 Standard System**

#### **削除ファイル一覧**
```
companion/dual_loop.py                    # メインシステムクラス
├── DualLoopSystem クラス
├── 基本的なキュー管理
└── シンプルなループ制御
```

#### **参照ファイル (更新必要)**
```
main_companion.py                         # フォールバック削除
├── from companion.dual_loop import DualLoopSystem  ❌
├── self.dual_loop_system = DualLoopSystem()        ❌  
└── フォールバック処理ロジック                        ❌

テストファイル (12個)
├── test_*.py - DualLoopSystem関連テスト     ❌
├── integration/test_phase1_*.py           ❌
└── test_enhanced_dual_loop_integration.py ⚠️ (部分削除)
```

### **🔴 v4.0 Final System (Refactored)**

#### **削除ファイル一覧**
```
companion/chat_loop.py (Refactored版)     # 簡略化された対話ループ
├── 4引数ChatLoop(__init__)
├── WorkspaceManager直接統合
├── 非同期入力処理
└── 基本コマンド処理

companion/task_loop.py (Refactored版)     # 簡略化されたタスクループ  
├── 4引数TaskLoop(__init__)
├── 基本的なタスク実行
├── process_intent処理
└── シンプルなエラーハンドリング
```

#### **依存関係 (置換必要)**
```
companion/enhanced_dual_loop.py           # 現在v4.0版を使用中
├── from .chat_loop import ChatLoop        ⚠️ (v4.0版)
├── from .task_loop import TaskLoop        ⚠️ (v4.0版)  
└── 初期化: ChatLoop(..., self)           ⚠️ (4引数形式)
```

---

## 🚨 **削除前リスク分析**

### **v1.0 Standard削除リスク**

| リスク項目 | 影響度 | 確率 | 対策 |
|-----------|-------|------|-----|
| フォールバック失効 | 低 | 低 | Enhanced v2.0安定化確認 |
| テスト破綻 | 中 | 高 | 削除前テスト更新 |
| ドキュメント不整合 | 低 | 中 | 同時更新 |

**総合リスク**: 🟢 **低** - 即座に削除可能

### **v4.0 Final削除リスク**

| リスク項目 | 影響度 | 確率 | 対策 |
|-----------|-------|------|-----|
| Enhanced v2.0動作停止 | 高 | 高 | Enhanced専用版先行作成 |
| 機能欠損 | 中 | 中 | 機能移植の完全性確認 |
| 設定互換性 | 低 | 低 | 設定統一 |

**総合リスク**: 🟡 **中** - 慎重な段階的削除必要

---

## 🗂️ **削除実行手順**

## **Phase 1: v1.0 Standard削除 (即座実行)**

### **Step 1.1: main_companion.py更新**
```python
# 削除対象コード
from companion.dual_loop import DualLoopSystem  # フォールバック用 ❌

# 削除対象ロジック  
except Exception as e:
    # フォールバック: 標準版を使用 ❌
    rich_ui.print_message(f"Enhanced版の初期化に失敗: {e}", "warning")
    rich_ui.print_message("📋 標準版Dual-Loop Systemを使用します", "info") ❌
    self.dual_loop_system = DualLoopSystem() ❌
    self.system_version = "Standard v1.0" ❌
```

**更新後コード**:
```python
# Enhanced版のみ使用
try:
    if ENHANCED_AVAILABLE:
        self.dual_loop_system = EnhancedDualLoopSystem()
        self.system_version = "Enhanced v2.0"
    else:
        raise ImportError("Enhanced版が利用できません")
except Exception as e:
    rich_ui.print_error(f"システム初期化に失敗しました: {e}")
    raise  # フォールバックなしで終了
```

### **Step 1.2: ファイル削除**
```bash
# 削除コマンド
rm companion/dual_loop.py

# 確認コマンド  
find . -name "*.py" -exec grep -l "DualLoopSystem" {} \;
find . -name "*.py" -exec grep -l "dual_loop.*import" {} \;
```

### **Step 1.3: テストファイル整理**
```bash
# 削除対象テスト
rm tests/integration/test_phase1_core.py     # 標準版テスト
rm tests/integration/test_phase1_flow.py    # 標準版テスト

# 更新対象テスト (DualLoopSystem参照削除)
tests/test_enhanced_dual_loop_integration.py
tests/test_plan_tool_integration.py
test_main_integration.py
```

## **Phase 2: Enhanced専用ChatLoop/TaskLoop作成**

### **Step 2.1: Enhanced版ChatLoop設計**
```python
# companion/enhanced_chat_loop.py (新規作成)
class EnhancedChatLoop:
    """Enhanced Dual-Loop System専用ChatLoop
    
    v4.0 Final版からの改善点:
    - Enhanced v2.0状態管理との完全統合
    - WorkspaceManager統合維持
    - エラーハンドリング強化
    """
    
    def __init__(self, task_queue, status_queue, enhanced_companion, dual_loop_system):
        # Enhanced v2.0専用の初期化処理
        pass
```

### **Step 2.2: Enhanced版TaskLoop設計**
```python  
# companion/enhanced_task_loop.py (新規作成)
class EnhancedTaskLoop:
    """Enhanced Dual-Loop System専用TaskLoop
    
    v4.0 Final版からの改善点:
    - 状態同期システム対応
    - Enhanced CompanionCore統合
    - 堅牢なエラー処理
    """
    
    def __init__(self, task_queue, status_queue, enhanced_companion, dual_loop_system):
        # Enhanced v2.0専用の初期化処理
        pass
```

### **Step 2.3: 機能移植チェックリスト**
```
📋 v4.0 Final → Enhanced版機能移植
├── ✅ 非同期対話処理 (ChatLoop)
├── ✅ WorkspaceManager統合 (ChatLoop)  
├── ✅ 基本コマンド (cd, ls, pwd, help, status)
├── ✅ AI意図理解ディスパッチ (ChatLoop)
├── ✅ process_intentタスク処理 (TaskLoop)
├── ✅ 基本的なエラーハンドリング
└── ⚠️ Enhanced v2.0状態管理統合 (新規)
```

## **Phase 3: v4.0 Final削除**

### **Step 3.1: Enhanced v2.0更新**
```python
# companion/enhanced_dual_loop.py 更新
from .enhanced_chat_loop import EnhancedChatLoop      # 変更
from .enhanced_task_loop import EnhancedTaskLoop      # 変更

# Initialize loops with a reference to the parent system
self.chat_loop = EnhancedChatLoop(self.task_queue, self.status_queue, self.enhanced_companion, self)
self.task_loop = EnhancedTaskLoop(self.task_queue, self.status_queue, self.enhanced_companion, self)
```

### **Step 3.2: v4.0 Final削除**
```bash
# 削除コマンド
rm companion/chat_loop.py     # Refactored版  
rm companion/task_loop.py     # Refactored版

# 確認コマンド
find . -name "*.py" -exec grep -l "Refactored" {} \;
```

---

## ✅ **削除完了確認チェックリスト**

### **v1.0 Standard削除確認**
- [ ] `companion/dual_loop.py` ファイル削除完了
- [ ] `main_companion.py` フォールバック削除完了  
- [ ] DualLoopSystemインポート参照なし
- [ ] Enhanced v2.0単体での起動確認
- [ ] 関連テストの削除/更新完了

### **v4.0 Final削除確認**
- [ ] Enhanced専用ChatLoop動作確認
- [ ] Enhanced専用TaskLoop動作確認
- [ ] `companion/chat_loop.py (Refactored)` 削除完了
- [ ] `companion/task_loop.py (Refactored)` 削除完了  
- [ ] WorkspaceManager機能動作確認
- [ ] 基本コマンド (cd, ls, pwd) 動作確認

### **システム統合確認**
- [ ] Enhanced v2.0単体での完全動作
- [ ] エラーレート前回比改善
- [ ] メモリ使用量削減確認
- [ ] 起動時間短縮確認

---

## 🚨 **緊急時回復手順**

### **削除による問題発生時**
1. **Git復旧**: `git checkout HEAD~1 [削除ファイル]`  
2. **動作確認**: システム起動テスト
3. **段階的再削除**: より慎重なアプローチで再実行

### **Enhanced v2.0異常時**
1. **ログ分析**: エラー内容の詳細調査
2. **依存関係確認**: インポート関係の再検証  
3. **最小構成テスト**: コンポーネント単体での動作確認

---

## 📊 **削除効果測定**

### **定量的指標**
- **ファイル数減少**: 削除前 vs 削除後
- **コード行数減少**: システム全体の軽量化
- **インポート数減少**: 依存関係の簡素化
- **メモリ使用量**: 起動時メモリ消費量

### **定性的指標**  
- **保守性**: コードの理解しやすさ
- **安定性**: エラー発生頻度
- **拡張性**: 新機能追加の容易さ

**この削除計画により、Enhanced v2.0への統一とシステム簡素化を安全に実現できます。**