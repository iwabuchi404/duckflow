# テスト運用ルール: Main 3 / Full 7 と変更トリガー再実行

**ステータス:** 確定（2026-09-16）。モデルIDはカタログ検証済み。
**目的:** 「モデルのテスト」と「テスト機構自体のテスト」を分け、コストと識別力を両立する。

## 1. モデル tier

### Main 3（普段使い: 安さ＋対照群としての識別力）

| 役割 | モデル | 価格/M in・out | 選ぶ理由 |
|---|---|---|---|
| native-positive | `deepseek/deepseek-v4-flash-0731` | $0.06・$0.12 | 504runで native 60/63。安い既知の基準点 |
| symops-positive | `z-ai/glm-4.5-air` | $0.13・$0.85 | symops 58/63 vs native 52/63。この差の検出が妥当性確認になる |
| weak control | `liquid/lfm-2.5-2.6b:free` | 無料 | 下限対照。※提案の `lfm-2.5-1.2b-instruct:free` はカタログ不在のため修正（64K context）。**ただし native のみ有効**（下記注意） |

> ⚠️ **weak control の方式別適否（2026-09-16 Quickで判明）**: LFMはsymopsで全滅（2/21・全件1ループ`no_edit`）するが、弱さではなく方式非対応が原因。独自形式 `<|tool_call_start|>[...]<|tool_call_end|>` を出力しSym-Ops解釈不能。nativeは9/21で下限対照として機能。よってLFMのsymops結果は対照に使わない。候補対応: protocol probeゲート（N回不発でincompatible扱い）／当該マーカーのAutoRepair変換。

### Full 7（Main 3＋外部検証4）

| モデル | Fullで見るもの |
|---|---|
| （上記3） | Main |
| `minimax/minimax-m2.5`（$0.27・$1.08） | 中間型 |
| `google/gemini-2.5-flash`（$0.30・$2.50） | proprietary / naturalだがtask失敗型 |
| `qwen/qwen3.8-27b` | ローカル現実ターゲット。※提案の `qwen3.5` 表記はID修正 |
| `z-ai/glm-5.3-flash`（$0.09・$0.30） | 新世代低コスト。4.5-Airより安いが Main には入れない（4.5-Airの「Sym-Ops寄り」既知差を基準に残す） |

Full 7は毎回の比較対象にしない。Main 3で開発→固まった段階だけ回す外部検証セット（過学習防止）。

## 2. 変更トリガー表（何を変えたら何を再実行するか）

Calibration 4ターン（Build/Modify/Ambiguity/Serialize＋任意Recovery）は**設計中・未実装**。
現行の21シナリオeval・単体テストへの読み替えを併記する。

| 変更 | Calibration（設計） | 現行での対応 |
|---|---|---|
| model/provider変更 | 該当ターンを再実行 | 21シナリオ Main 3 Quick（各1回）→差があれば Regression |
| system prompt変更 | Build・Ambiguity | 21シナリオ Main 3 Quick＋単体全件 |
| context処理・compaction変更 | Build | MemoryManager系テスト＋協業系シナリオ Quick |
| history構築・state-card形式変更 | Modify | Modify相当（edit系）シナリオ Quick |
| 協業方針・Uncertainty Gate変更 | Ambiguity | ambiguous系8種 Quick |
| tool schema・codec・prompt format変更 | Serialize・Protocol A/B | Protocol A/B（Main 3×両方式×1回） |
| tool executor・approval UI・edit実装のみ | 再テスト不要 | 単体全件のみ |
| Pacemaker・error文面・failure処理変更 | Recovery | エラー系タグの出るシナリオ Quick |
| Calibrationスコア計算のみの変更 | 下位のみ | 21シナリオ再実行不要 |
| protocol自動選択まで届く変更 | 21シナリオevalで検証 | Full条件で検証 |

## 3. fingerprint キャッシュ（Calibration実装時に導入）

```yaml
calibration_tests:
  build:
    depends_on: [model, provider, system_prompt, context_strategy, compaction]
  ambiguity:
    depends_on: [model, provider, system_prompt, collaboration_policy]
  serialize:
    depends_on: [model, provider, action_codec, tool_schema]
```

同一 fingerprint なら保存済み profile を再利用し、再実行しない。

## 4. provider 変更時の昇格手順

1. まず `Serialize / tool round-trip` のみ再実行（差が出やすいのは tool calling・schema・sampling・long payload）
2. 正常 → Build/Modify/Ambiguity は旧 profile 継承
3. 異常 → Full Calibration へ昇格

## 5. 新規 model＋provider は初回のみ全ターン、その後は同一 fingerprint でスキップ

## 6. 実行レベル

| Level | 対象 | Runs | 用途 |
|---|---|---|---|
| Quick | Main 3 | 1 seed | 普段の実装変更 |
| Regression | Main 3 | 3 seeds | PR merge前・重要なprompt/protocol変更 |
| Full | 7 models | 3 seeds程度 | Calibration設計変更時・release baseline |
| Agent Eval | 21シナリオ | 別枠 | protocol自動選択まで届く変更時のみ |

上へ進む構造とし、全部毎回やらない。
