"""
Companion Help System with Approval System Integration

This module provides help and documentation for the companion system,
including detailed information about the approval system.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class HelpTopic:
    """Help topic information."""
    title: str
    description: str
    content: str
    keywords: List[str]
    category: str


class CompanionHelpSystem:
    """Comprehensive help system for Duckflow Companion."""
    
    def __init__(self):
        """Initialize help system with topics."""
        self.topics = self._initialize_help_topics()
    
    def _initialize_help_topics(self) -> Dict[str, HelpTopic]:
        """Initialize all help topics."""
        topics = {}
        
        # Approval System Topics
        topics["approval"] = HelpTopic(
            title="承認システム",
            description="ファイル操作の安全性を確保する承認システムについて",
            content=self._get_approval_help_content(),
            keywords=["approval", "承認", "security", "セキュリティ", "permission", "許可"],
            category="security"
        )
        
        topics["approval-modes"] = HelpTopic(
            title="承認モード",
            description="STRICT、STANDARD、TRUSTEDの各承認モードについて",
            content=self._get_approval_modes_content(),
            keywords=["mode", "モード", "strict", "standard", "trusted", "設定"],
            category="security"
        )
        
        topics["approval-config"] = HelpTopic(
            title="承認システム設定",
            description="承認システムの設定方法と除外パスの設定",
            content=self._get_approval_config_content(),
            keywords=["config", "設定", "configuration", "exclude", "除外"],
            category="configuration"
        )
        
        # File Operations Topics
        topics["file-ops"] = HelpTopic(
            title="ファイル操作",
            description="ファイルの作成、編集、削除などの基本操作",
            content=self._get_file_ops_content(),
            keywords=["file", "ファイル", "create", "作成", "edit", "編集", "delete", "削除"],
            category="operations"
        )
        
        # General Topics
        topics["getting-started"] = HelpTopic(
            title="はじめに",
            description="Duckflow Companionの基本的な使い方",
            content=self._get_getting_started_content(),
            keywords=["start", "はじめ", "basic", "基本", "tutorial", "チュートリアル"],
            category="general"
        )
        
        topics["commands"] = HelpTopic(
            title="コマンド一覧",
            description="利用可能なコマンドの一覧と説明",
            content=self._get_commands_content(),
            keywords=["command", "コマンド", "list", "一覧", "reference", "リファレンス"],
            category="reference"
        )
        
        return topics
    
    def get_help(self, query: Optional[str] = None) -> str:
        """Get help information based on query."""
        if not query:
            return self._get_main_help()
        
        # Search for matching topics
        matching_topics = self._search_topics(query.lower())
        
        if not matching_topics:
            return self._get_no_results_help(query)
        
        if len(matching_topics) == 1:
            return matching_topics[0].content
        
        # Multiple matches - show topic list
        return self._format_topic_list(matching_topics, query)
    
    def _search_topics(self, query: str) -> List[HelpTopic]:
        """Search for topics matching the query."""
        matching_topics = []
        
        for topic in self.topics.values():
            # Check title, description, and keywords
            if (query in topic.title.lower() or 
                query in topic.description.lower() or
                any(query in keyword.lower() for keyword in topic.keywords)):
                matching_topics.append(topic)
        
        return matching_topics
    
    def _get_main_help(self) -> str:
        """Get main help content."""
        return """
🤖 **Duckflow Companion ヘルプシステム**

こんにちは！Duckflow Companionの使い方についてお手伝いします。

## 🔍 ヘルプの使い方
- `help` - このヘルプメニューを表示
- `help <トピック>` - 特定のトピックのヘルプを表示
- `help 承認` - 承認システムについて
- `help コマンド` - 利用可能なコマンド一覧

## 📚 主要なトピック

### 🛡️ セキュリティ
- **承認システム** - ファイル操作の安全性確保
- **承認モード** - STRICT、STANDARD、TRUSTEDモード
- **承認設定** - 承認システムの設定方法

### 📁 操作
- **ファイル操作** - ファイルの作成、編集、削除
- **コマンド** - 利用可能なコマンド一覧

### 🚀 基本
- **はじめに** - 基本的な使い方
- **設定** - システム設定の方法

## 💡 ヒント
承認システムが有効になっているため、ファイル操作時には確認が求められます。
これはあなたの大切なファイルを保護するための機能です。

何かご質問があれば、お気軽にお聞きください！
"""
    
    def _get_approval_help_content(self) -> str:
        """Get approval system help content."""
        return """
🛡️ **承認システム**

Duckflow Companionには、あなたの大切なファイルとシステムを保護するための
承認システムが組み込まれています。

## 🔐 承認システムとは？

AIがファイルを作成、編集、削除する前に、あなたの明示的な許可を求めるシステムです。
これにより、予期しない操作や危険な操作を防ぐことができます。

## 📋 承認が必要な操作

### 🟡 高リスク操作（標準モード）
- ファイルの作成
- ファイルの編集・更新
- ファイルの削除
- コードの実行

### 🟢 承認不要の操作
- ファイルの読み取り
- ディレクトリの一覧表示
- 設定の確認

## 💬 承認要求の例

```
🤔 ちょっと相談があるのですが...

📝 **操作内容**
ファイル 'src/main.py' を作成 (内容: print("Hello, World!"))

🎯 **対象**: src/main.py
📊 **リスクレベル**: 🟡 高リスク

この操作を実行してもよろしいですか？ (y/n): 
```

## ✅ 承認する場合
- `y` または `yes` を入力
- 操作が実行されます
- 「承認いただきありがとうございます！」のメッセージが表示

## ❌ 拒否する場合
- `n` または `no` を入力
- 操作はキャンセルされます
- 代替案が提案される場合があります

## ⚙️ 承認モードの変更

詳細は `help 承認モード` をご覧ください。

## 🔧 設定のカスタマイズ

詳細は `help 承認設定` をご覧ください。

---
💡 **ヒント**: 承認システムはあなたの安全を守るためのものです。
不明な操作については遠慮なく拒否してください。
"""
    
    def _get_approval_modes_content(self) -> str:
        """Get approval modes help content."""
        return """
⚙️ **承認モード**

承認システムには3つのモードがあり、セキュリティレベルを調整できます。

## 🔒 STRICT（厳格）モード

**最高レベルのセキュリティ**
- 低リスク以外のすべての操作で承認が必要
- 本番環境や重要なプロジェクトに推奨

```
承認が必要: ファイル作成、編集、削除、コード実行
承認不要: ファイル読み取り、ディレクトリ一覧
```

## 🔐 STANDARD（標準）モード ⭐ **デフォルト**

**バランスの取れたセキュリティ**
- 高リスク以上の操作で承認が必要
- 日常的な開発作業に最適

```
承認が必要: ファイル作成、編集、削除、コード実行
承認不要: ファイル読み取り、ディレクトリ一覧
```

## 🔓 TRUSTED（信頼）モード

**最小限のセキュリティ**
- 重要リスク（システムファイル等）のみ承認が必要
- 個人プロジェクトやプロトタイピングに適している

```
承認が必要: システムファイルの変更、危険なコマンド
承認不要: 通常のファイル操作、コード実行
```

## 🔧 モードの変更方法

### コマンドで変更
```bash
# 標準モードに設定
companion config approval-mode standard

# 厳格モードに設定  
companion config approval-mode strict

# 信頼モードに設定
companion config approval-mode trusted
```

### 現在のモードを確認
```bash
companion config show approval-mode
```

## 💡 推奨設定

- **本番環境**: STRICT モード
- **開発環境**: STANDARD モード  
- **個人プロジェクト**: STANDARD または TRUSTED モード
- **学習・実験**: TRUSTED モード

---
⚠️ **注意**: モードを変更した場合、新しい設定は次回の操作から適用されます。
"""
    
    def _get_approval_config_content(self) -> str:
        """Get approval configuration help content."""
        return """
🔧 **承認システム設定**

承認システムの動作をカスタマイズする方法について説明します。

## 📁 設定ファイル

設定は `.companion/config.json` に保存されます：

```json
{
  "approval": {
    "mode": "standard",
    "timeout_seconds": 30,
    "excluded_paths": [
      "temp/*",
      "*.tmp",
      ".git/*"
    ]
  }
}
```

## ⏱️ タイムアウト設定

承認要求のタイムアウト時間を設定できます：

```bash
# 60秒に設定
companion config approval-timeout 60

# デフォルト（30秒）に戻す
companion config approval-timeout 30
```

## 🚫 除外パスの設定

特定のファイルやディレクトリを承認から除外できます：

### よく使用される除外パターン
```json
{
  "excluded_paths": [
    "temp/*",           // tempディレクトリ全体
    "*.log",            // ログファイル
    "*.tmp",            // 一時ファイル
    "test_*.py",        // テストファイル
    ".git/*",           // Gitディレクトリ
    "node_modules/*",   // Node.jsモジュール
    "__pycache__/*",    // Pythonキャッシュ
    "*.pyc"             // Pythonバイトコード
  ]
}
```

### 除外パスの追加
```bash
# 単一パスを追加
companion config add-excluded-path "logs/*"

# 複数パスを追加
companion config add-excluded-path "*.log" "temp/*" "build/*"
```

### 除外パスの削除
```bash
# 特定パスを削除
companion config remove-excluded-path "temp/*"

# すべての除外パスをクリア
companion config clear-excluded-paths
```

## 📊 ログ設定

承認システムのログレベルを調整できます：

```bash
# 詳細ログを有効化
companion config approval-log-level debug

# 標準ログレベル
companion config approval-log-level info

# エラーのみ
companion config approval-log-level error
```

## 🔍 設定の確認

現在の設定を確認：

```bash
# すべての承認設定を表示
companion config show approval

# 特定の設定を表示
companion config show approval-mode
companion config show approval-timeout
companion config show excluded-paths
```

## 🔄 設定のリセット

設定をデフォルトに戻す：

```bash
# 承認設定のみリセット
companion config reset approval

# すべての設定をリセット
companion config reset all
```

## 📋 設定例

### 開発環境向け設定
```json
{
  "approval": {
    "mode": "standard",
    "timeout_seconds": 45,
    "excluded_paths": [
      "temp/*",
      "*.log",
      "test_*",
      "__pycache__/*"
    ]
  }
}
```

### 本番環境向け設定
```json
{
  "approval": {
    "mode": "strict", 
    "timeout_seconds": 60,
    "excluded_paths": [
      "logs/*"
    ]
  }
}
```

---
💡 **ヒント**: 設定変更後は `companion restart` で設定を反映させてください。
"""
    
    def _get_file_ops_content(self) -> str:
        """Get file operations help content."""
        return """
📁 **ファイル操作**

Duckflow Companionでのファイル操作について説明します。

## 📝 基本的なファイル操作

### ファイル作成
```
「新しいPythonファイルを作成してください」
「main.pyというファイルを作って、Hello Worldを出力するコードを書いてください」
```

### ファイル編集
```
「main.pyに新しい関数を追加してください」
「設定ファイルのポート番号を8080に変更してください」
```

### ファイル読み取り
```
「main.pyの内容を見せてください」
「設定ファイルを確認してください」
```

### ファイル削除
```
「不要なファイルを削除してください」
「tempディレクトリを削除してください」
```

## 🛡️ 承認システムとの連携

### 承認が必要な操作
- ✅ ファイル作成
- ✅ ファイル編集・更新
- ✅ ファイル削除
- ✅ ディレクトリ作成・削除

### 承認不要の操作
- 📖 ファイル読み取り
- 📋 ディレクトリ一覧表示
- 🔍 ファイル検索

## 💬 承認要求の例

### ファイル作成時
```
🤔 ちょっと相談があるのですが...

📝 **操作内容**
ファイル 'src/utils.py' を作成 (内容: def helper_function():...)

🎯 **対象**: src/utils.py
📊 **リスクレベル**: 🟡 高リスク
📄 **プレビュー**: 
def helper_function():
    return "Hello from helper"

この操作を実行してもよろしいですか？ (y/n): 
```

### ファイル編集時
```
🤔 ちょっと相談があるのですが...

📝 **操作内容**
ファイル 'config.json' を更新 (変更: port: 3000 → 8080)

🎯 **対象**: config.json
📊 **リスクレベル**: 🟡 高リスク
🔄 **変更内容**: 
- "port": 3000
+ "port": 8080

この操作を実行してもよろしいですか？ (y/n): 
```

## 🔧 便利な機能

### バックアップ作成
重要なファイルを編集する前に、自動的にバックアップを提案します：

```
「設定ファイルを変更する前に、バックアップを作成しますか？」
```

### プレビュー機能
操作前に変更内容をプレビューできます：

```
「変更内容をプレビューで確認してから実行しますか？」
```

### 段階的実行
大きな変更を小さなステップに分けて実行できます：

```
「この変更を段階的に実行しますか？」
```

## ⚠️ 注意事項

### 危険な操作
以下の操作は特に注意が必要です：
- システムファイルの変更
- 設定ファイルの変更
- 大量のファイル削除
- 実行可能ファイルの作成

### 安全な操作
以下の操作は比較的安全です：
- テキストファイルの作成
- ドキュメントの編集
- ログファイルの確認

## 🆘 トラブルシューティング

### ファイル操作が拒否される
1. 承認モードを確認
2. 除外パスの設定を確認
3. ファイルの権限を確認

### 承認要求が表示されない
1. 承認システムが有効か確認
2. ログファイルでエラーを確認
3. 設定ファイルを確認

---
💡 **ヒント**: 不明な操作については遠慮なく質問してください。
安全性を最優先に、一緒に作業を進めましょう！
"""
    
    def _get_getting_started_content(self) -> str:
        """Get getting started help content."""
        return """
🚀 **はじめに**

Duckflow Companionへようこそ！あなたの開発作業をサポートする
AI相棒として、安全で効率的な開発環境を提供します。

## 👋 初回セットアップ

### 1. 承認システムの理解
Companionには安全性を確保するための承認システムが組み込まれています：
- ファイル操作前に確認を求めます
- あなたの許可なしに重要な変更は行いません
- 不明な操作は遠慮なく拒否してください

### 2. 基本的な使い方
```
# ヘルプを表示
help

# ファイルを作成
「新しいPythonファイルを作成してください」

# ファイルを確認
「現在のディレクトリのファイル一覧を見せてください」

# 設定を確認
companion config show
```

## 🛡️ 安全な使い方

### ✅ 推奨される操作
- 小さな変更から始める
- 操作内容を理解してから承認する
- 重要なファイルは事前にバックアップ
- 不明な点は質問する

### ⚠️ 注意が必要な操作
- システムファイルの変更
- 大量のファイル削除
- 設定ファイルの変更
- 実行可能ファイルの作成

## 💬 自然な対話

Companionとは自然な言葉で対話できます：

```
❌ 避けるべき表現:
「execute_file_operation('create', 'main.py')」

✅ 推奨される表現:
「main.pyというファイルを作って、Hello Worldを出力するコードを書いてください」
```

## 🔧 設定のカスタマイズ

### 承認モードの選択
- **STRICT**: 最高セキュリティ（本番環境）
- **STANDARD**: バランス型（開発環境）⭐ デフォルト
- **TRUSTED**: 最小限（個人プロジェクト）

```bash
# モードを変更
companion config approval-mode standard
```

### 除外パスの設定
頻繁に変更するファイルを除外：

```bash
# 一時ファイルを除外
companion config add-excluded-path "temp/*" "*.tmp"
```

## 📚 学習リソース

### 基本コマンド
- `help` - ヘルプシステム
- `help 承認` - 承認システムについて
- `help コマンド` - コマンド一覧

### 設定コマンド
- `companion config show` - 現在の設定
- `companion config approval-mode <mode>` - 承認モード変更
- `companion status` - システム状態確認

## 🎯 最初のプロジェクト

### ステップ1: プロジェクト作成
```
「新しいPythonプロジェクトを作成してください。
main.pyファイルを作って、簡単なHello Worldプログラムを書いてください。」
```

### ステップ2: 承認の練習
- 操作内容を確認
- 理解できる内容なら `y` で承認
- 不明な点があれば質問

### ステップ3: ファイル確認
```
「作成されたファイルの内容を確認してください」
```

## 🆘 困ったときは

### よくある質問
- `help` - 一般的なヘルプ
- `help 承認` - 承認システムについて
- `help トラブルシューティング` - 問題解決

### サポート
- 不明な操作は遠慮なく質問
- エラーメッセージは詳しく教えてください
- ログファイル: `.companion/logs/`

---
🎉 **準備完了！**
これでDuckflow Companionを安全に使い始める準備ができました。
何かご質問があれば、お気軽にお聞きください！
"""
    
    def _get_commands_content(self) -> str:
        """Get commands help content."""
        return """
📋 **コマンド一覧**

Duckflow Companionで利用可能なコマンドの一覧です。

## 🔧 設定コマンド

### 承認システム設定
```bash
# 承認モードの変更
companion config approval-mode <strict|standard|trusted>

# タイムアウト設定
companion config approval-timeout <seconds>

# 除外パス追加
companion config add-excluded-path <pattern>

# 除外パス削除  
companion config remove-excluded-path <pattern>

# 設定表示
companion config show [setting]

# 設定リセット
companion config reset [approval|all]
```

### システム設定
```bash
# システム状態確認
companion status

# システム再起動
companion restart

# ログレベル設定
companion config log-level <debug|info|warning|error>

# 設定ファイル場所
companion config path
```

## 📁 ファイル操作コマンド

### 基本操作
```bash
# ファイル作成（対話的）
「<ファイル名>を作成してください」

# ファイル編集（対話的）
「<ファイル名>を編集してください」

# ファイル確認（対話的）
「<ファイル名>の内容を見せてください」

# ディレクトリ一覧（対話的）
「ファイル一覧を表示してください」
```

## 💬 対話コマンド

### ヘルプシステム
```bash
# メインヘルプ
help

# 特定トピック
help <トピック名>
help 承認
help コマンド
help 設定
```

### 質問・相談
```bash
# 自然な対話
「Pythonファイルを作成したいのですが...」
「設定を変更する方法を教えてください」
「このエラーの解決方法は？」
```

## 🛡️ 承認システムコマンド

### 承認応答
```bash
# 承認
y / yes / はい

# 拒否  
n / no / いいえ

# 詳細確認
? / help / 詳細
```

### 承認履歴
```bash
# 承認ログ確認
companion logs approval

# 最新の承認履歴
companion logs approval --recent

# 承認統計
companion stats approval
```

## 🔍 情報確認コマンド

### システム情報
```bash
# バージョン情報
companion version

# システム情報
companion info

# 設定サマリー
companion summary
```

### ログ確認
```bash
# 全ログ確認
companion logs

# エラーログのみ
companion logs --error

# 特定期間のログ
companion logs --since "2024-01-01"
```

## 🚀 開発支援コマンド

### プロジェクト管理
```bash
# プロジェクト初期化
「新しいプロジェクトを作成してください」

# 依存関係管理
「requirements.txtを作成してください」

# テスト実行
「テストを実行してください」
```

### コード支援
```bash
# コードレビュー
「このコードをレビューしてください」

# リファクタリング
「このコードを改善してください」

# ドキュメント生成
「このコードのドキュメントを作成してください」
```

## ⚙️ 高度なコマンド

### バッチ操作
```bash
# 複数ファイル操作
「複数のファイルを一括で処理してください」

# 設定の一括変更
companion config batch-update <config-file>
```

### 自動化
```bash
# スクリプト実行
companion run-script <script-name>

# 定期実行設定
companion schedule <command> <interval>
```

## 📖 使用例

### 日常的な使用
```bash
# 朝の作業開始
companion status
help

# ファイル作業
「今日のタスクファイルを作成してください」
「昨日の作業ログを確認してください」

# 設定確認
companion config show approval-mode
```

### プロジェクト開始時
```bash
# 新規プロジェクト
「Pythonプロジェクトを作成してください」
companion config approval-mode standard

# 設定カスタマイズ
companion config add-excluded-path "temp/*" "*.log"
```

---
💡 **ヒント**: 
- コマンドは大文字小文字を区別しません
- 自然な日本語での対話も可能です
- 不明なコマンドは `help` で確認してください
"""
    
    def _format_topic_list(self, topics: List[HelpTopic], query: str) -> str:
        """Format a list of matching topics."""
        result = f"🔍 **'{query}' に関連するヘルプトピック**\n\n"
        
        for i, topic in enumerate(topics, 1):
            result += f"{i}. **{topic.title}**\n"
            result += f"   {topic.description}\n"
            result += f"   使用方法: `help {topic.title.lower()}`\n\n"
        
        result += "💡 特定のトピックを表示するには、`help <トピック名>` を使用してください。"
        return result
    
    def _get_no_results_help(self, query: str) -> str:
        """Get help content when no results found."""
        return f"""
❓ **'{query}' に関するヘルプが見つかりませんでした**

## 📚 利用可能なヘルプトピック

### 🛡️ セキュリティ
- `help 承認` - 承認システムについて
- `help 承認モード` - 承認モードの設定
- `help 承認設定` - 承認システムの設定

### 📁 操作
- `help ファイル操作` - ファイルの作成、編集、削除
- `help コマンド` - 利用可能なコマンド一覧

### 🚀 基本
- `help はじめに` - 基本的な使い方
- `help` - メインヘルプメニュー

## 💬 その他の方法

質問や相談も自然な言葉で受け付けています：
- 「承認システムについて教えて」
- 「ファイルを作成する方法は？」
- 「設定を変更したい」

お気軽にお聞きください！
"""


# Global help system instance
help_system = CompanionHelpSystem()


def get_help(query: Optional[str] = None) -> str:
    """Get help information."""
    return help_system.get_help(query)


def search_help(keywords: List[str]) -> List[str]:
    """Search help topics by keywords."""
    results = []
    for keyword in keywords:
        topics = help_system._search_topics(keyword.lower())
        for topic in topics:
            if topic.title not in results:
                results.append(topic.title)
    return results