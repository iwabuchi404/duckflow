# 改善されたDual-Loop処理フロー

## 現在の問題
- 意図理解が2回実行される（ChatLoop + CompanionCore）
- 判定結果の不整合リスク
- パフォーマンスの無駄

## 改善案1: 統一意図理解
```
ユーザー入力 → ChatLoop
├── CompanionCore.analyze_intent_only() (軽量版)
├── ActionType取得
├── if ActionType == DIRECT_RESPONSE:
│   └── ChatLoop内で直接処理
└── else:
    └── TaskLoopに送信（意図理解結果も含む）
```

## 改善案2: 遅延意図理解
```
ユーザー入力 → ChatLoop
├── 全てTaskLoopに送信
├── TaskLoop内で統一的に意図理解
└── 結果に応じて処理分岐
```

## 改善案3: 階層的意図理解
```
ユーザー入力 → ChatLoop
├── 軽量な事前判定（キーワードベース）
├── if 明らかに雑談:
│   └── ChatLoop内で処理
└── else:
    └── TaskLoopで詳細分析
```