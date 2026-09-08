# Proactive Continuation: 自律と協業のバランス設計

## 1. 背景と課題

### 現状の問題
Duckflowのコンセプトは「Companion with Agency（自律性を持つパートナー）」だが、
実際の振る舞いは「指示待ち」型になっている。

### 調査で判明した根本原因
ループ構造自体は自律性をサポートしている（`should_return_to_user()` は
`::response`/`::duck_call`/`::exit` のみで停止）。問題は**行動傾向**にある：

1. **過剰な報告**: エージェントが作業完了後に常に `::response` で制御をユーザーに返す
2. **自動継続メカニズムの欠如**: プランの次ステップへ自動で進む仕組みがない
3. **プロアクティブな提案の不足**: 「次これやりますか？」と自分から提案する促しが弱い

結論: **構造がダメなのではなく、LLMが「作業が終わったら報告する」という習性を
強く持っているため、自律的な連続実行が発動していない。**

---

## 2. 設計方針

### コンセプト: 「Briefing + Continue」パターン
> ステップ完了後、「次に何をやるか」を宣言してから、ユーザーの反応を待たずに進む。
> ただし、ユーザーはいつでも割り込める。

ペアプログラミングで「次はこれやるね」「うん、どうぞ」というやり取りの
**非同期版**を目指す。

### 設計原則
- **透明性**: 何が起きているかを常に見える状態にする
- **テンポ**: 毎回止まらないので、作業のリズムが落ちない
- **介入権**: ユーザーが能動的に割り込める（Ctrl+C / `::duck_call` / `::exit`）
- **安全弁**: 真の停滞検知とループ上限で暴走を防ぐ（定期チェックインはしない）

### 重要: 定期チェックインは導入しない
当初のL3「N歩ごとに強制停止」は**自律的ではない**。定期的に止まって報告するのは
「指示待ち」の変種に過ぎない。Proactive Continuationの理念は
「詰まるか完了するまで自律的に進む」こと。したがって安全弁は
**停滞検知（同じ操作の反復等）**と**ループ上限**の2層とする。

---

## 3. 2層進行モデル + 2層安全弁

| 層 | 役割 | タイミング | アクション | 停止? |
|---|---|---|---|---|
| L1 | 進捗の可視化 | 各アクション後 | `::note`（1行進捗） | ❌ |
| L2 | 宣言して進む | ステップ完了時 | `::note`（完了＋次の宣言） | ❌ |
| 安全弁1 | 停滞検知 | 進捗なし3回連続 | 強制 `::duck_call` | ✅ |
| 安全弁2 | 暴走防止 | `max_loops`到達 | 強制停止 | ✅ |

### L1: アクションレベル（進捗の可視化）
個別のアクション（read_file, edit_file等）完了後に、1行の進捗を `::note` で出す。

例:
```
::note @utils.py の構造を確認しました。次に関数の置き換えをします。
```

- ユーザー入力を待たない
- ループ継続
- 目的: 「何やってるか見えてる」状態を維持

### L2: ステップレベル（宣言して進む）
プランの1ステップが完了した時点で、完了内容と次のステップを宣言してから進む。

例:
```
::note @✅ ステップ1完了: APIクライアント実装。次はステップ2: DBスキーマ設計に進みます。
```

- ユーザー入力を待たない（宣言のみ）
- ループ継続
- 目的: 「次に何が始まるか」を予告し、ユーザーが割り込む猶予を与える

### 安全弁1: 停滞検知（進捗判定ベース）

現在の `no_progress_count` は**毎ループ無条件で+1**されているため、
Proactive Continuationの理念と衝突する。これを**実際の進捗判定**に改修する。

#### 進捗あり（カウンターをリセット）
- 新しいファイルを読んだ（前回と異なるパス）
- ファイルを編集した
- プランのStepが進んだ（`current_step_index`の変化）
- 前回と異なるアクションを実行した

#### 進捗なし（カウンター+1）
- 同じアクション + 同じパラメータの繰り返し
- アクションが空
- `::note` のみで実質的な操作がない

#### 閾値
3回連続で進捗なし → 強制 `::duck_call` で停止。

「同じ操作を3回繰り返す = 詰まっている」は妥当な判定。
精度の高い進捗判定が前提だが、上記基準で十分実用的。

### 安全弁2: ループ上限（`max_loops`）

Proactive Continuation ON時は作業が長くなるため、`max_loops` を別途設定する。

| 状態 | デフォルト `max_loops` |
|---|---|
| Proactive OFF | 10（現状通り） |
| Proactive ON | 50 |

`max_loops`到達時は強制停止し、ユーザーに状況を報告する。

---

## 4. ON/OFF切り替え

### コマンド

```
/proactive              — 現在の状態を表示
/proactive on           — 有効化
/proactive off          — 無効化
```

- 既存の `AgentMode`（Planning/Investigation/Task）とは独立して動作
- モード別の挙動差はなし（すべてのモードで同じ自律度）
- OFF→ON切り替え時は即座にプロンプトへ反映

### 設定（`duckflow.yaml`）

```yaml
agent:
  proactive_continuation:
    enabled: false        # デフォルトはOFF
    max_loops: 50         # proactive ON時のループ上限
```

- `enabled`: 起動時の初期状態
- `max_loops`: proactive ON時に `agent.max_loops` の代わりに使用

### 状態（`AgentState`）

```python
proactive_continuation_enabled: bool = False
steps_since_last_checkin: int = 0  # 予備（現仕様では未使用、将来の拡張用）
```

---

## 5. 実装箇所

| ファイル | 変更内容 |
|---|---|
| `companion/state/agent_state.py` | `proactive_continuation_enabled` フラグ追加（✅済）、`to_prompt_context` に状態表示追加（✅済） |
| `duckflow.yaml` | `agent.proactive_continuation` 設定セクション追加（✅済） |
| `companion/modules/command_handler.py` | `/proactive` コマンド追加 |
| `companion/prompts/templates.py` | proactive continuation 用プロンプトブロック追加 |
| `companion/prompts/builder.py` | ON時にプロンプトへ動的注入 |
| `companion/core.py` | `no_progress_count` の進捗判定改修、proactive ON時の `max_loops` 切り替え |
| `companion/core_loop_helpers.py` | 進捗判定ロジックの抽出（`has_progress` 関数等） |

---

## 6. Proactive Continuation プロンプト（注入内容）

ON時に `PromptBuilder` が動的コンテキストへ以下を追加する:

```
## Proactive Continuation Mode (ACTIVE)

あなたは自律的に継続実行しています。以下のルールに従ってください:

1. ステップ完了時は `::note` で完了内容と次のステップを宣言し、そのまま継続する
2. `::response` は**全タスク完了時**または**ユーザーに確認が必要な分岐**のみで使用する
3. すべてのアクション後に1行の `::note` で進捗を可視化する
4. 詰まった場合は `::duck_call` でユーザーに相談する
5. ユーザーはいつでも割り込める（Ctrl+C）
```