# Duckflow v4: メインエージェント実装計画 (Part 1)

## 概要
本計画は、Duckflow v4の核となる「統一ツールコールモデル」と「階層的プランニング」を備えた、堅牢な実行基盤を構築するためのロードマップです。
まずは「脳（思考）」と「手足（実行）」をつなぎ、論理的にコードを書ける状態を目指します。

## アーキテクチャ方針
- **Unified Tool Call:** LLMは常に `ActionList` (JSON) を出力し、システムはそれを順次実行する。
- **No LangGraph:** 複雑なグラフ構造を廃止し、シンプルな `While` ループとディスパッチャを採用。
- **階層的状態管理:** `Plan` (長期) -> `Step` (中期) -> `Task` (短期) の構造を `AgentState` で一元管理。

---

## Step 1: 脳と神経の接続 (Brain & Niggers) ✅
**目標:** ユーザー入力に対し、LLMが JSON で行動計画を返し、システムがそれを認識して応答できる。

- [x] **State定義 (`companion/state/agent_state.py`)**
    - Pydanticによる `AgentState`, `Action`, `Vitals` モデルの実装。
- [x] **LLMクライアント (`companion/base/llm_client.py`)**
    - JSONモードを強制するシンプルなOpenAIラッパーの実装。
- [x] **システムプロンプト (`companion/prompts/system.py`)**
    - v3の哲学とv7のJSONスキーマを統合した基本プロンプト。
- [x] **コアロジック (`companion/core.py`)**
    - メインループの実装。
    - `response` (返答) と `exit` (終了) アクションのディスパッチ処理。
- [x] **エントリーポイント (`main.py`)**
    - CLI起動スクリプト。

## Step 2: 手足の獲得 (Basic Tools) ✅
**目標:** エージェントがファイルシステムを安全に読み書きできる。

- [x] **ファイル操作ツール (`companion/tools/file_ops.py`)**
    - `read_file`, `write_file`, `list_files`, `mkdir` の実装。
    - 既存の `SimpleFileOps` をベースに簡素化して移植。
- [x] **安全装置 (The Duck Keeper)**
    - 指定ワークスペース外へのアクセス禁止ロジック。
- [x] **ディスパッチャ拡張 (`companion/core.py`)**
    - ファイル操作系アクションの処理ロジック追加。

## Step 3: 思考の階層化 (Hierarchical Planning) ✅
**目標:** 抽象的な指示から具体的な作業リストを生成できる。

- [x] **階層モデル拡張 (`companion/state/agent_state.py`)**
    - `Plan`, `Step`, `Task` クラスの詳細化。
- [x] **参謀ツール (`companion/tools/plan_tool.py`)**
    - `propose(goal)`: ゴールからステップ一覧を生成。
    - `update_step`: 進捗状態の更新。
- [x] **現場監督ツール (`companion/tools/task_tool.py`)**
    - `generate_list(step)`: ステップから具体的タスクリストを生成。
- [x] **コンテキスト切り替えロジック**
    - `plan_tool` 使用時と `task_tool` 使用時で、プロンプトに含める情報を動的に切り替える機能。

## Step 4: 非同期実行と報告 (Execution Worker) ✅
**目標:** 複数のタスクを一括実行し、結果をまとめて報告できる。

- [x] **実行ワーカー (`companion/execution/task_loop.py`)**
    - `List[Task]` を受け取り、順次実行するサブシステム。
    - LLMを使わず、Pythonコードとして高速に実行。
- [x] **結果サマライザー**
    - 実行ログをLLMに渡し、自然言語の完了報告を生成させる機能。
- [x] **統合テスト**
    - 「計画 → タスク分解 → 実行 → 報告」の一連の流れが通ることを確認。

---

## Phase 1.6: Pacemaker & Safety (実装完了) ✅
**目標:** エージェントの暴走を防ぎ、安全な自律実行を実現する。

- [x] **Pacemakerモジュール (`companion/modules/pacemaker.py`)**
    - ループ回数の動的計算（タスク数とVitalsに基づく）
    - バイタル（Confidence, Safety, Memory, Focus）の更新と監視
    - 異常検知（ループ枯渇、バイタル枯渇、エラー連鎖、停滞）
    - 介入アクションの生成（duck_callによるユーザー相談）
- [x] **Investigationモード**
    - 仮説検証ループの実装
    - Stuck Protocol（仮説失敗時の介入）

---

## Phase 2: Long-term Memory (計画中)
**目標:** 過去の対話や決定を記憶し、文脈を超えた継続性を提供する。

- [ ] **Memory Manager (`companion/memory/memory_manager.py`)**
    - セッションアーカイブの管理
    - 検索可能なインデックスの構築
- [ ] **Recallツール**
    - 過去のログからの情報検索
- [ ] **文脈圧縮**
    - 長い対話履歴の要約