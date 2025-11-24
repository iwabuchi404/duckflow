## **Duckflow v3a 実装プラン**

### 1. 背景と目的

**現状の課題**:
先の調査で、現行システムはv3設計の核心部分が未実装であることが判明しました。具体的には、以下の重大な設計上の問題が残存しています。

1.  **中央制御の欠如**: 安全な状態遷移を保証するはずの`StateMachine`が全く利用されていません。
2.  **分散した状態管理**: `ChatLoop`と`TaskLoop`が、異なるスレッドから無秩序に共有の`AgentState`を書き換えており、競合状態（Race Condition）の温床となっています。
3.  **脆弱な非同期通信**: ループ間の通信がタイミングに依存する`Queue`に頼っているため、「結果が表示されない」という致命的な不具合が頻発します。

**v3aプランの目的**:
この「v3aプラン」は、v3の再設計ではなく、**v3が本来目指した堅牢なアーキテクチャを正しく完成させる**ための具体的な実装計画です。上記の問題を根本的に解決し、システムの安定性、予測可能性、保守性を確立することを目的とします。

### 2. v3aアーキテクチャの概要

v3aが目指すアーキテクチャは、`EnhancedDualLoopSystem`が絶対的な中央司令塔として機能するモデルです。

```mermaid
graph TD
    subgraph EnhancedDualLoopSystem (中央司令塔)
        SM(StateMachine) -- 1. 状態遷移を管理 --> U(update_state)
        U -- 2. コールバック起動 --> SYNC
        SYNC[3. _sync_state_to_agent_state] -- 4. AgentStateを更新 --> AS(AgentState)
    end

    subgraph Threads
        CL(ChatLoop) -- ユーザー入力/コマンド --> U
        TL(TaskLoop) -- タスク完了/エラー --> U
    end
    
    CL -- 6. 状態を読み取りUI表示 --> AS
    TL -- 5. 処理に必要な状態を参照 --> AS

    style SM fill:#bbf,stroke:#333,stroke-width:2px
    style AS fill:#bfb,stroke:#333,stroke-width:2px
```

*   **状態遷移の一元化**: 全ての状態変更は、`EnhancedDualLoopSystem`の`update_state`メソッドを経由し、`StateMachine`によって許可されたものだけが実行されます。
*   **コールバックによる同期**: `StateMachine`の変更は、即座にコールバックを介して中央の`AgentState`に同期されます。
*   **リアクティブなUI**: `ChatLoop`は`AgentState`を監視し、その変更に基づいてUIを更新します。これにより、キューのタイミング問題は発生しません。

### 3. 段階的実装計画

リスクを最小化し、着実に改善を進めるため、以下の3フェーズで実装を進めます。

---

#### **Phase 1: 状態管理の中央集権化**

**目的**: 最も危険な「分散した状態管理」を解決し、システムの振る舞いを予測可能にする。

| 項目 | 内容 |
| :--- | :--- |
| **修正対象ファイル** | `enhanced_dual_loop.py`, `chat_loop.py`, `task_loop.py` |
| **具体的な修正内容** | 1. **`EnhancedDualLoopSystem`の責務強化**: <br>   - `__init__`で`StateMachine`をインスタンス化する。<br>   - `state_machine.add_state_change_callback(self._sync_state_to_agent_state)` を呼び出し、コールバックを登録する。<br>   - `_sync_state_to_agent_state`メソッドを実装し、`StateMachine`の最新状態を`self.agent_state`に書き込むロジックを記述する。<br>   - 外部（ループ）から状態遷移を要求するための`update_state(new_step, new_status)`メソッドを新規作成する。このメソッド内で`state_machine.set_state()`を呼び出す。<br>2. **ループからの直接更新を禁止**: <br>   - `ChatLoop`と`TaskLoop`内にある全ての`self.enhanced_companion.state.step = ...` および `...status = ...` というコードを削除する。<br>   - 削除した箇所を、親システムのメソッド呼び出し `self.parent_system.update_state(...)` に置き換える。（`__init__`で`parent_system`を受け取るように修正） |
| **完了条件** | - `agent_state`の`step`と`status`が、常に`StateMachine`の状態と同期していることがログで確認できる。<br>- `ChatLoop`と`TaskLoop`から、`agent_state`を直接書き換えるコードが完全に除去されている。<br>- 許可されていない状態遷移を試みた際に、`StateMachine`がそれをブロックし、警告ログが出力される。 |

---

#### **Phase 2: キュー通信からの脱却とリアクティブUI**

**目的**: 「結果が表示されない」不具合を恒久的に解決し、UIが常に最新の状態を反映するようにする。

| 項目 | 内容 |
| :--- | :--- |
| **修正対象ファイル** | `enhanced_core.py`, `agent_state.py`, `chat_loop.py`, `task_loop.py` |
| **具体的な修正内容** | 1. **`AgentState`の拡張**: <br>   - `agent_state.py`に、タスクの最終結果を保持するためのフィールド（例: `last_task_result: Optional[Dict] = None`）を追加する。<br>2. **`TaskLoop`の出力先変更**: <br>   - タスク完了時、`status_queue`に結果を`put`する代わりに、`self.enhanced_companion.state.last_task_result = {'message': result, 'timestamp': ...}` のように`AgentState`に結果を書き込む。<br>3. **`ChatLoop`の表示ロジック変更**: <br>   - `_check_status_queue`メソッドを修正または削除する。<br>   - メインループ内で`agent_state = self.enhanced_companion.get_agent_state()`を常に監視する。<br>   - `if agent_state.last_task_result:` のような条件で新しい結果を検知し、UIに表示する。<br>   - 表示後は、`agent_state.last_task_result = None` のように結果をクリアし、再表示を防ぐ。 |
| **完了条件** | - ファイル読み込みなどのタスクを実行した際、処理結果が100%の確率でUIに表示される。<br>- `status_queue`を介した最終結果の受け渡しが完全になくなる。<br>- UIの更新が、`AgentState`の変更に追従する形になっている。 |

---

#### **Phase 3: 責務のクリーンアップとリファクタリング**

**目的**: コードの可読性と保守性を向上させ、v3aアーキテクチャを盤石なものにする。

| 項目 | 内容 |
| :--- | :--- |
| **修正対象ファイル** | `enhanced_core.py`, `chat_loop.py`, `task_loop.py` |
| **具体的な修正内容** | 1. **ループの単純化**: <br>   - `ChatLoop`と`TaskLoop`から、状態遷移以外の複雑なロジックを可能な限り`EnhancedCompanionCore`や`EnhancedDualLoopSystem`に移譲する。<br>   - ループはそれぞれ「UI処理」「タスク実行」という単一の責務に特化させる。<br>2. **`EnhancedCompanionCore`の責務見直し**: <br>   - `EnhancedCompanionCore`が意図せず状態遷移ロジックを持っている場合、それを`EnhancedDualLoopSystem`に移す。<br>3. **コード品質の向上**: <br>   - キューで使われていた `'task_completed'` のような文字列リテラルを、Enumに置き換えるなど、型安全性を高める。 |
| **完了条件** | - 各クラスの責務がより明確になり、コードの見通しが改善される。<br>- 将来の機能追加やデバッグが容易な構造になる。 |

### 4. 期待される効果

このv3aプランを完遂することにより、以下の効果が期待されます。

*   **安定性の飛躍的向上**: 競合状態やタイミングの問題がなくなり、システムは安定して動作します。
*   **バグの解消**: 「結果が表示されない」という根本的な不具合が解消されます。
*   **保守性の向上**: 状態管理が一元化され、責務が明確になることで、コードの理解や修正が格段に容易になります。
*   **v3設計の完成**: システムが、本来あるべき堅牢でスケーラブルなアーキテクチャへと進化します。