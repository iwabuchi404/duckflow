# Simple Dual-Loop System - シンプル設計ドキュメント

**バージョン:** 1.0  
**作成日:** 2025 年 8 月 15 日  
**目標:** シンプルで実用的な対話継続システム

---

## 🎯 基本コンセプト

**問題:** 現在の Duckflow はタスク実行中に対話ができない  
**解決:** 対話とタスク実行を分離し、両方を同時に動かす

### 核心アイデア

```
対話ループ: ユーザーとずっと話せる
実行ループ: バックグラウンドでタスクを処理
```

**これだけ。** 複雑な設計は不要。

## 🏗️ シンプル設計

### 基本構造

```
┌─────────────────────┐    ┌─────────────────────┐
│   対話ループ          │◄──►│   実行ループ          │
│   (ChatLoop)        │    │   (TaskLoop)        │
│                     │    │                     │
│ - ユーザーとの対話    │    │ - タスクの実行       │
│ - 進捗の確認         │    │ - 進捗の報告         │
│ - 指示の受付         │    │ - エラーの通知       │
└─────────────────────┘    └─────────────────────┘
```

### 2 つのループだけ

**ChatLoop（対話ループ）:**

- 既存の`companion/core.py`を拡張
- ユーザー入力を常に受け付け
- タスク状況を確認・表示

**TaskLoop（実行ループ）:**

- バックグラウンドでタスク実行
- 進捗を ChatLoop に報告
- 完了・エラーを通知

**通信:** Python の`queue.Queue`で十分

## 💻 実装設計

### ChatLoop（対話ループ）

```python
class ChatLoop:
    """シンプルな対話ループ"""

    def __init__(self):
        self.companion = CompanionCore()  # 既存を活用
        self.task_queue = queue.Queue()   # タスク送信用
        self.status_queue = queue.Queue() # 状態受信用
        self.running = True

    def run(self):
        """メインループ"""
        while self.running:
            # ユーザー入力を受け付け
            user_input = get_user_input()

            # タスクかどうか判定
            if self.is_task_request(user_input):
                # タスクループに送信
                self.task_queue.put(user_input)
                print("タスクを開始しました")
            else:
                # 通常の対話
                response = self.companion.process_message(user_input)
                print(response)

            # タスクの状況確認
            self.check_task_status()
```

### TaskLoop（実行ループ）

```python
class TaskLoop:
    """シンプルなタスク実行ループ"""

    def __init__(self):
        self.task_queue = queue.Queue()   # タスク受信用
        self.status_queue = queue.Queue() # 状態送信用
        self.current_task = None
        self.running = True

    def run(self):
        """実行ループ"""
        while self.running:
            try:
                # 新しいタスクを取得
                task = self.task_queue.get(timeout=1)
                self.execute_task(task)
            except queue.Empty:
                continue  # タスクがなければ待機

    def execute_task(self, task_description):
        """タスクを実行"""
        self.status_queue.put("実行中...")

        # 既存のファイル操作などを使用
        result = self.companion.handle_file_operation(task_description)

        self.status_queue.put(f"完了: {result}")
```

## 🔄 動作フロー

### 基本的な流れ

```
1. ユーザー: "ファイルを読んでレビューして"
2. ChatLoop: タスクと判定 → TaskLoopに送信
3. ChatLoop: "タスクを開始しました" と表示
4. TaskLoop: バックグラウンドで実行開始
5. ユーザー: "今どこまで進んだ？"
6. ChatLoop: TaskLoopの状況を確認 → "ファイル読み取り中です"
7. TaskLoop: 完了 → "レビュー完了しました"
8. ChatLoop: 結果を表示
```

### 割り込み処理

```
実行中に別の質問 → ChatLoopが即座に応答
実行中に新しいタスク → 現在のタスク完了後に実行
```

**これだけ。** 複雑な状態管理やメッセージバスは不要。

## 📋 実装計画

### Phase 1: 基本実装（1 週間）

```python
# 約200行で実現
files_to_create:
  - companion/dual_loop.py      # メインシステム
  - companion/chat_loop.py      # 対話ループ
  - companion/task_loop.py      # 実行ループ

modifications:
  - main_companion.py           # DualLoopSystemを使用
  - companion/core.py           # タスク判定メソッド追加
```

**機能:**

- 基本的な 2 ループ動作
- タスク実行中も対話可能
- 進捗確認機能

### Phase 2: 改善（1 週間）

```python
enhancements:
  - タスクキューの改善
  - エラーハンドリング強化
  - 進捗表示の改善
  - 複数タスクの順次実行
```

---

### Step 2: 対話的実行（2 週間）

**目標:** タスク実行の透明性向上と基本的な割り込み処理

**追加機能:**

```python
chat_loop_enhancements:
  - 進捗の自動表示
  - 実行状況の詳細問い合わせ
  - 簡単な割り込み処理（一時停止/再開）

task_loop_enhancements:
  - 定期的な進捗報告
  - チェックポイント機能
  - タスクの分割実行

simple_pecking_order:
  - 2階層のタスク分割（親・子）
  - 順次実行のみ
  - 基本的な依存関係
```

**ユーザー体験:**

```text
User: "複数のファイルをレビューして"
Assistant: "3つのファイルを見つけたよ。順番に見ていくね"
[実行中...]
User: "今どこまで進んだ？"
Assistant: "2つ目のファイルを確認中！あと1つだよ"
User: "ちょっと待って"
Assistant: "一時停止しました。再開するときは教えてね"
```

---

### Step 3: 協調的計画（3 週間）

**目標:** ユーザーとの共同計画立案と動的調整

**高度な機能:**

```python
collaborative_planning:
  - タスク計画の事前提示
  - ユーザーフィードバックの反映
  - 実行中の計画変更対応

advanced_execution:
  - 動的な実行順序調整
  - 並列実行の基礎
  - エラーリカバリ機能

full_pecking_order:
  - 3階層以上の階層構造
  - 依存関係の管理
  - 優先順位付け
  - 実行時間の推定
```

**ユーザー体験:**

```text
User: "プロジェクトのリファクタリングをして"
Assistant: "大きなタスクだね。こんな感じで進めるのはどう？
  1. テストの確認 (5分)
  2. コードの分析 (10分)
    2.1 複雑度の測定
    2.2 重複の検出
  3. リファクタリング実行 (20分)
  順番変えたい？"
User: "テストは後でいいよ"
Assistant: "了解！じゃあコード分析から始めるね"
```

---

### Step 4: 理想的な相棒（長期目標）

**目標:** 学習機能と感情的サポートを持つ真の相棒

**革新的機能:**

```python
intelligent_companion:
  - 完全非同期処理
  - 複数の会話スレッド
  - 文脈の深い理解
  - 感情的サポート

autonomous_execution:
  - 真の並列実行
  - 自律的な最適化
  - 予測的タスク準備

learning_pecking_order:
  - 動的な再計画
  - 学習による最適化
  - パターン認識
  - リスク評価と管理
  - ユーザー好みの学習
```

**ユーザー体験:**

```text
User: "いつものやつお願い"
Assistant: "月曜恒例のコードレビューだね！
  前回は src/ から見たけど、今回もその順番でいい？
  あ、でも今日は tests/ に更新が多いみたいだよ"
User: "じゃあ tests/ から"
Assistant: "了解！並列で依存関係も調べておくね
  何か気になることがあったらすぐ教えて"
[並行して実行中...]
User: "ちょっと疲れた"
Assistant: "結構長時間やってるもんね。
  キリのいいところまでやったら休憩しない？
  あと2ファイルで区切りがいいよ"
```

---

## 🔄 データフロー設計

### タスク実行フロー

```text
1. ユーザー入力
   ↓
2. ChatLoop: 意図分析
   ↓
3. タスク要求の場合
   ↓
4. Pecking Order: タスク分解・計画
   ↓
5. ユーザーと計画の調整（ChatLoop経由）
   ↓
6. TaskLoop: 実行開始
   ↓
7. 各タスクの実行
   ├── 進捗報告 → ChatLoop → ユーザー
   ├── エラー発生 → ChatLoop → ユーザー相談
   └── 完了 → 次のタスクへ
   ↓
8. 全体完了報告
```

### 割り込み処理フロー

```text
1. タスク実行中のユーザー入力
   ↓
2. ChatLoop: 割り込み判定
   ↓
3. TaskLoopへ通知
   ↓
4. チェックポイントで一時停止
   ↓
5. ユーザーとの対話
   ↓
6. 再開/中止/変更の判断
```

**段階的に機能追加。** 最初はシンプルに。

## 🛠️ 技術仕様

### 必要なもの

```python
# 標準ライブラリのみ
import threading
import queue
import time

# 既存のDuckflowコンポーネント
from companion.core import CompanionCore
from codecrafter.ui.rich_ui import rich_ui
```

**外部依存なし。** 既存のコードを最大活用。

---

## 🎯 まとめ

### 実現する価値

- **継続的対話**: タスク実行中も会話できる
- **透明性**: 進捗がいつでも確認できる
- **柔軟性**: 実行中に質問や指示ができる

### 実装の特徴

- **シンプル**: 2 つのループとキューだけ
- **軽量**: 約 200 行で実現
- **実用的**: 既存システムを最大活用

**複雑な設計は不要。** シンプルで実用的なシステムを目指します。

---

**Version:** 1.0 (Simple)  
**Next Step:** Phase 1 実装開始
