# ファイル操作/承認フロー 改修設計（現実適応版）

最終更新: 2025-08-16
対象範囲: companion/file_ops.py, companion/approval_system.py, companion/workspace_manager.py, codecrafter/ui/rich_ui.py, companion/enhanced_dual_loop.py

---

## 1. 背景と課題の要約
- ログ上は `FILE_OPERATION:CREATE:design-doc.md` と表示されるが、実ファイルが作成されていない。
- 高抽象度の要求でも安全な新規ファイル作成等の低リスク操作を実行せず、確認質問で停止。
- 承認（Approval）と実行、UI表示が分断され、見かけ上の完了が先行するケースがある。

根本原因の仮説:
- 承認フローと実操作の責務分離が曖昧（UIカード生成が先行）。
- `file_ops` のポスト条件（存在/内容一致）検証が弱く、結果を上流に還元できていない。
- 冪等性/ロールバック戦略がなく、実行に消極的。

---

## 2. 改修目標（受け入れ基準）
- 実行完了＝ポスト条件検証完了（存在/内容ハッシュ一致）までを一体化。
- 低リスク操作（新規作成、追記、既存非破壊読み取り）は「デフォルト提案→承認→即実行」が可能。
- UI表示は実行結果イベントに連動（擬似完了を禁止）。
- すべての `file_ops` は冪等・結果型で返す（成功/差分/スキップ理由）。

---

## 3. 設計方針

### 3.1 結果型 ResultContract
```python
@dataclass
class FileOpOutcome:
    ok: bool
    op: Literal["create", "write", "read", "delete", "mkdir", "move", "copy"]
    path: str
    reason: str | None
    before_hash: str | None
    after_hash: str | None
    changed: bool  # 変更が発生したか
```
- すべてのファイル操作は `FileOpOutcome` を返し、上流（DualLoop/UI/ログ）がこの契約に依存。

### 3.2 冪等化・検証
- 書き込み系: 実行前に現状ハッシュ→実行→ハッシュ再計算→一致で `ok=True, changed=(before!=after)`。
- 読み取り系: ハッシュ算出のみ。
- 既存と同一内容なら `changed=False` で早期終了。

### 3.3 承認→実行→検証 一体化 API
```python
def apply_with_approval(plan: FilePlan) -> FileOpOutcome:
    # 1) diff/影響提示 2) ユーザー承認 3) 実行 4) 検証 5) 結果イベント発火
```
- `approval_system.py` に統合ヘルパを追加。UIはこの関数の結果イベントにだけ連動。

### 3.4 安全デフォルトの導入
- 新規作成: ファイルがなければ `create` を即提案（パスとテンプレ内容にデフォルト値）。
- 上書き疑義: 選択肢（上書き/別名/プレビュー差分）を1回だけ提示。既定はプレビュー→上書き。

### 3.5 UI 連動の見直し
- FILE_OPERATIONカードは「検証後の成功イベント」から生成。
- 実行前は PREVIEW カード（差分/影響）を使用、成功と明確に区別。

---

## 4. 変更点（モジュール別）

- companion/file_ops.py
  - 既存関数を結果型で統一（上記 `FileOpOutcome`）。
  - ハッシュ計算（SHA-256）ユーティリティを追加。
  - `create_file`, `write_file`, `ensure_dir`, `read_file` に冪等/検証を実装。

- companion/approval_system.py
  - `apply_with_approval(plan)` を新設。差分/影響→承認→実行→検証→イベント発火まで一貫。
  - ロールバック方針: 失敗時は変更前ハッシュとバックアップファイルにより復旧（tmp/またはメモリ退避）。

- companion/workspace_manager.py
  - 実行前のパス正規化・サンドボックス境界チェックを共通化（workspace-write前提）。

- codecrafter/ui/rich_ui.py
  - PREVIEW と RESULT を明確化。`FILE_OPERATION` 表示は RESULT のみ。

- companion/enhanced_dual_loop.py
  - タスク完了条件に「実行結果検証済み」を追加。質問のみで完了しないよう制御。

---

## 5. 実装手順（小さなPR単位）
1) `FileOpOutcome` の導入と `file_ops` リファクタ（リード/ライト/作成）。
2) ハッシュユーティリティと検証ロジック追加、冪等化対応。
3) `apply_with_approval` の実装（差分生成・承認・実行・検証・イベント）。
4) UI連動の調整（PREVIEW/RESULTの分離）。
5) DualLoopの完了条件強化（結果検証必須）。
6) 既存呼び出し箇所を順次置換し、回帰確認。

---

## 6. テスト計画
- ユニット: `file_ops`
  - 新規作成: 非存在→作成→存在/ハッシュ一致。
  - 同一内容再書込: `changed=False`。
  - 上書き: 変更前/後ハッシュ差異を検出。
  - 例外時ロールバック: 失敗→元内容復元。
- 統合: `apply_with_approval`
  - PREVIEW→承認→RESULT イベント順の検証。
  - キャンセル時は無副作用。
- E2E: design-doc.md 生成フロー
  - 要求→PREVIEW→承認→RESULT（存在/内容検証ログ）。

---

## 7. リスクと対策
- 既存呼び出しの結果型移行で型不整合 → 段階的ラッパ提供。
- UIの先行表示依存箇所 → deprecate期間を設け、移行ガイド提示。

---

## 8. 運用・移行
- 既存の `FILE_OPERATION` 表示は PREVIEW に統一し、RESULT表示は新イベントのみ許可。
- 影響大箇所はフィーチャーフラグ（`FILE_OPS_V2=1`）で段階適用。

---

## 9. 付録：擬似コード
```python
def create_file_safely(path: Path, content: str) -> FileOpOutcome:
    norm = normalize(path)
    if norm.exists():
        before = sha256(norm.read_bytes())
        if norm.read_text() == content:
            return Outcome(ok=True, op="write", path=str(norm), reason="no_change", before_hash=before, after_hash=before, changed=False)
    preview = diff(current=norm.read_text() if norm.exists() else "", next=content)
    approved = approval.ask(preview)
    if not approved:
        return Outcome(False, "create", str(norm), "user_declined", None, None, False)
    backup = backup_if_exists(norm)
    write(norm, content)
    after = sha256(norm.read_bytes())
    ok = verify(norm.exists() and content_hash(content)==after)
    if not ok:
        restore(backup)
        return Outcome(False, "create", str(norm), "post_condition_failed", None, None, False)
    return Outcome(True, "create", str(norm), None, backup.hash if backup else None, after, changed=True)
```

