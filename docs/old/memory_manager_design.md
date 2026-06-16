# Memory Manager 詳細設計書

## 1. 概要

### 1.1 目的

Memory Managerは、Duckflow v4の長期セッション運用を可能にするために、会話履歴（コンテキスト）を効率的に管理するシステムです。

### 1.2 解決すべき問題

1. **コンテキストウィンドウの制約**
   - LLMには入力トークン数の上限がある（例: GPT-4は8K, 128K等）
   - 長時間セッションでは会話履歴が無限に増大する
   - トークン超過でAPIエラー、またはコスト増大

2. **重要な情報の喪失**
   - 単純なFIFO（古い順削除）では重要な文脈が失われる
   - ユーザーの指示、成功したツール結果、エラー情報などを保持する必要

3. **パフォーマンス低下**
   - 大量の履歴をLLMに毎回送るとレイテンシーが増加
   - トークン数推定やスコアリング自体がオーバーヘッドになりうる

### 1.3 制約条件

- **トークン予算**: デフォルト8,000トークン（adjustable）
- **リアルタイム性**: 整理処理は数秒以内に完了すべき
- **要約コスト**: LLM要約は追加APIコールが必要
- **無損失不可能**: すべての情報を保持することは不可能。重要度に基づく選択が必要

---

## 2. 設計方針

### 2.1 FIFO + Selective Retention + Summary

1. **基本はFIFO**: 古いメッセージから削除候補とする
2. **重要度スコアリング**: 各メッセージの重要度を計算し、重要なメッセージは保持
3. **要約挿入**: 削除されるメッセージ群を要約して履歴に挿入
4. **動的調整**: トークン使用率が閾値（例: 80%）を超えたら整理を開始

### 2.2 段階的な整理戦略

| トークン使用率 | アクション |
|---------------|-----------|
| 0-60% | 何もしない |
| 60-80% | 警告ログのみ |
| 80-90% | 低重要度メッセージの削除開始 |
| 90-100% | 積極的な削除 + 要約生成 |
| 100%+ | 緊急削除（要約なし） |

### 2.3 重要度の定義

以下の要素を総合してスコアリング（0.0-1.0）：

1. **Recency（新しさ）**: 最近のメッセージほど重要 (Weight: 30%)
2. **Role（発言者）**: ユーザー発言は重要 (Weight: 30%)
3. **Content Type（内容種別）**: (Weight: 40%)
   - ユーザー指示・質問: 高
   - ツール実行結果（成功）: 高
   - エラーメッセージ: 中～高
   - システムメッセージ: 低～中
   - 要約メッセージ: 中
   - 通常の会話: 低

---

## 3. アーキテクチャ

### 3.1 コンポーネント構成

```
┌──────────────────────────────────────┐
│         DuckAgent (core.py)          │
│  ┌────────────────────────────────┐  │
│  │      AgentState                │  │
│  │  - conversation_history        │  │
│  │  - add_message()               │  │
│  │  - add_message_with_pruning()  │  │
│  └────────┬───────────────────────┘  │
│           │                           │
│           ▼                           │
│  ┌────────────────────────────────┐  │
│  │    MemoryManager               │  │
│  │  - prune_history()             │  │
│  │  - _score_messages()           │  │
│  │  - _estimate_tokens()          │  │
│  │  - _summarize_gap()            │  │
│  └────────┬───────────────────────┘  │
│           │                           │
│           ▼                           │
│  ┌────────────────────────────────┐  │
│  │    LLMClient                   │  │
│  │  (要約生成に使用)               │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

### 3.2 データフロー

```
1. User Input
   ↓
2. AgentState.add_message("user", content)
   ↓
3. MemoryManager.check_if_pruning_needed()
   ↓
4. [If needed] MemoryManager.prune_history()
   ├─ Score all messages
   ├─ Select high-importance messages
   ├─ Detect gaps in timeline
   └─ Summarize gaps
   ↓
5. Updated conversation_history
   ↓
6. LLM API Call (with pruned history)
```

### 3.3 統合ポイント

1. **AgentState.add_message()**
   - 現在: メッセージを単純に追加
   - 修正後: `memory_manager` が渡されていれば、追加後に整理チェック

2. **DuckAgent.__init__()**
   - `MemoryManager` インスタンスを作成
   - `AgentState` に渡す

3. **system prompt 生成時**
   - 整理後の履歴を使用

---

## 4. 重要度スコアリングアルゴリズム

### 4.1 スコア計算式

```python
total_score = (
    recency_score * 0.3 +
    role_score * 0.3 +
    content_score * 0.4
)
```

### 4.2 Recency Score（新しさ）

```python
recency_score = message_index / total_message_count
```

- 最新のメッセージ: 1.0
- 最古のメッセージ: 0.0
- 線形補間

### 4.3 Role Score（発言者）

```python
if role == "user":
    role_score = 1.0
elif role == "assistant":
    role_score = 0.5
elif role == "system":
    role_score = 0.3
```

### 4.4 Content Score（内容）

```python
content_score = 0.0

# キーワードベース
if any(kw in content.lower() for kw in ["error", "failed", "exception"]):
    content_score += 0.3

if any(kw in content.lower() for kw in ["success", "completed", "done"]):
    content_score += 0.2

if "[Tool:" in content:  # ツール実行結果
    content_score += 0.25

if "[SYSTEM:" in content or "[User" in content:  # 重要なシステムメッセージ
    content_score += 0.2

if "duck_call" in content or "approval" in content:
    content_score += 0.3

# 長さベース（極端に短いメッセージは重要度低い）
if len(content) < 20:
    content_score *= 0.7

content_score = min(content_score, 1.0)
```

### 4.5 調整可能なパラメータ

```python
class ScoringConfig:
    recency_weight: float = 0.3
    role_weight: float = 0.3
    content_weight: float = 0.4
    
    important_keywords: List[str] = [
        "error", "success", "plan", "task", "duck_call", 
        "approval", "denied", "completed", "failed"
    ]
    
    min_content_length_penalty_threshold: int = 20
    short_content_penalty: float = 0.7
```

---

## 5. 整理戦略

### 5.1 トリガー条件

```python
def should_prune(self, conversation_history: List[Dict]) -> bool:
    current_tokens = self._estimate_tokens(conversation_history)
    usage_ratio = current_tokens / self.max_tokens
    
    if usage_ratio > 0.8:  # 80%超えたら整理
        return True
    
    return False
```

### 5.2 整理アルゴリズム

```
Input: conversation_history (List[Dict])
Output: pruned_history (List[Dict])

1. 全メッセージのスコアリング
   scores = [(score, index, message) for each message]

2. スコア順にソート（降順）
   sorted_scores = sort(scores, reverse=True)

3. トークン予算内で高スコアメッセージを選択
   target_tokens = max_tokens * 0.7  # 70%使用を目標
   selected = []
   for (score, idx, msg) in sorted_scores:
       if budget - token_of(msg) > 0:
           selected.append((idx, msg))
           budget -= token_of(msg)

4. インデックス順に並び替え
   selected = sort(selected by index)

5. ギャップ検出と要約挿入
   result = []
   last_idx = -1
   for (idx, msg) in selected:
       if idx - last_idx > 1:  # ギャップあり
           gap_messages = history[last_idx+1 : idx]
           if len(gap_messages) > 0:
               summary = _summarize_gap(gap_messages)
               result.append(summary)
       result.append(msg)
       last_idx = idx
   
6. Return result
```

### 5.3 要約 vs 削除の判断

| 条件 | アクション |
|------|----------|
| 連続削除メッセージ数 >= 5 | 要約生成 |
| 連続削除メッセージ数 < 5 | 単純削除 |
        }
```

---

## 6. 実装詳細

### 6.1 クラス設計

```python
from typing import List, Dict, Optional, Tuple
from pydantic import BaseModel, Field
import logging
from companion.base.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ScoringConfig(BaseModel):
    """重要度スコアリングの設定"""
    recency_weight: float = 0.3
    role_weight: float = 0.3
    content_weight: float = 0.4
    
    important_keywords: List[str] = [
        "error", "success", "plan", "task", "duck_call",
        "approval", "denied", "completed", "failed", "warning"
    ]
    
    min_content_length: int = 20
    short_content_penalty: float = 0.7


class MemoryManager:
    """
    会話履歴のコンテキスト管理を担当
    
    主な機能:
    - トークン数の監視
    - 重要度に基づくメッセージの選択
    - 低優先度メッセージの削除
    - 削除されたメッセージの要約
    """
    
    def __init__(
        self,
        llm_client: LLMClient,
        max_tokens: int = 8000,
        config: Optional[ScoringConfig] = None
    ):
        self.llm = llm_client
        self.max_tokens = max_tokens
        self.config = config or ScoringConfig()
        self.prune_count = 0  # 整理実行回数（統計用）
        
    def should_prune(self, conversation_history: List[Dict]) -> bool:
        """整理が必要かチェック"""
        current_tokens = self._estimate_tokens(conversation_history)
        usage_ratio = current_tokens / self.max_tokens
        
        if usage_ratio > 0.8:
            logger.info(
                f"Memory pruning needed: {current_tokens}/{self.max_tokens} "
                f"tokens ({usage_ratio:.1%})"
            )
            return True
        
        return False
    
    async def prune_history(
        self,
        conversation_history: List[Dict]
    ) -> Tuple[List[Dict], Dict]:
        """
        会話履歴を整理
        
        Returns:
            (pruned_history, stats)
        """
        self.prune_count += 1
        
        original_count = len(conversation_history)
        original_tokens = self._estimate_tokens(conversation_history)
        
        # トークン使用率チェック
        if not self.should_prune(conversation_history):
            return conversation_history, {
                "pruned": False,
                "original_count": original_count,
                "original_tokens": original_tokens
            }
        
        # 緊急モード（100%超え）
        emergency_mode = original_tokens > self.max_tokens
        
        # スコアリング
        scored_messages = self._score_messages(conversation_history)
        
        # スコア順にソート
        scored_messages.sort(reverse=True, key=lambda x: x[0])
        
        # トークン予算内で選択
        target_tokens = self.max_tokens * 0.7  # 70%使用を目標
        selected_messages = self._select_within_budget(
            scored_messages, 
            target_tokens
        )
        
        # インデックス順に並び替え
        selected_messages.sort(key=lambda x: x[0])
        
        # ギャップ検出と要約挿入
        if emergency_mode:
            # 緊急モードでは要約をスキップ
            result_history = [msg for _, msg in selected_messages]
        else:
            result_history = await self._insert_summaries(
                conversation_history,
                selected_messages
            )
        
        final_count = len(result_history)
        final_tokens = self._estimate_tokens(result_history)
        
        stats = {
            "pruned": True,
            "original_count": original_count,
            "original_tokens": original_tokens,
            "final_count": final_count,
            "final_tokens": final_tokens,
            "removed_count": original_count - final_count,
            "removed_tokens": original_tokens - final_tokens,
            "emergency_mode": emergency_mode
        }
        
        logger.info(
            f"Memory pruned: {original_count} → {final_count} messages, "
            f"{original_tokens} → {final_tokens} tokens"
        )
        
        return result_history, stats
    
    def _score_messages(
        self,
        conversation_history: List[Dict]
    ) -> List[Tuple[float, int, Dict]]:
        """全メッセージのスコアリング"""
        scored = []
        total = len(conversation_history)
        
        for idx, msg in enumerate(conversation_history):
            score = self._calculate_importance(msg, idx, total)
            scored.append((score, idx, msg))
        
        return scored
    
    def _calculate_importance(
        self,
        message: Dict,
        index: int,
        total: int
    ) -> float:
        """メッセージの重要度を0-1でスコアリング"""
        content = message.get("content", "")
        role = message.get("role", "")
        
        # Recency score
        recency_score = index / max(total - 1, 1)
        
        # Role score
        role_scores = {
            "user": 1.0,
            "assistant": 0.5,
            "system": 0.3
        }
        role_score = role_scores.get(role, 0.5)
        
        # Content score
        content_score = 0.0
        content_lower = content.lower()
        
        # キーワードチェック
        if any(kw in content_lower for kw in self.config.important_keywords):
            content_score += 0.3
        
        # 特殊マーカー
        if "[Tool:" in content:
            content_score += 0.25
        if any(marker in content for marker in ["[SYSTEM:", "[User", "[TASK"]):
            content_score += 0.2
        if "duck_call" in content_lower or "approval" in content_lower:
            content_score += 0.3
        
        # 長さペナルティ
        if len(content) < self.config.min_content_length:
            content_score *= self.config.short_content_penalty
        
        content_score = min(content_score, 1.0)
        
        # 総合スコア
        total_score = (
            recency_score * self.config.recency_weight +
            role_score * self.config.role_weight +
            content_score * self.config.content_weight
        )
        
        return min(total_score, 1.0)
    
    def _select_within_budget(
        self,
        scored_messages: List[Tuple[float, int, Dict]],
        budget: int
    ) -> List[Tuple[int, Dict]]:
        """トークン予算内で高スコアメッセージを選択"""
        selected = []
        remaining_budget = budget
        
        for score, idx, msg in scored_messages:
            msg_tokens = self._estimate_tokens([msg])
            
            if remaining_budget - msg_tokens > 0:
                selected.append((idx, msg))
                remaining_budget -= msg_tokens
            
            if remaining_budget <= 0:
                break
        
        return selected
    
    async def _insert_summaries(
        self,
        original_history: List[Dict],
        selected_messages: List[Tuple[int, Dict]]
    ) -> List[Dict]:
        """ギャップを検出し、要約を挿入"""
        result = []
        last_idx = -1
        
        for idx, msg in selected_messages:
            # ギャップ検出
            if idx - last_idx > 1:
                gap_messages = original_history[last_idx + 1 : idx]
                
                if len(gap_messages) >= 5:
                    # 5件以上のギャップは要約
                    summary = await self._summarize_gap(gap_messages)
                    result.append(summary)
                elif len(gap_messages) > 0:
                    # 少数のギャップは削除通知のみ
                    result.append({
                        "role": "assistant",
                        "content": f"[{len(gap_messages)}件のメッセージが省略されました]"
                    })
            
            result.append(msg)
            last_idx = idx
        
        return result
    
    async def _summarize_gap(self, messages: List[Dict]) -> Dict:
        """メッセージ群を要約"""
        combined = "\n\n".join([
            f"{msg['role']}: {msg['content'][:200]}"
            for msg in messages
        ])
        
        prompt = f"""以下の会話の重要なポイントのみを簡潔に要約してください。
出力は必ず以下のJSON形式にしてください：
{{
    "summary": "要約テキスト（2-3文、100文字以内）"
}}

会話内容:
{combined}"""
        
        try:
            response = await self.llm.chat(
                [{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.3
            )
            
            summary_text = response.get("summary", "（要約失敗）")
            
            return {
                "role": "assistant",
                "content": f"[過去{len(messages)}件の会話の要約: {summary_text}]"
            }
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return {
                "role": "assistant",
                "content": f"[過去{len(messages)}件のメッセージが削除されました]"
            }
    
    def _estimate_tokens(self, messages: List[Dict]) -> int:
        """トークン数を概算"""
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        # 1文字 ≈ 0.5トークン（日本語・英語混在を考慮）
        return int(total_chars * 0.5)
```

### 6.2 AgentState への統合

```python
# in companion/state/agent_state.py

from typing import Optional
from companion.modules.memory import MemoryManager

class AgentState(BaseModel):
    # ... existing fields ...
    
    async def add_message_with_pruning(
        self,
        role: str,
        content: str,
        memory_manager: Optional[MemoryManager] = None
    ):
        """
        メッセージを追加し、必要なら履歴を整理
        
        Args:
            role: メッセージのロール ("user", "assistant", "system")
            content: メッセージ内容
            memory_manager: MemoryManagerインスタンス（Noneなら整理しない）
        """
        # 通常の追加
        self.add_message(role, content)
        
        # 整理チェック
        if memory_manager and memory_manager.should_prune(self.conversation_history):
            self.conversation_history, stats = await memory_manager.prune_history(
                self.conversation_history
            )
            
            # 統計ログ
            if stats.get("pruned"):
                logger.info(
                    f"Memory pruned: removed {stats['removed_count']} messages, "
                    f"saved {stats['removed_tokens']} tokens"
                )
```

### 6.3 DuckAgent への統合

```python
# in companion/core.py

from companion.modules.memory import MemoryManager

class DuckAgent:
    def __init__(self, llm_client: LLMClient = default_client):
        # ... existing initialization ...
        
        # Initialize Memory Manager
        self.memory_manager = MemoryManager(
            llm_client=self.llm,
            max_tokens=8000
        )
    
    async def run(self):
        while True:
            # ... get user input ...
            
            # Add message with auto-pruning
            await self.state.add_message_with_pruning(
                "user",
                user_input,
                memory_manager=self.memory_manager
            )
            
            # ... autonomous loop ...
```

---

## 7. パフォーマンス考慮

### 7.1 トークン推定の効率

- **O(n)の複雑度**: メッセージ数に線形
- **最適化**: キャッシュ不要（計算が軽量）

### 7.2 要約生成のコスト

- **LLM API コール**: 1回のpruneで最大数回
- **軽減策**:
  - 緊急モードでは要約スキップ
  - 連続5件以上のギャップのみ要約
  - max_tokens=150で制限

### 7.3 メモリ使用量

- **スコアリング**: O(n)の追加メモリ
- **選択**: O(n log n)（ソート）
- **影響**: 1000メッセージでも数MB程度

---

## 8. エラーハンドリング

### 8.1 要約失敗時

```python
try:
    summary = await self._summarize_gap(messages)
except Exception as e:
    logger.error(f"Summarization failed: {e}")
    # フォールバック: 削除通知のみ
    summary = {
        "role": "assistant",
        "content": f"[{len(messages)}件のメッセージが削除されました]"
    }
```

### 8.2 トークン超過時

```python
if current_tokens > self.max_tokens:
    # 緊急モード
    logger.warning("Emergency pruning: token limit exceeded")
    emergency_mode = True
    # 要約をスキップして即削除
```

---

## 9. テスト戦略

### 9.1 ユニットテスト

```python
def test_token_estimation():
    """トークン推定の精度テスト"""
    messages = [{"role": "user", "content": "Hello world"}]
    # ...

def test_importance_scoring():
    """重要度スコアリングのテスト"""
    # ユーザーメッセージが高スコア
    # エラーメッセージが中～高スコア
    # 通常メッセージが低スコア
    # ...

def test_message_selection():
    """メッセージ選択のテスト"""
    # トークン予算内に収まるか
    # 重要メッセージが保持されるか
    # ...
```

### 9.2 統合テスト

```python
async def test_full_pruning_cycle():
    """完全な整理サイクルのテスト"""
    # 1. 大量のメッセージを作成
    # 2. prune_history()を呼び出し
    # 3. トークン数が制限内か確認
    # 4. 重要メッセージが残っているか確認
    # ...
```

### 9.3 シナリオテスト

- 長時間セッションシミュレーション
- 様々なメッセージパターン
- エラー連鎖時の動作

---

## 10. 将来の拡張性

### 10.1 ユーザー設定

```python
class MemoryConfig(BaseModel):
    max_tokens: int = 8000
    pruning_threshold: float = 0.8  # 80%で整理開始
    target_usage: float = 0.7       # 70%を目標
    enable_summarization: bool = True
    min_gap_for_summary: int = 5
```

### 10.2 異なる整理戦略

- **Sliding Window**: 最新N件のみ保持
- **Session-based**: セッション境界で分割
- **Topic-based**: トピッククラスタリング

### 10.3 長期記憶への移行

```python
class LongTermMemory:
    """将来実装: ベクトルDBなどへの保存"""
    def store(self, messages: List[Dict]):
        # ...
    
    def retrieve(self, query: str, k: int = 5):
        # ...
```

---

## 11. 成功基準

### 11.1 機能要件

- [ ] 会話履歴が設定トークン数を超えない
- [ ] ユーザー発言が優先的に保持される
- [ ] ツール実行結果（成功・エラー）が保持される
- [ ] 削除されたメッセージが適切に要約される
- [ ] 緊急時（100%超過）でも動作する

### 11.2 非機能要件

- [ ] 整理処理が3秒以内に完了
- [ ] メモリ使用量が妥当（数MB以内）
- [ ] 要約生成失敗時も動作継続
- [ ] 長時間セッションでも性能劣化なし

### 11.3 品質要件

- [ ] ユニットテストカバレッジ80%以上
- [ ] 統合テスト実施
- [ ] ログが適切に出力される
- [ ] エラーハンドリングが適切

---

## 12. 実装スケジュール

### Phase 1: Core Implementation (Priority: High)
- [ ] `MemoryManager`クラスの基本実装
- [ ] トークン推定機能
- [ ] 重要度スコアリング
- [ ] メッセージ選択ロジック

### Phase 2: Summary Integration (Priority: Medium)
- [ ] 要約生成機能
- [ ] ギャップ検出と挿入
- [ ] エラーハンドリング

### Phase 3: State Integration (Priority: High)
- [ ] `AgentState.add_message_with_pruning()`
- [ ] `DuckAgent`への統合
- [ ] ログ出力

### Phase 4: Testing & Refinement (Priority: Medium)
- [ ] ユニットテスト作成
- [ ] 統合テスト作成
- [ ] パラメータチューニング
- [ ] ドキュメント更新

---

## 13. 参考文献

- `docs/old/golden_fish_memory_protocol.md`: 階層的記憶システムの概念
- `docs/implementation_plan_v4_part2.md`: 全体実装計画
- LangChain Memory: https://python.langchain.com/docs/modules/memory/
- OpenAI Token Counting: https://github.com/openai/openai-cookbook/

---

## 14. 付録: 設定例

```python
# デフォルト設定（バランス型）
config = MemoryConfig(
    max_tokens=8000,
    pruning_threshold=0.8,
    target_usage=0.7
)

# 保守的設定（頻繁に整理）
conservative_config = MemoryConfig(
    max_tokens=6000,
    pruning_threshold=0.6,
    target_usage=0.5
)

# 積極的設定（ギリギリまで保持）
aggressive_config = MemoryConfig(
    max_tokens=12000,
    pruning_threshold=0.9,
    target_usage=0.8
)
```
