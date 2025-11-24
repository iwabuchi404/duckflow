# Duckflow v4: 実装計画 Part 2 - 自律調整と記憶管理

## 概要

Part 1（Step 1-5）では、基本的な自律実行ループと階層的プランニング、Human-in-the-loopシステムを実現しました。  
Part 2では、このシステムを**持続可能かつ安全に運用**するための以下の機能を実装します：

1. **Pacemaker（自律調整システム）**: 無限ループやスタックを防ぎ、適切なタイミングで介入する
2. **Memory Management（記憶管理）**: コンテキストウィンドウの制約を超えた長期的な文脈保持

## 現在の実装状況

### ✅ 実装済み（Part 1完了）

- **Unified Tool Call**: LLMが`ActionList` (JSON)を出力し、システムが順次実行
- **階層的プランニング**: `Plan` → `Step` → `Task`の構造
- **自律実行ループ**: `response`/`exit`/`duck_call`が出るまで思考・実行を繰り返す
- **File Operations**: 安全なファイル操作ツール（Duck Keeper）
- **Approval System**: 危険な操作に対するユーザー承認フロー
- **Rich UI**: 統一されたターミナルUI

### 🔄 部分実装

- **D.U.C.K. Vitals**: `Vitals`クラスは存在するが、活用されていない
  - `mood`, `focus`, `stamina`のフィールドが定義済み
  - `update_vitals()`, `decay()`, `recover()`メソッドが実装済み
  - しかし、**バイタルに基づく介入ロジックが未実装**

- **Duck Call**: `duck_call`アクションは存在するが、**自動発動ロジックが未実装**
  - 現在はLLMが明示的に`duck_call`を選択する場合のみ動作
  - Pacemakerによる強制的な介入機能が必要

### ❌ 未実装

- **Pacemaker**: 
  - 無限ループ防止機能なし（現状ループ回数制限なし）
  - スタック検知なし
  - バイタルに基づく自動介入なし
  
- **Memory Management**:
  - 会話履歴が無限に増大する
  - コンテキストウィンドウ超過への対策なし
  - 古い情報の要約・削除機能なし

---

## Step 6: The Pacemaker（自律調整システム）

### 目標

エージェントの「バイタル」と「実行状況」を監視し、以下の異常を検知して介入する：

1. **Loop Exhaustion（ループ枯渇）**: 最大ループ回数に到達
2. **Vital Depletion（バイタル枯渇）**: Stamina/Focusが危険水準に低下
3. **Error Cascade（エラー連鎖）**: 同じエラーが連続発生
4. **Stagnation（停滞）**: 同じアクションを同じ引数で繰り返し実行

### 設計方針

- **No LangGraph**: メインループ（`core.py`）内で毎サイクル呼び出される`check()`メソッドとして実装
- **動的ループ制限**: タスクの難易度とバイタルに応じて最大ループ回数を動的決定
- **積極的介入**: 異常検知時は強制的に`duck_call`を発動

### 実装コンポーネント

#### 6.1 `DuckPacemaker`クラス（`companion/modules/pacemaker.py`）

```python
class DuckPacemaker:
    """エージェントの健康状態と実行状況を監視し、介入を行う"""
    
    def __init__(self, state: AgentState, ui: DuckUI):
        self.state = state
        self.ui = ui
        self.loop_count = 0
        self.max_loops = 10  # デフォルト値
        self.action_history: List[Action] = []
        self.error_count = 0
        self.consecutive_errors = 0
        
    def calculate_max_loops(self) -> int:
        """タスクの種類とバイタルに応じて最大ループ回数を計算"""
        # ベース値の決定
        if self.state.current_plan:
            base_loops = 15  # 計画実行中
        else:
            base_loops = 8   # 通常会話
        
        # バイタル係数の計算
        vitals = self.state.vitals
        vitals_score = (
            vitals.mood * 0.4 +
            vitals.focus * 0.4 +
            vitals.stamina * 0.2
        )
        
        if vitals_score < 0.4:
            vitals_factor = 0.7  # 不調
        elif vitals_score > 0.8:
            vitals_factor = 1.2  # 好調
        else:
            vitals_factor = 1.0  # 通常
        
        # 最終計算（3-20の範囲で制限）
        calculated = int(base_loops * vitals_factor)
        return max(3, min(calculated, 20))
    
    def update_vitals(self, action: Action, result: Any, is_error: bool):
        """アクション実行結果に基づいてバイタルを更新"""
        if is_error:
            # エラー時はStaminaとFocusが低下
            self.state.vitals.stamina = max(0.0, self.state.vitals.stamina - 0.1)
            self.state.vitals.focus = max(0.0, self.state.vitals.focus - 0.05)
            self.error_count += 1
            self.consecutive_errors += 1
        else:
            # 成功時は緩やかに回復
            self.state.vitals.stamina = min(1.0, self.state.vitals.stamina + 0.02)
            self.consecutive_errors = 0
        
        # 通常のdecay（毎ループわずかに消耗）
        self.state.vitals.decay(0.03)
    
    def check_health(self) -> Optional[InterventionReason]:
        """健康状態を診断し、介入が必要ならその理由を返す"""
        vitals = self.state.vitals
        
        # 1. Stamina枯渇（最優先）
        if vitals.stamina < 0.1:
            return InterventionReason(
                type="STAMINA_DEPLETED",
                message="体力が限界です。これ以上の作業は危険です。",
                severity="critical"
            )
        
        # 2. ループ回数超過
        if self.loop_count >= self.max_loops:
            return InterventionReason(
                type="LOOP_EXHAUSTED",
                message=f"最大試行回数（{self.max_loops}回）に到達しました。",
                severity="high"
            )
        
        # 3. Focus低下（停滞）
        if vitals.focus < 0.3:
            return InterventionReason(
                type="FOCUS_LOST",
                message="思考が停滞しています。別のアプローチが必要かもしれません。",
                severity="medium"
            )
        
        # 4. 連続エラー
        if self.consecutive_errors >= 3:
            return InterventionReason(
                type="ERROR_CASCADE",
                message="同じエラーが繰り返し発生しています。",
                severity="high"
            )
        
        # 5. スタック検知（同じアクションの繰り返し）
        if self._detect_stagnation():
            return InterventionReason(
                type="STAGNATION",
                message="同じ操作を繰り返しており、進捗がありません。",
                severity="medium"
            )
        
        # 6. Mood低下（自信喪失）
        if vitals.mood < 0.6:
            return InterventionReason(
                type="CONFIDENCE_LOW",
                message="現在の計画に自信が持てていません。",
                severity="low"
            )
        
        return None
    
    def _detect_stagnation(self) -> bool:
        """直近3回のアクションが同一パターンかチェック"""
        if len(self.action_history) < 3:
            return False
        
        recent = self.action_history[-3:]
        # 名前が全て同じで、パラメータも類似している場合
        if len(set(a.name for a in recent)) == 1:
            # 簡易的な類似度チェック
            return True
        return False
    
    def intervene(self, reason: InterventionReason) -> Action:
        """介入アクションを生成"""
        self.ui.print_warning(f"🦆 Pacemaker介入: {reason.message}")
        
        # Duck Callアクションを強制的に生成
        return Action(
            name="duck_call",
            parameters={
                "reason": reason.type,
                "message": reason.message,
                "severity": reason.severity,
                "vitals": {
                    "mood": self.state.vitals.mood,
                    "focus": self.state.vitals.focus,
                    "stamina": self.state.vitals.stamina
                }
            },
            thought=f"Pacemakerの介入により、ユーザーに相談します（理由: {reason.type}）"
        )
```

#### 6.2 `InterventionReason`データモデル（`companion/state/agent_state.py`）

```python
class InterventionReason(BaseModel):
    """Pacemakerの介入理由"""
    type: Literal[
        "STAMINA_DEPLETED",
        "LOOP_EXHAUSTED", 
        "FOCUS_LOST",
        "ERROR_CASCADE",
        "STAGNATION",
        "CONFIDENCE_LOW"
    ]
    message: str
    severity: Literal["critical", "high", "medium", "low"]
```

#### 6.3 `core.py`への統合

```python
class DuckAgent:
    def __init__(self, ...):
        # ...
        self.pacemaker = DuckPacemaker(self.state, self.ui)
    
    async def run(self):
        # セッション開始時にmax_loopsを計算
        self.pacemaker.max_loops = self.pacemaker.calculate_max_loops()
        self.ui.print_system(
            f"最大試行回数: {self.pacemaker.max_loops}回 "
            f"(Vitals - M:{self.state.vitals.mood:.2f}, "
            f"F:{self.state.vitals.focus:.2f}, S:{self.state.vitals.stamina:.2f})"
        )
        
        while True:
            user_input = self.ui.get_input()
            self.state.add_message("user", user_input)
            
            # 自律ループ
            while True:
                self.pacemaker.loop_count += 1
                
                # Pacemakerチェック（アクション実行前）
                intervention = self.pacemaker.check_health()
                if intervention:
                    # 強制介入
                    action_list = ActionList(
                        actions=[self.pacemaker.intervene(intervention)],
                        reasoning=f"Pacemaker intervention: {intervention.type}"
                    )
                else:
                    # 通常のLLM呼び出し
                    action_list = await self.think_and_decide()
                
                # アクション実行
                if action_list.actions:
                    for action in action_list.actions:
                        result, is_error = await self.execute_action(action)
                        
                        # Pacemakerにフィードバック
                        self.pacemaker.update_vitals(action, result, is_error)
                        self.pacemaker.action_history.append(action)
                        
                        # 終了条件チェック
                        if action.name in ["response", "exit", "duck_call"]:
                            self.pacemaker.loop_count = 0  # リセット
                            break
```

---

## Step 7: Memory Management（記憶管理システム）

### 目標

長時間のセッションでもコンテキストウィンドウを溢れさせず、重要な文脈を維持する。

### 設計方針

- **FIFO + Summary**: 単純な切り捨てではなく、古い会話を要約して保持
- **Selective Retention**: ユーザー指示や成功したツール結果など、重要な情報は保持
- **Token Budget**: 会話履歴のトークン数を常時監視

### 実装コンポーネント

#### 7.1 `MemoryManager`クラス（`companion/modules/memory.py`）

```python
class MemoryManager:
        kept_indices = set()
        budget = self.max_tokens * 0.7  # 70%使用を目標
        
        for score, idx, msg in scored_messages:
            msg_tokens = self._estimate_tokens([msg])
            if budget - msg_tokens > 0:
                kept_messages.append((idx, msg))
                kept_indices.add(idx)
                budget -= msg_tokens
        
        # インデックス順に並び替え
        kept_messages.sort(key=lambda x: x[0])
        
        # 要約の挿入
        result = []
        gap_start = None
        
        for idx, msg in kept_messages:
            # ギャップの検出
            if gap_start is None:
                gap_start = idx
            elif idx - result[-1][0] > 1:
                # ギャップがある場合、要約を挿入
                gap_messages = conversation_history[result[-1][0]+1:idx]
                if gap_messages:
                    summary = await self._summarize_messages(gap_messages)
                    result.append((-1, {
                        "role": "assistant",
                        "content": f"[前回の会話の要約: {summary}]"
                    }))
            
            result.append((idx, msg))
        
        return min(score, 1.0)
    
    async def _summarize_messages(self, messages: List[Dict[str, str]]) -> str:
        """メッセージ群を要約"""
        combined = "\n\n".join([
            f"{msg['role']}: {msg['content']}" for msg in messages
        ])
        
        prompt = f"""以下の会話を簡潔に要約してください（1-2文）：

{combined}

要約："""
        
        try:
            response = await self.llm.chat(
                [{"role": "user", "content": prompt}],
                response_model=None
            )
            return response.get("content", "（要約失敗）")
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return f"（{len(messages)}件のメッセージ）"
```

#### 7.2 `AgentState`への統合

```python
class AgentState(BaseModel):
    # ...
    
    async def add_message_with_pruning(
        self, 
        role: str, 
        content: str, 
        memory_manager: Optional[MemoryManager] = None
    ):
        """メッセージを追加し、必要なら履歴を整理"""
        self.add_message(role, content)
        
        if memory_manager:
            self.conversation_history = await memory_manager.prune_history(
                self.conversation_history
            )
```

---

## 実装優先順位

### Phase 1: Pacemaker Basic（高優先度）

- [ ] `DuckPacemaker`クラスの実装
- [ ] `InterventionReason`モデルの追加
- [ ] ループ回数制限の実装
- [ ] バイタル更新ロジックの実装
- [ ] `core.py`への統合

### Phase 2: Pacemaker Advanced（中優先度）

- [ ] スタック検知ロジックの実装
- [ ] エラー連鎖検知の実装
- [ ] 動的ループ計算の高度化
- [ ] UIへのバイタル表示追加

### Phase 3: Memory Management（中優先度）

- [ ] `MemoryManager`クラスの実装
- [ ] トークン数推定機能
- [ ] 重要度スコアリング
- [ ] 自動要約機能
- [ ] `AgentState`への統合

### Phase 4: Testing & Refinement（通常優先度）

- [ ] 各種異常シナリオでのテスト
- [ ] バイタル係数の調整
- [ ] ループ制限値の最適化
- [ ] メモリ整理戦略の改善

---

## 設計上の注意点

### Pacemakerについて

1. **過度な介入を避ける**: 介入の閾値は慎重に設定し、エージェントの自律性を損なわない
2. **透明性**: 介入理由を明確に表示し、ユーザーが状況を理解できるようにする
3. **段階的な警告**: いきなり強制停止ではなく、軽度の警告から始める（将来実装）

### Memory Managementについて

1. **無損失を目指さない**: 完全な文脈保持は不可能。重要な情報の優先保持に注力
2. **要約の質**: LLM要約はコストがかかるため、シンプルな文字列結合も検討
3. **ユーザー制御**: 自動整理の頻度や方法をユーザーが調整できるようにする（将来実装）

---

## 参考ドキュメント

- `docs/old/duck_pacemaker_dynamic_design_simple.md`: 動的ループ制限の詳細設計
- `docs/old/D.U.C.K._vitals_system.md`: バイタルシステムの哲学と実装
- `docs/old/duck_call.md`: Duck Callの仕様
- `docs/old/golden_fish_memory_protocol.md`: 記憶管理の階層構造
- `docs/feature_selection_rationale.md`: 機能選択の基準

---

## 成功基準

### Step 6 (Pacemaker)完了の定義

- [ ] 無限ループが発生しない（max_loops制限が動作）
- [ ] バイタル枯渇時に自動介入する
- [ ] 3回連続エラー時に介入する
- [ ] 同じアクション繰り返し時に介入する
- [ ] 介入時のUIフィードバックが適切

### Step 7 (Memory)完了の定義

- [ ] 会話履歴が8000トークンを超えない
- [ ] 重要な情報（ユーザー指示等）が保持される
- [ ] 古い情報が適切に要約される
- [ ] 長時間セッションでもパフォーマンス低下なし
