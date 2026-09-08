# Reasoning Model Support Plan

## 背景

DuckflowのLLM応答処理パイプラインは、推論モデル（Qwen3, DeepSeek-R1, Kimi K2, GLM等）を
正しく扱えていない。推論OFFで運用していたが、モデルの能力が引き出せていない。
推論をONにしつつ、以下の問題を解決する。

## 現状の問題

| 問題 | 原因 |
|------|------|
| 推論でトークンを使い切る | `max_output_tokens` に推論トークンが含まれるため、推論が長いと本文が空になる |
| Thought-only fallback で停止 | 本文が空の時、推論の `>>` Thought を `::response` に変換して停止する |
| 推論内のアクションが無視 | `reasoning_to_thought` が `::` 行をスキップするが、本文に戻さない |
| 推論OFFで能力低下 | `reasoning.enabled: false` で推論を完全無効化すると、モデルの能力が引き出せない |
| モード切替ループ | 推論不足でLLMが状況判断できず `::investigate` を繰り返す |

## 推論モデルの2種類の応答形式

### Type A: API分離型（OpenRouter経由）
- 推論が `message.reasoning` / `message.reasoning_content` フィールドに分離
- 本文 (`message.content`) には推論が含まれない
- 対象: DeepSeek-R1, Qwen3 (OpenRouter経由), GLM, GPT-OSS

### Type B: 本文埋め込み型
- 推論が `<think>...</think>` タグで本文に混入
- 対象: DeepSeek-R1 (直接API), Kimi K2 (一部)

## 設計

### 1. トークン管理

- `reasoning.effort: low` で推論トークンを `max_output_tokens` の ~20% に制限
- `max_output_tokens: 16384` に維持（推論 + 本文の合計）
- 推論枯渇の検出: `finish_reason == "length"` かつ推論テキストが長い場合

### 2. 推論→Thought変換の改善

#### 現状
```
reasoning_to_thought(reasoning)
  → :: 行をスキップして >> 行に変換
  → 本文の先頭に <!--reasoning-start--> マーカーで付加
```

#### 改善
- **推論内の `::` アクション行を本文に追加**: `extract_reasoning_actions` の結果を本文末尾に付加
- **推論の `>>` Thought はコンテキストとして保持**: `ActionList.reasoning` に格納、UI表示用
- **Thought-only fallback から推論を除外**: 推論由来の Thought が `result.thoughts` に混入しないよう分離

### 3. 空本文時のリカバリ

推論はあるが本文が空の場合の処理フロー:

```
1. extract_reasoning_actions(reasoning) で :: 行を抽出
   → アクション行があれば本文として扱い、パーサーに渡す
2. アクション行がない場合:
   → finish_reason == "length" なら推論枯渇と判定
   → max_output_tokens を増やしてリトライ（推論はキャッシュされる可能性が高い）
3. リトライでも空の場合:
   → 推論の最後の数行から次のアクションを推測して続行
   → または「推論でトークンを使い切りました。続けてください」を返す
```

### 4. プロンプト調整

システムプロンプトに推論モデル向けの指示を追加:

```
<reasoning_guidance>
If you are a reasoning model:
- Keep reasoning concise. Aim for 3-5 key points, not exhaustive analysis.
- ALWAYS write your Sym-Ops actions in the response body, not in the reasoning field.
- The reasoning field is for thinking. The body is for action.
- If you find yourself writing :: actions in reasoning, move them to the body.
</reasoning_guidance>
```

### 5. パーサーのマーカー処理

`<!--reasoning-start-->` / `<!--reasoning-end-->` マーカー内:
- Thought として扱い、`ActionList.reasoning` に格納
- アクションパーサーに渡さない（本文とは別物）

## 実装順序

1. **推論トークン制限**: `reasoning.effort: low` を設定、`max_output_tokens: 16384` 维持
2. **空本文リカバリ**: `extract_reasoning_actions` でアクション抽出 → 本文に追加
3. **Thought-only fallback 修正**: 推論由来 Thought を fallback から完全除外
4. **プロンプト調整**: 推論モデル向けの簡潔な推論指示を追加

## 対象ファイル

| ファイル | 変更内容 |
|----------|----------|
| `companion/base/llm_client.py` | 推論抽出、空本文リカバリ、Thought-only fallback |
| `companion/utils/preprocessor.py` | `reasoning_to_thought`, `extract_reasoning_actions` |
| `companion/utils/sym_ops.py` | `process()` の推論処理パイプライン |
| `companion/prompts/templates.py` | 推論モデル向けプロンプト |
| `duckflow.yaml` | `reasoning.enabled: true`, `reasoning.effort: low` |

## テスト方針

- 推論あり・なしの両パターンでアクションが正しく実行されること
- 推論でトークンを使い切った場合のリカバリが動作すること
- 推論内の `::` アクションが本文に抽出されて実行されること
- Thought-only fallback が推論由来の Thought で発動しないこと
