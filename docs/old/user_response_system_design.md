# ユーザー応答生成システム設計ドキュメント

**バージョン:** 1.0  
**作成日:** 2025年8月24日  
**目的:** LLM呼び出しをToolとして定義し、既存の三層プロンプトシステムとPecking Orderシステムを活用したユーザー応答生成システムの設計

---

## 1. 概要

### 1.1. 設計思想
- **既存システムの活用**: 三層プロンプトシステムとPecking Orderシステムの設計思想を継承
- **Toolベースの設計**: LLMへの呼び出しをToolとして定義し、LLMが直接呼び出せる形で実装
- **責任分離の明確化**: 各コンポーネントの役割を明確に分離し、保守性と拡張性を確保

### 1.2. システム全体像
```
User Input → LLM Tool Call → ActionPlanTool → Tool Execution → UserResponseTool → User Response
```

---

## 2. 第一段階：PromptCompilerの拡張（Specialized層への応答生成テンプレート追加）

### 2.1. 現状の理解
現在のPromptCompilerは3層構造（Base/Main/Specialized）で動作し、`compile_with_memory`メソッドで各層のコンテキストを統合できます。Specialized層に応答生成用のテンプレートを追加することで、既存の仕組みを活用できます。

### 2.2. 具体的な実装

#### 2.2.1. 応答生成用テンプレートの定義
```python
def _load_response_templates(self) -> Dict[str, str]:
    """応答生成用テンプレートを読み込み"""
    return {
        "file_analysis": self._get_file_analysis_response_template(),
        "search_result": self._get_search_result_response_template(),
        "plan_generation": self._get_plan_generation_response_template(),
        "error": self._get_error_response_template(),
        "generic": self._get_generic_response_template()
    }
```

#### 2.2.2. 応答生成用プロンプトコンパイルメソッドの追加
```python
def compile_response_prompt(self, 
                          pattern: str,
                          action_results: List[ActionResult],
                          user_input: str,
                          agent_state: Optional[AgentState] = None) -> str:
    """応答生成用のプロンプトをコンパイル"""
    
    # Base層：システム設定・制約・安全ルール
    base_context = self._build_response_base_context()
    
    # Main層：会話履歴・短期記憶・現在の状況
    main_context = self._build_response_main_context(action_results, user_input)
    
    # Specialized層：応答生成用テンプレート・専門知識
    specialized_context = self._build_response_specialized_context(action_results, user_input)
    
    # 既存のcompile_with_memoryメソッドを使用
    return self.compile_with_memory(
        pattern=pattern,
        base_context=base_context,
        main_context=main_context,
        specialized_context=specialized_context,
        agent_state=agent_state
    )
```

#### 2.2.3. 各層のコンテキスト構築

**Base層**：応答生成の基本ルールと制約
```python
def _build_response_base_context(self, agent_state: Optional[AgentState] = None) -> str:
    """応答生成のBase層コンテキストを構築"""
    
    base_context = """
あなたはDuckflowのAIアシスタントです。
以下のルールに従って、ユーザーへの適切な応答を生成してください：

1. 実行されたアクションの結果を分かりやすく説明する
2. エラーが発生した場合は、原因と対処法を説明する
3. 次のステップの提案がある場合は、具体的に示す
4. 専門的すぎる用語は避け、一般ユーザーが理解できる表現を使用する
5. 応答は自然な日本語で、親しみやすい口調にする
"""
    
    # タスク状態情報を追加
    if agent_state:
        task_summary = agent_state.get_task_status_summary()
        base_context += f"\n\n--- 現在のタスク状態 ---\n{task_summary}"
    
    return base_context
```

**Main層**：アクション実行結果とユーザー入力の要約
```python
def _build_response_main_context(self, action_results: List[ActionResult], user_input: str, agent_state: Optional[AgentState] = None) -> str:
    """応答生成のMain層コンテキストを構築"""
    
    context_lines = [f"ユーザーの要求: {user_input}"]
    context_lines.append("\n実行されたアクション:")
    
    for i, result in enumerate(action_results, 1):
        context_lines.append(f"{i}. 操作: {result.operation}")
        context_lines.append(f"   結果: {result.data}")
        context_lines.append(f"   成功: {result.success}")
        if result.error_message:
            context_lines.append(f"   エラー: {result.error_message}")
        context_lines.append("")
    
    # タスク状態情報を追加
    if agent_state:
        context_lines.append("--- タスク状態 ---")
        context_lines.append(agent_state.get_task_status_summary())
    
    return "\n".join(context_lines)
```

**Specialized層**：応答生成用の専門テンプレート
```python
def _build_response_specialized_context(self, action_results: List[ActionResult], user_input: str) -> str:
    """応答生成のSpecialized層コンテキストを構築"""
    
    # アクションの種類に基づいてテンプレートを選択
    if any("analyze_file" in result.operation for result in action_results):
        return self._get_file_analysis_response_template()
    elif any("search_content" in result.operation for result in action_results):
        return self._get_search_result_response_template()
    elif any("generate_plan" in result.operation for result in action_results):
        return self._get_plan_generation_response_template()
    else:
        return self._get_generic_response_template()
```

### 2.3. 実装手順
1. **テンプレート定義**：各応答タイプ用のテンプレートを作成
2. **コンテキスト構築メソッド**：各層のコンテキストを構築するメソッドを実装
3. **応答生成用コンパイルメソッド**：`compile_response_prompt`メソッドを実装
4. **テスト**：既存のテストケースに応答生成用のテストを追加

---

## 3. 第二段階：LLM呼び出しをToolとして定義

### 3.1. ActionPlanToolの実装

LLMが直接呼び出せる形で、タスク分解とサブタスク生成を行うToolを実装します。

```python
class ActionPlanTool:
    """LLMが直接呼び出せるタスク分解・サブタスク生成Tool"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)
    
    async def decompose_task(self, user_input: str, task_profile: str, complexity: str) -> Dict[str, Any]:
        """
        ユーザー要求を分析し、実行可能なサブタスクに分解する
        
        Args:
            user_input: ユーザーの要求
            task_profile: タスクプロファイルタイプ
            complexity: タスクの複雑度
            
        Returns:
            タスク分解結果の辞書
        """
        try:
            # LLMプロンプトの構築
            prompt = self._build_decomposition_prompt(user_input, task_profile, complexity)
            
            # LLM呼び出し
            response = await self.llm_client.chat(prompt=prompt)
            
            # レスポンスからサブタスクを解析
            subtasks = self._parse_decomposition_response(response.content)
            
            return {
                "success": True,
                "main_task": user_input,
                "subtasks": subtasks,
                "total_count": len(subtasks),
                "decomposition_method": "llm_based"
            }
            
        except Exception as e:
            self.logger.error(f"タスク分解エラー: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback_subtasks": self._generate_fallback_subtasks(user_input)
            }
```

### 3.2. UserResponseToolの実装

LLMが直接呼び出せる形で、ユーザーへの応答を生成するToolを実装します。

```python
class UserResponseTool:
    """LLMが直接呼び出せるユーザー応答生成Tool"""
    
    def __init__(self, prompt_compiler: PromptCompiler):
        self.prompt_compiler = prompt_compiler
        self.logger = logging.getLogger(__name__)
    
    async def generate_response(self, 
                              action_results: List[Dict[str, Any]], 
                              user_input: str,
                              agent_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        アクション実行結果からユーザーへの応答を生成する
        
        Args:
            action_results: 実行されたアクションの結果リスト
            user_input: ユーザーの元の要求
            agent_state: エージェントの現在の状態
            
        Returns:
            生成された応答の辞書
        """
        try:
            # 応答生成用のプロンプトをコンパイル
            prompt = self.prompt_compiler.compile_response_prompt(
                pattern="base_main_specialized",
                action_results=action_results,
                user_input=user_input,
                agent_state=agent_state
            )
            
            # LLMに応答生成を依頼
            response = await self._call_llm_for_response(prompt)
            
            return {
                "success": True,
                "response": response,
                "generation_method": "llm_based",
                "prompt_length": len(prompt),
                "response_length": len(response)
            }
            
        except Exception as e:
            self.logger.error(f"応答生成エラー: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback_response": self._generate_fallback_response(action_results, user_input)
            }
```

### 3.3. Toolの登録

実装したToolを、LLMが呼び出せるように登録します。

```python
class ToolRegistry:
    """LLMが呼び出せるToolの登録管理"""
    
    def __init__(self):
        self.tools = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """デフォルトのToolを登録"""
        # ActionPlanToolの登録
        self.register_tool("action_plan_tool", {
            "name": "decompose_task",
            "description": "ユーザー要求を分析し、実行可能なサブタスクに分解する",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_input": {
                        "type": "string",
                        "description": "ユーザーの要求"
                    },
                    "task_profile": {
                        "type": "string",
                        "description": "タスクプロファイルタイプ"
                    },
                    "complexity": {
                        "type": "string",
                        "description": "タスクの複雑度"
                    }
                },
                "required": ["user_input"]
            }
        })
        
        # UserResponseToolの登録
        self.register_tool("user_response_tool", {
            "name": "generate_response",
            "description": "アクション実行結果からユーザーへの応答を生成する",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_results": {
                        "type": "array",
                        "description": "実行されたアクションの結果リスト"
                    },
                    "user_input": {
                        "type": "string",
                        "description": "ユーザーの元の要求"
                    }
                },
                "required": ["action_results", "user_input"]
            }
        })
```

### 3.4. 実装手順
1. **ActionPlanTool実装**：タスク分解用のLLM呼び出しとレスポンス解析
2. **UserResponseTool実装**：応答生成用のLLM呼び出しとレスポンス解析
3. **ToolRegistry実装**：Toolの登録と管理機能
4. **テスト**：各Toolの動作確認テスト

---

## 4. 第三段階：AgentStateへのタスク情報追加とプロンプトコンパイラーでの出力

### 4.1. AgentStateへのタスク情報追加

既存のAgentStateクラスに、Pecking Orderシステムの状態情報を追加します。

```python
class AgentState(BaseModel):
    # 既存のフィールド...
    
    # Pecking Orderシステムの状態
    current_task: Optional[Dict[str, Any]] = None
    task_hierarchy: Optional[Dict[str, Any]] = None
    task_progress: Dict[str, Any] = Field(default_factory=dict)
    
    def get_task_status_summary(self) -> str:
        """タスク状態の要約を取得"""
        if not self.current_task:
            return "現在実行中のタスクはありません"
        
        summary_lines = []
        summary_lines.append(f"現在のタスク: {self.current_task.get('title', '不明')}")
        summary_lines.append(f"説明: {self.current_task.get('description', '説明なし')}")
        summary_lines.append(f"状態: {self.current_task.get('status', '不明')}")
        
        if self.task_progress:
            total = self.task_progress.get('total', 0)
            completed = self.task_progress.get('completed', 0)
            if total > 0:
                percentage = (completed / total) * 100
                summary_lines.append(f"進捗: {completed}/{total} 完了 ({percentage:.1f}%)")
        
        return "\n".join(summary_lines)
```

### 4.2. プロンプトコンパイラーでのタスク情報出力

PromptCompilerのBase層またはMain層に、タスク状態情報を出力するように拡張します。

**Base層への追加**：システムの基本情報として常に含める
```python
def _build_response_base_context(self, agent_state: Optional[AgentState] = None) -> str:
    """応答生成のBase層コンテキストを構築"""
    
    base_context = """
あなたはDuckflowのAIアシスタントです。
以下のルールに従って、ユーザーへの適切な応答を生成してください：

1. 実行されたアクションの結果を分かりやすく説明する
2. エラーが発生した場合は、原因と対処法を説明する
3. 次のステップの提案がある場合は、具体的に示す
4. 専門的すぎる用語は避け、一般ユーザーが理解できる表現を使用する
5. 応答は自然な日本語で、親しみやすい口調にする
"""
    
    # タスク状態情報を追加
    if agent_state:
        task_summary = agent_state.get_task_status_summary()
        base_context += f"\n\n--- 現在のタスク状態 ---\n{task_summary}"
    
    return base_context
```

**Main層への追加**：会話履歴と一緒に動的に更新される情報として含める
```python
def _build_response_main_context(self, action_results: List[ActionResult], user_input: str, agent_state: Optional[AgentState] = None) -> str:
    """応答生成のMain層コンテキストを構築"""
    
    context_lines = [f"ユーザーの要求: {user_input}"]
    context_lines.append("\n実行されたアクション:")
    
    for i, result in enumerate(action_results, 1):
        context_lines.append(f"{i}. 操作: {result.operation}")
        context_lines.append(f"   結果: {result.data}")
        context_lines.append(f"   成功: {result.success}")
        if result.error_message:
            context_lines.append(f"   エラー: {result.error_message}")
        context_lines.append("")
    
    # タスク状態情報を追加
    if agent_state:
        context_lines.append("--- タスク状態 ---")
        context_lines.append(agent_state.get_task_status_summary())
    
    return "\n".join(context_lines)
```

### 4.3. 実装手順
1. **AgentState拡張**：タスク状態管理機能を追加
2. **プロンプトコンパイラー拡張**：Base層とMain層にタスク情報を出力
3. **統合テスト**：タスク状態がプロンプトに正しく反映されることを確認

---

## 5. 第四段階：Toolの統合とLLMからの呼び出し

### 5.1. 統合システムの実装

実装したToolを統合し、LLMが直接呼び出せるようにします。

```python
class IntegratedResponseController:
    """Tool統合された応答生成コントローラー"""
    
    def __init__(self, llm_client, prompt_compiler: PromptCompiler):
        self.llm_client = llm_client
        self.prompt_compiler = prompt_compiler
        self.action_plan_tool = ActionPlanTool(llm_client)
        self.user_response_tool = UserResponseTool(prompt_compiler)
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor()
    
    async def process_user_input(self, user_input: str, agent_state: AgentState) -> str:
        """ユーザー入力を処理して応答を生成"""
        
        try:
            # 1. LLMにTool呼び出しを依頼（ActionPlanTool使用）
            action_plan = await self._generate_action_plan_llm(user_input, agent_state)
            
            # 2. 生成されたアクションを実行
            action_results = []
            for action in action_plan.get('subtasks', []):
                result = await self.tool_executor.execute(action)
                action_results.append(result)
            
            # 3. LLMにTool呼び出しを依頼（UserResponseTool使用）
            response = await self._generate_response_llm(action_results, user_input, agent_state)
            
            return response.get('response', '応答の生成に失敗しました')
            
        except Exception as e:
            return f"申し訳ありません、処理中にエラーが発生しました: {str(e)}"
```

### 5.2. LLMからのTool呼び出し

LLMがToolを呼び出せるように、システムを統合します。

```python
async def _generate_action_plan_llm(self, user_input: str, agent_state: AgentState) -> Dict[str, Any]:
    """LLMにActionPlanToolの使用を依頼"""
    
    # LLMにTool呼び出しを依頼するプロンプトを構築
    prompt = f"""
以下のユーザー要求を分析し、適切なToolを使用してタスク分解を行ってください。

ユーザー要求: {user_input}

利用可能なTool:
- action_plan_tool.decompose_task: ユーザー要求を分析し、実行可能なサブタスクに分解する

以下のJSON形式でTool呼び出しを指定してください：

```json
{{
    "tool_calls": [
        {{
            "tool": "action_plan_tool.decompose_task",
            "parameters": {{
                "user_input": "{user_input}",
                "task_profile": "適切なタスクプロファイル",
                "complexity": "適切な複雑度"
            }}
        }}
    ]
}}
```
"""
    
    # LLM呼び出し
    response = await self.llm_client.chat(prompt=prompt)
    
    # レスポンスからTool呼び出しを解析
    tool_calls = self._parse_tool_calls(response.content)
    
    # Toolを実行
    results = []
    for tool_call in tool_calls:
        if tool_call['tool'] == 'action_plan_tool.decompose_task':
            result = await self.action_plan_tool.decompose_task(**tool_call['parameters'])
            results.append(result)
    
    # 最初の結果を返す
    return results[0] if results else {"subtasks": []}
```

### 5.3. 実装手順
1. **統合システム実装**：IntegratedResponseControllerの実装
2. **Tool呼び出し実装**：LLMからのTool呼び出し処理の実装
3. **統合テスト**：全体の動作確認テスト

---

## 6. 実装順序とスケジュール

### 6.1. 実装順序
1. **第一段階**：PromptCompilerの拡張（1-2日）
2. **第三段階**：AgentStateへのタスク情報追加（1日）
3. **第二段階**：ActionPlanToolとUserResponseToolの実装（2-3日）
4. **第四段階**：Toolの統合とLLMからの呼び出し（2-3日）
5. **統合テスト**：全体の動作確認（1日）

### 6.2. 期待される効果
- **問題解決**：現在のハードコードされたActionList生成の問題を解決
- **システム統合**：既存の三層プロンプトシステムとPecking Orderシステムの連携強化
- **保守性向上**：既存の設計思想を継承した実装により、保守性と拡張性を確保

---

## 7. 技術的な考慮事項

### 7.1. エラーハンドリング
- 各Toolで適切なエラーハンドリングを実装
- LLM呼び出し失敗時のフォールバック処理
- レスポンス解析失敗時の適切な処理

### 7.2. パフォーマンス
- プロンプトのキャッシュ機能を活用
- 不要なLLM呼び出しを最小限に抑制
- 非同期処理の適切な実装

### 7.3. 拡張性
- 新しいToolの追加が容易な設計
- 既存の三層プロンプトシステムとの互換性維持
- 設定による動作のカスタマイズ

---

## 8. まとめ

この設計により、既存システムの設計思想を維持しながら、LLMが直接Toolを呼び出せる形で、タスク分解と応答生成を行うシステムを構築できます。既存の三層プロンプトシステムとPecking Orderシステムを活用することで、開発効率と保守性を両立させた実装が可能になります。

---

**最終更新:** 2025年8月24日  
**次回レビュー:** 実装開始時
