# 複数ターン・複雑タスク失敗の根本原因分析と改善計画

## 作成日: 2026-03-09
## ステータス: PROPOSED

---

## 1. 問題概要

### 現象
- 簡単なタスク（1-2ターン、単一ツール）は正常に実行できる
- 複数ターンが絡むタスク、または少し複雑なタスクが実行できない
- 長期実行や高度に複雑なタスクは仕方ないが、「最低芸レベル」に足りない

### 影響範囲
- ユーザー体験の著しい低下
- エージェントとしての実用性の限界
- 複雑なリファクタリングやデバッグ作業の不可能

---

## 2. 根本原因分析

### 2.1 主原因: 推論・アクション履歴の欠落（致命的）

**場所**: `companion/core.py` L482-L514, L801

**現状のフロー**:
```
1. LLM呼び出し → action_list = await self.llm.chat(messages, response_model=ActionList)
2. reasoning表示 → ui.print_thinking(action_list.reasoning)  ← UIに表示するだけ
3. アクション実行 → await self.execute_actions(action_list)
4. ツール結果記録 → self.state.add_message("user", formatted_res)  ← 結果のみ保存
```

**問題点**:
- `action_list.reasoning`（LLMの思考プロセス）が会話履歴に保存されない
- `action_list.actions`（何を決定したか）が会話履歴に保存されない
- 次ターンのLLMは、自分が前ターンで何を考えたかを参照できない

**影響の連鎖**:

| ターン | LLMが見えるもの | LLMが見えないもの |
|--------|----------------|-------------------|
| Turn 1 | ユーザー入力 + ツール結果 | 自分の推論・決定内容 |
| Turn 2 | Turn 1のツール結果 + 新入力 | Turn 1でなぜそのアクションを選んだか |
| Turn 3 | 結果の羅列のみ | 全体的な意図・方針の連続性 |

→ LLMは「結果は見えるが文脈がない」状態になり、複雑なタスクで一貫性を失う

### 2.2 副次原因A: ツール結果ロールの混同

**場所**: `companion/core.py` L801

```python
self.state.add_message("user", formatted_res)  # ← ツール結果を"user"ロールで追加
```

**問題点**:
- ツール実行結果が `"user"` ロールで会話履歴に追加される
- LLMにとって「ユーザーが言ったこと」と「ツールが出した結果」が区別できない
- ユーザーの意図とツールの事実が混ざり、判断が歪む

### 2.3 副次原因B: action_note の履歴未追加

**場所**: `companion/core.py` L909-L923

```python
async def action_note_(self, message: str = "") -> str:
    ui.print_info(message)       # ← UIに表示するだけ
    logger.info(f"Note: {message}")
    return f"Notified: {message}"  # ← 履歴に追加されない
```

**問題点**:
- `::note` で通知した進捗状況がLLMに伝わらない
- LLMが自分の進捗メモを次ターンで参照できない
- 進捗の連続性が途切れる

### 2.4 副次原因C: エラーフィードバックの不十分さ

**場所**: `companion/core.py` L858-L869

**現状**:
- 連続2回エラーで残りアクションを中断する
- 中断メッセージは汎用的（「原因を確認してから再試行してください」）
- どのアクションが、なぜ失敗したかの構造化フィードバックがない

**問題点**:
- LLMがエラーから学習し、戦略を変更する機会がない
- 同じエラーを繰り返す可能性が高い

### 2.5 副次原因D: パーサー間の不整合（一部修正済み）

**場所**: `companion/utils/sym_ops.py` L377, L656, L679, L688

**現状**:
- `AutoRepair` の一部で `line.rstrip() == '>>>'` が残存
- `FuzzyParser` は `line == '>>>'` を使用
- ブロック終端判定の不整合により、アクションがサイレントに無視される可能性

---

## 3. 改善計画

### Phase 1: 推論・アクション履歴の追加（最重要・最高効果）

**対象**: `companion/core.py` `execute_actions` メソッド

**変更内容**:
- `execute_actions` の最後（`return results` の直前）に、
  LLMの `reasoning` + 実行したアクション概要を `"assistant"` ロールで
  会話履歴に追加する
- 新規メソッド `_build_action_summary(action_list)` を実装

**期待効果**:
- LLMが次ターンで自分の前回の推論と行動を参照可能になる
- 複数ターンタスクの一貫性が保たれる
- 「最低芸レベル」の底上げ

**実装イメージ**:
```python
# execute_actions の最後、return results の直前
action_summary = self._build_action_summary(action_list)
self.state.add_message("assistant", action_summary)
```

```python
def _build_action_summary(self, action_list: ActionList) -> str:
    """LLMの推論とアクション概要を会話履歴用にフォーマットする。"""
    lines = []
    if action_list.reasoning:
        lines.append(f">> {action_list.reasoning}")
    for action in action_list.actions:
        target = action.parameters.get("path", action.parameters.get("command", ""))
        lines.append(f":: {action.name} @{target}" if target else f":: {action.name}")
    return "\n".join(lines)
```

### Phase 2: ツール結果ロールの分離

**対象**: `companion/core.py` L801, L850, L692

**変更内容**:
- ツール結果を `"user"` ロールではなく `"system"` ロールで記録する
- ※ `"tool"` ロールはOpenAI APIの仕様上 `tool_call_id` が必要なため、
  現状の構造化呼び出し（response_model）とは互換性がない
- `"system"` ロールで「ツール結果である」ことを明示するプレフィックスを付与

**期待効果**:
- LLMが「ユーザーの指示」と「ツールの実行結果」を正しく区別
- 判断の精度向上

### Phase 3: action_note の履歴追加

**対象**: `companion/core.py` `action_note_` メソッド L909-L923

**変更内容**:
- `::note` のメッセージを会話履歴に追加する
- ロールは `"assistant"` とする（LLM自身の進捗メモのため）

**期待効果**:
- LLMが進捗状況を次ターンでも参照可能
- 進捗の連続性の維持

### Phase 4: エラーフィードバックの強化

**対象**: `companion/core.py` L858-L869

**変更内容**:
- 連続エラー中断時に、構造化エラーメッセージを履歴に追加
- 「どのアクションが、なぜ失敗したか、どう修正すべきか」を含める
- `last_syntax_errors` に蓄積されたエラー情報を活用

**期待効果**:
- LLMがエラーから学習し、戦略を変更可能に
- 同じエラーの繰り返しを防止

### Phase 5: パーサー不整合の完全解消

**対象**: `companion/utils/sym_ops.py` L377, L656, L679, L688

**変更内容**:
- 残存する4箇所の `line.rstrip() == '>>>'` を `line == '>>>'` に修正
- `AutoRepair` と `FuzzyParser` の判定ロジックを完全統一

**期待効果**:
- アクションのサイレント無視を防止
- パーサーの信頼性向上

---

## 4. 優先順位と実行順序

| 優先度 | Phase | 効果 | 工数 | リスク |
|--------|-------|------|------|--------|
| 🔴 最高 | Phase 1 | 複数ターン成功率の大幅向上 | 中 | 低 |
| 🟡 高 | Phase 2 | 判断精度の向上 | 小 | 低 |
| 🟡 高 | Phase 3 | 進捗の連続性維持 | 極小 | 極低 |
| 🟢 中 | Phase 4 | エラー回復力の向上 | 小 | 低 |
| 🟢 中 | Phase 5 | パーサー信頼性の向上 | 極小 | 極低 |

**推奨**: Phase 1 → Phase 5 → Phase 2 → Phase 3 → Phase 4 の順で実装

---

## 5. 検証方法

### ユニットテスト
- `_build_action_summary` の出力フォーマット検証
- 会話履歴に `"assistant"` ロールで推論が追加されることの確認
- ツール結果が `"system"` ロールで追加されることの確認

### 統合テスト（手動）
- 3ターン以上のタスクでLLMが前回の推論を参照できているか確認
- 複数ファイル編集タスクで一貫性が保たれるか確認
- エラー発生後にLLMが戦略を変更できるか確認

### 回帰テスト
- 既存の単純タスクが引き続き正常に動作することを確認
- セッション復元時に推論履歴が正しく保持されることを確認

---

## 6. 注意事項

- Phase 1の実装により会話履歴のトークン消費が増加する
  → MemoryManager の pruning タイミングと連携を確認する必要あり
- Phase 2でロールを変更すると、プロンプトキャッシュのヒット率に影響する可能性
  → キャッシュ境界の再確認が必要
- 既存のセッションログ（`logs/sessions/`）との互換性は維持する
  → 新ロールは既存の `add_message` インターフェースで対応可能

---

## 7. 関連ファイル

- `companion/core.py` — メインループ、execute_actions、action_note_
- `companion/state/agent_state.py` — AgentState、add_message
- `companion/prompts/builder.py` — PromptBuilder
- `companion/utils/sym_ops.py` — AutoRepair、FuzzyParser
- `companion/modules/memory.py` — MemoryManager（pruning連携）
- `companion/tools/results.py` — ToolResult、wrap_tool_result