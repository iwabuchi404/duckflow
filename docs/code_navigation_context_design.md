# コード探索とコンテキスト戦略: 「検索させない」設計

**ステータス:** 設計合意済み・未実装
**作成日:** 2026-06-13
**関連:** `docs/edit_format_search_replace_design.md`（シンボル単位の編集と対をなす）、`docs/vitals_redesign_design.md`（テレメトリ思想の系列）

---

## 1. 背景と現状認識

### 1.1 エコシステムの現状（2026-06 調査より）

- **埋め込みRAGは脱落**: チャンク分割がコードの意味単位を壊す、埋め込みは「話題の類似」を捉えても「構造的関連」（呼び出し関係・定義と使用）を捉えない、編集のたびにインデックスが陳腐化する（[参考](https://yage.ai/share/why-coding-agents-still-use-grep-en-20260327.html)、[Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)）
- **エージェント的grepがベースライン**: 正確・反復可能・検証可能・インデックス維持ゼロ。主要エージェント（Claude Code, Codex CLI 等）が採用
- **構造ナビゲーションが未決の最前線**: 「呼び出し元を全部」「同名シンボルの定義特定」等はgrepの原理的弱点。グラフベース位置特定（LocAgent, RepoGraph）、LSP統合（Serena等）、aiderのrepo map（tree-sitter＋PageRankの圧縮シンボルマップ注入）が第三の道として存在（※私的知識、検証セット外）

### 1.2 重要な洞察: grepの勝利は訓練分布の均衡でもある

grepは「モデルが学習データで最も見てきた検索インターフェース」であり、その勝利には編集フォーマットと同じ力学（最も学習された形式が勝つ）が働いている。よってツール設計の判断基準も編集フォーマットと同じ:

> **「モデルはこのインターフェースを既に知っているか」**。新しいクエリDSLの発明は弱いモデルには逆効果。

### 1.3 Duckflow固有の前提: エージェント的grepは弱いモデルに不利

エージェント的grepの隠れた前提は「モデルが反復的な検索戦略（広く検索→絞る→読む）を立てられること」であり、これは高い計画能力を要求する。**弱いモデルはまさにここが下手**。よって主流の結論をそのまま輸入せず:

> 弱いモデルに「上手に探させる」のではなく、**システム側が先回りしてコンテキストを組み立てる**。

これはDuckflowの当初ビジョン第1の柱（「関連性の高い情報を最小限の形で賢く組み立てる」）そのものであり、`AgentState.to_prompt_context()`（状態カード）の配管は既に存在する。

---

## 2. 設計原則

1. **クエリの形は標準に寄せる**: grep/ripgrepの慣習（正規表現、大文字小文字オプション、glob絞り込み）。独自の語彙・構文を増やさない
2. **独自性は「結果の整形」と「先回り注入」に置く**: ツールの入口は平凡に、出口とコンテキスト設計で差別化する
3. **ツール総数は増やさない**: モード別ツール公開（アクション空間の縮小）の思想を維持。追加は最小限、結果側を豊かに
4. **シンボル単位で操作系を揃える**: ナビゲーション単位＝シンボル（関数/クラス）、編集単位＝関数。弱いモデルから行番号もバイト一致も取り除く
5. **Python特化で始める**: 標準ライブラリ `ast` のみで実装（LSPサーバー・tree-sitter依存なし）。多言語化は将来の拡張点

---

## 3. コンポーネント設計

### 3.1 既存検索ツールの標準化（grep_files / find_files）

- パラメータ語彙・挙動を ripgrep 慣習に整合（`pattern`（正規表現）、`-i` 相当、glob絞り込み）
- 独自の省略形・特殊構文があれば廃止

### 3.2 検索結果の整形強化

- ヒットを `path:line` 形式で返す（read_file / 編集ツールとの受け渡しを統一）
- 各ヒットに**所属シンボルのヘッダ**（`def foo(...)` / `class Bar`）を付与 → モデルが「どの関数の中か」を追加の read なしで把握できる
- ファイル単位のグループ化、ヒット数上限と「切り捨てた件数」の明示（沈黙の切り捨て禁止）

### 3.3 シンボル層ツール（標準ライブラリ ast のみ）

新規 `companion/tools/symbols.py`:

- `list_symbols(path)`: ファイル → 関数/クラスの一覧（名前・シグネチャ・行範囲・docstring冒頭）
- `find_definition(name, scope=".")`: シンボル名 → 定義位置の特定（ast走査＋grep補助）。同名複数時は候補列挙
- 公開はこの2つまで（原則3）。「呼び出し元検索」は grep＋結果整形（3.2）で代替し、専用ツール化しない

### 3.4 Repo Map の先回り注入（本設計の本命）

aider方式の翻案。ツールではなく**コンテキストの一部**として提供する（モデルの探索判断を不要にする）:

- **生成**: ast でリポジトリ全体のシンボル（クラス/関数シグネチャ）を抽出
- **ランク付け**: 初期版は単純なヒューリスティック（被参照回数のgrepカウント＋ファイルサイズ＋更新の新しさ）。PageRankは将来拡張
- **予算**: 1〜2kトークン上限に圧縮（弱いモデルの〜25k実効コンテキスト予算と整合）。超過時は上位シンボルのみ
- **注入位置**: PromptBuilder の動的コンテキスト（状態カード）。タスク開始時に生成し、ファイル変更アクションの後に該当ファイル分を更新
- **キャッシュ**: モジュール単位でmtimeベースの差分更新（全走査の繰り返しを避ける）

### 3.5 シンボル単位編集との接続（replace_function）

§2-4 の操作系を完成させる編集側の対応物。`docs/edit_format_search_replace_design.md` のフォールバック階段の最下段に位置づける:

- `replace_function @path name=foo` ＋ 新しい関数本体（content block）
- モデルに要求するのは「関数名」と「本体全文」のみ。**マッチング自体が消滅**する
- 書き込み前に `ast.parse` で構文検証（壊れた関数本体は適用前に拒否）
- 根拠: 7B級では行ベースdiffが壊滅（14%）する一方、関数ブロック丸ごと書き換えはファイル全体書き換えと同等（57%）（[arxiv 2604.27296](https://arxiv.org/html/2604.27296)、※未検証）

### 3.6 RAGロードマップの正式な廃止

- 旧計画の `search_code (RAG)` は追わない（§1.1 の潮流）
- 付随する整理: `pyproject.toml` の未使用レガシー依存 **chromadb / faiss-cpu / sentence-transformers の削除**（既知の課題§8-5 の一部解消）

---

## 4. 実装計画（フェーズ分割）

### Phase A: 検索ツールの標準化と結果整形
| # | 変更箇所 | 内容 |
|---|---|---|
| A1 | `companion/tools/file_ops.py` | grep_files / find_files のパラメータ・挙動を rg 慣習に整合 |
| A2 | 同上 | 結果整形: `path:line`、所属シンボルヘッダ付与、グループ化、切り捨ての明示 |

### Phase B: シンボル層
| # | 変更箇所 | 内容 |
|---|---|---|
| B1 | 新規 `companion/tools/symbols.py` | `list_symbols` / `find_definition`（ast実装） |
| B2 | `companion/core.py` | ツール登録＋ MODE_TOOL_MAPPING への追加（planning / investigation / task） |

### Phase C: Repo Map 注入
| # | 変更箇所 | 内容 |
|---|---|---|
| C1 | 新規 `companion/modules/repo_map.py` | 生成・ランク付け・トークン予算圧縮・mtimeキャッシュ |
| C2 | `companion/prompts/builder.py` | 状態カードへの注入（動的コンテキスト層） |
| C3 | `companion/core.py` | ファイル変更アクション後の差分更新フック |

### Phase D: replace_function（編集側の対応物）
| # | 変更箇所 | 内容 |
|---|---|---|
| D1 | `companion/tools/file_ops.py` または `symbols.py` | `replace_function` 実装（ast構文検証付き） |
| D2 | `companion/prompts/few_shot.py` | 使用例の追加（edit_file 失敗 → replace_function のリカバリ例） |

### テスト（各フェーズに付随）
- 結果整形のスナップショットテスト（シンボルヘッダ付与・切り捨て表示）
- ast シンボル抽出の単体テスト（ネスト関数・デコレータ・async対応）
- repo map の予算遵守（1〜2kトークン上限）とキャッシュ無効化のテスト
- replace_function の構文検証（壊れた本体の拒否）・同名関数の曖昧性エラーのテスト

### スコープ外
- LSP / tree-sitter 統合（多言語化するときの拡張点として温存）
- 埋め込みRAG（正式に廃止）
- PageRank等の高度なランク付け（ヒューリスティックで開始し、ベンチで必要性を判断）

---

## 5. 検証基準

1. **探索回数の削減**: 同一タスクセットで「最初の正しい read_file に到達するまでの検索アクション数」が repo map 注入で減ること（弱いモデルでA/B）
2. **トークン収支**: repo map の注入コスト（1〜2k）が、削減された探索往復のコストを下回ること
3. **シンボルヘッダの正確性**: grep結果の所属シンボル付与が誤らないこと（境界ケース: モジュールレベルコード、ネスト）
4. **replace_function**: 共通インデント領域の編集タスクで edit_file（マーカー形式）との成功率比較 — フォールバック階段の閾値設計の根拠にする

---

## 6. 参考

- なぜコーディングエージェントはgrepを使い続けるのか — https://yage.ai/share/why-coding-agents-still-use-grep-en-20260327.html
- Anthropic, "Effective context engineering for AI agents" — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- aider repo map（tree-sitter＋ランク付きシンボルマップ）— https://aider.chat/docs/repomap.html （※私的知識）
- 関数単位書き換えの優位（7B級）— https://arxiv.org/html/2604.27296 （※未検証）
- LocAgent / RepoGraph / Serena（構造ナビゲーションの先行事例、※私的知識）
