# Duckflow Memory Extension: Archives & Search 設計書

## 1. 概要
本ドキュメントは、`Golden Fish Memory Protocol` における **「中期記憶 (The Gravel Cache)」** および **「想起 (Recollection)」** の機能を実装するための技術設計書である。
現在の `MemoryManager` がコンテキストウィンドウ制御のために削除（忘却）しているメッセージを、ファイルとして永続化（アーカイブ）し、エージェントが必要に応じて自発的に検索・参照できる仕組みを構築する。

## 2. アーキテクチャ

### 2.1 データフロー
1.  **会話発生**: ユーザーとエージェントの会話が進む。
2.  **メモリ整理 (Pruning)**: `MemoryManager` がコンテキスト上限を検知し、古いメッセージをリストから除外する。
3.  **アーカイブ (Archiving)**: 除外されたメッセージを**即座に**アーカイブファイルへ追記保存する。
4.  **検索 (Searching)**: エージェントがツール `search_archives` を使用し、過去のログから情報を引き出す。

### 2.2 ファイル構造
アーカイブデータは日次のJSONL (JSON Lines) 形式で保存する。これにより、追記が容易で、破損リスクを最小限に抑える。

```
logs/
  archives/
    2024-12-06.jsonl
    2024-12-07.jsonl
    ...
```

**レコード形式 (JSONLの各行):**
```json
{
  "timestamp": "2024-12-07T10:15:30.123456",
  "role": "user",
  "content": "...メッセージ内容...",
  "metadata": {
    "task_id": "...",    // あれば
    "tool_name": "..."   // ツール実行結果の場合
  }
}
```

## 3. コンポーネント設計

### 3.1 `ArchiveStorage` クラス (新規)
アーカイブの書き込みと読み込みを担当する責務を持つクラス。`MemoryManager` から利用される。

*   **場所**: `companion/modules/memory/archive_storage.py`
*   **主要メソッド**:
    *   `archive_messages(messages: List[Dict])`: メッセージリストを受け取り、今日の日付のファイルに追記する。
    *   `search(query: str, date_range: Tuple[date, date] = None, limit: int = 10) -> List[Dict]`: アーカイブ済みメッセージを検索する。

### 3.2 `MemoryManager` の拡張
`companion/modules/memory.py` を修正し、`prune_history` メソッド内で削除対象 (`removed_messages`) が確定した時点で `ArchiveStorage.archive_messages` を呼び出す。

### 3.3 `SearchArchivesTool` (新規ツール)
エージェントがアーカイブを検索するためのインターフェース。

*   **ツール名**: `search_archives`
*   **説明**: "Search past conversation logs for specific keywords. Use this to recall details that have been cleared from short-term memory."
*   **引数**:
    *   `query` (str): 検索したいキーワード（スペース区切りでAND検索）。
    *   `limit` (int, optional): 取得件数上限（デフォルト: 5）。
*   **動作**:
    1.  `ArchiveStorage.search` を呼び出す。
    2.  結果を見やすい形式（`[2024-12-07 User]: ...`）に整形して返す。

## 4. 実装ステップ

### Phase 1: 保存機構の実装
1.  `companion/modules/memory/archive_storage.py` を作成。
2.  `setup_logging` 等で `logs/archives` ディレクトリの自動作成を確認。
3.  `MemoryManager` に統合し、ユニットテストで「削除されたメッセージがファイルに保存されるか」を確認。

### Phase 2: 検索ツールの実装
1.  `ArchiveStorage` に検索ロジック（キーワードマッチング）を実装。
    *   単純な文字列マッチングから開始。
    *   新しいファイル（日付が新しいもの）から順に走査し、ヒットしたら返す。
2.  `companion/tools/memory_tool.py` を作成し、`search_archives` を実装。
3.  `DuckAgent` (`core.py`) にツールを登録。

### Phase 3: プロンプト調整
1.  システムプロンプトに「過去のことは `search_archives` で思い出せる」という指示を追加。
2.  「思い出して」と言われた時にツールを使う挙動をテスト。

## 5. 将来の拡張性 (Out of Scope)
*   **ベクトル検索**: JSONLの内容を並行してChromaDB等に入れれば、意味検索が可能になる。今回はテキスト一致検索にとどめる。
*   **重要度フィルタ**: 全てではなく、重要と判断されたものだけを保存する（現在は全て保存する方針で、ディスク容量はテキストなので軽微と判断）。
