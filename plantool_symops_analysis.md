# PlanTool Sym-Ops化 - 詳細分析と懸念点

## 現在の実装構造

### PlanTool.propose_plan()
```python
async def propose_plan(self, goal: str) -> str:
    # 1. LLMに独自プロンプトでJSON要求
    prompt = "Please break this goal down... Return a JSON object..."
    proposal = await self.llm.chat(messages, response_model=PlanProposal)
    
    # 2. JSONをパース
    for step_data in proposal.steps:
        new_plan.add_step(
            title=step_data.get("title"),
            description=step_data.get("description")
        )
    
    # 3. Planオブジェクト作成 & state保存
    self.state.current_plan = new_plan
```

### Plan & Step構造
```python
class Step(BaseModel):
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.NOT_STARTED

class Plan(BaseModel):
    goal: str
    steps: List[Step] = []
    current_step_index: int = 0
    is_complete: bool = False
```

---

## Sym-Ops化の影響分析

### ✅ 問題なし

1. **goal パラメータ取得**: すでに正常動作
2. **Plan.goal 設定**: テキストをそのまま保存可能
3. **state.current_plan 更新**: 問題なし

### ⚠️ 懸念点

#### 1. **Step構造の抽出**
**現在**: JSON構造化出力で明確
```json
{
  "steps": [
    {"title": "Setup", "description": "Install deps"},
    {"title": "Core", "description": "Write logic"}
  ]
}
```

**Sym-Ops化後**: Markdownからステップ抽出が必要
```markdown
## フェーズ1: コアシステム
1. **Engineクラスの実装**
   - シングルトンパターン
   - システム登録
```

**リスク**: 
- パース精度**60-70%** (見出しレベル、番号形式が多様)
- `title`と`description`の区別が曖昧

#### 2. **mark_step_complete()の依存**
```python
current_step = self.state.current_plan.get_current_step()
current_step.status = TaskStatus.COMPLETED
```

**要件**: 
- Stepオブジェクトが必須
- `title`, `description`, `status` 属性が必要

**リスク**: Markdownパースが不正確だとステップ管理が機能不全

#### 3. **TaskToolとの連携**
`task_tool.py`が`current_plan`と`current_step`に依存:
```python
# companion/tools/task_tool.py:39
Current Goal: {self.state.current_plan.goal}
Current Step: {current_step.title}
```

**要件**: Step構造が正確である必要

#### 4. **Pacemakerモジュールとの連携**
```python
# companion/modules/pacemaker.py:35-36
if self.state.current_plan:
    current_step = self.state.current_plan.get_current_step()
```

---

## 解決策の選択肢

### A. **完全Sym-Ops化 + 簡易パーサー** (推奨)

**実装**:
```python
async def propose_plan(self, goal: str) -> str:
    # goalにはMarkdown形式の完全なプランが含まれる
    new_plan = Plan(goal=goal)
    
    # 簡易的なMarkdownパース
    steps = self._parse_markdown_steps(goal)
    for step in steps:
        new_plan.add_step(title=step['title'], description=step.get('description', ''))
    
    self.state.current_plan = new_plan
    return f"Plan created with {len(steps)} steps."

def _parse_markdown_steps(self, markdown: str) -> List[Dict]:
    """Markdownから見出しベースでステップ抽出"""
    steps = []
    lines = markdown.split('\n')
    
    for line in lines:
        # ## または ### で始まる見出しを抽出
        if re.match(r'^#{2,3}\s+', line):
            title = re.sub(r'^#{2,3}\s+', '', line).strip()
            steps.append({'title': title, 'description': ''})
    
    return steps
```

**メリット**:
- ✅ Sym-Ops一本化
- ✅ Step構造維持（既存機能動作）
- ✅ 実装シンプル

**デメリット**:
- ⚠️ パース精度60-70% (複雑なMarkdown対応困難)
- ⚠️ description抽出が難しい

---

### B. **Sym-Ops + 構造化ヒント**

**System Prompt強化**:
```
When using ::propose_plan, format your plan as:
## Step 1: [Title]
[Description]

## Step 2: [Title]
[Description]
```

**パーサー改善**:
```python
def _parse_markdown_steps(self, markdown: str) -> List[Dict]:
    steps = []
    current_step = None
    
    for line in markdown.split('\n'):
        if line.startswith('## Step'):
            if current_step:
                steps.append(current_step)
            title = re.sub(r'^## Step \d+:\s*', '', line).strip()
            current_step = {'title': title, 'description': []}
        elif current_step and line.strip():
            current_step['description'].append(line)
    
    if current_step:
        steps.append(current_step)
    
    # description をjoin
    for step in steps:
        step['description'] = '\n'.join(step['description'])
    
    return steps
```

**メリット**:
- ✅ パース精度向上 80-85%
- ✅ Sym-Ops一本化
- ✅ description抽出可能

**デメリット**:
- ⚠️ LLMがフォーマット守らない可能性

---

### C. **Plan簡素化 (Step不要化)**

**根本的変更**:
```python
class Plan(BaseModel):
    goal: str  # Markdown全文
    # steps不要、goalのMarkdownで十分
```

**影響**:
- ❌ **Breaking Change**: mark_step_complete()が動作不能
- ❌ TaskTool, Pacemaker修正必要
- ❌ 大規模リファクタリング

---

## 推奨: オプションB

**理由**:
1. ✅ 既存機能（Step管理）を維持
2. ✅ Sym-Ops一本化達成
3. ✅ 精度向上可能（Promptで制御）
4. ⚠️ リスク: LLM依存（ただしAutoRepairでカバー可）

**実装方針**:
1. System Promptにフォーマット例追加
2. Markdownパーサー実装
3. フォールバック: パース失敗時は全体を1 Stepとして扱う

---

## 最終確認事項

### 実装前にテストすべき

1. ✅ 複雑なMarkdown (ネスト、番号形式)
2. ✅ LLMがフォーマット無視した場合
3. ✅ mark_step_complete()の動作
4. ✅ TaskToolとPacemakerの連携

### 成功基準

- Step抽出成功率 **80%+**
- mark_step_complete() 正常動作
- 既存機能に影響なし
