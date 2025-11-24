# Enhanced v2.0 リファクタリング コードガイドライン

**作成日**: 2025-08-20  
**対象**: Duckflow Enhanced Dual-Loop System v2.0  
**目的**: リファクタリング時の明確な指針と品質保証

---

## 📋 **基本原則**

### **1.1 単一責任の原則（Single Responsibility Principle）**

#### **1.1.1 原則の定義**
各クラスは**1つの明確で具体的な責任**のみを持ち、その責任に関連する変更理由が**1つだけ**であるべきです。

#### **1.1.2 現在の問題点**
```python
# ❌ 問題のある設計（現在のEnhancedCompanionCore）
class EnhancedCompanionCore:
    """18個の責任を持つ巨大クラス"""
    
    # 責任1: 状態管理
    def get_agent_state(self) -> AgentState: ...
    def _sync_to_legacy_readonly(self): ...
    
    # 責任2: プロンプト生成
    def _build_main_llm_output(self): ...
    def _build_recent_conversation_context(self): ...
    
    # 責任3: ファイル操作
    def _handle_file_read_operation(self): ...
    def _handle_file_write_operation(self): ...
    def _handle_file_list_operation(self): ...
    
    # 責任4: LLM統合
    def _generate_enhanced_response(self): ...
    def _extract_file_path_from_llm(self): ...
    
    # 責任5: プラン管理
    def _generate_plan_unified(self): ...
    def set_plan_state(self): ...
    
    # 責任6: 意図理解
    def analyze_intent_only(self): ...
    def _analyze_intent_enhanced(self): ...
    
    # 責任7: メモリ管理
    def _record_file_operation(self): ...
    def _collect_file_context(self): ...
    
    # 責任8: エラーハンドリング
    def _fallback_file_extraction(self): ...
    def _looks_like_plan(self): ...
    
    # 責任9: レガシー互換
    def _sync_to_legacy_readonly(self): ...
    def toggle_enhanced_mode(self): ...
    
    # 責任10: コード実行
    def _handle_code_execution(self): ...
    
    # 責任11: 承認管理
    def _request_approval(self): ...
    
    # 責任12: コンテキスト構築
    def _build_session_summary(self): ...
    
    # 責任13: ルーティング
    def _handle_routing_based_processing(self): ...
    
    # 責任14: 詳細確認
    def _handle_enhanced_clarification(self): ...
    
    # 責任15: フォールバック処理
    def _fallback_to_legacy(self): ...
    
    # 責任16: バリデーション
    def _validate_llm_output(self): ...
    
    # 責任17: ログ記録
    def _log_operation(self): ...
    
    # 責任18: 設定管理
    def _load_configuration(self): ...
```

#### **1.1.3 責任の分類と分離**

##### **状態管理責任（State Management Responsibility）**
```python
# ✅ 正しい設計: 状態管理専用クラス
class AgentStateManager:
    """唯一の責任: エージェントの状態管理"""
    
    def __init__(self):
        self.agent_state = AgentState()
    
    def update_step(self, new_step: Step) -> None:
        """ステップの更新"""
        self.agent_state.step = new_step
        self._log_state_change("step", new_step)
    
    def update_status(self, new_status: Status) -> None:
        """ステータスの更新"""
        self.agent_state.status = new_status
        self._log_state_change("status", new_status)
    
    def update_fixed_five_items(self, **kwargs) -> None:
        """固定5項目の更新"""
        for key, value in kwargs.items():
            if hasattr(self.agent_state, key):
                setattr(self.agent_state, key, value)
                self._log_state_change(key, value)
    
    def get_state_summary(self) -> Dict[str, Any]:
        """状態の要約取得"""
        return {
            "step": self.agent_state.step.value,
            "status": self.agent_state.status.value,
            "goal": self.agent_state.goal,
            "why_now": self.agent_state.why_now,
            "constraints": self.agent_state.constraints,
            "plan_brief": self.agent_state.plan_brief,
            "open_questions": self.agent_state.open_questions
        }
    
    def _log_state_change(self, field: str, value: Any) -> None:
        """状態変更のログ記録"""
        self.agent_state.last_delta = f"{field}: {value}"
        # ログ記録の実装
```

##### **プロンプト生成責任（Prompt Generation Responsibility）**
```python
# ✅ 正しい設計: プロンプト生成専用クラス
class PromptGenerator:
    """唯一の責任: 3層プロンプトの生成"""
    
    def __init__(self, agent_state_manager: AgentStateManager):
        self.agent_state_manager = agent_state_manager
    
    def generate_base_prompt(self) -> str:
        """Base Prompt（人格・憲法）の生成"""
        state = self.agent_state_manager.get_state_summary()
        return f"""
あなたはDuckflowのAIアシスタントです。

基本人格:
- 安全第一、正確性重視、継続性を大切にする
- ユーザーの学習レベルに合わせた説明を行う

現在のセッション:
- セッションID: {state.get('session_id', 'unknown')}
- 目標: {state.get('goal', '未設定')}
- 制約: {', '.join(state.get('constraints', []))}
"""
    
    def generate_main_prompt(self) -> str:
        """Main Prompt（司令塔）の生成"""
        state = self.agent_state_manager.get_state_summary()
        return f"""
# 現在の対話状況（ワーキングメモリ）

現在のステップ: {state.get('step', 'unknown')}
現在のステータス: {state.get('status', 'unknown')}

# 固定5項目（文脈の核）
目標: {state.get('goal', '未設定')}
なぜ今やるのか: {state.get('why_now', '未設定')}
制約: {', '.join(state.get('constraints', []))}
直近の計画: {', '.join(state.get('plan_brief', []))}
未解決の問い: {', '.join(state.get('open_questions', []))}
"""
    
    def generate_specialized_prompt(self, step: Step) -> str:
        """Specialized Prompt（手順書）の生成"""
        if step == Step.PLANNING:
            return self._generate_planning_prompt()
        elif step == Step.EXECUTION:
            return self._generate_execution_prompt()
        elif step == Step.REVIEW:
            return self._generate_review_prompt()
        else:
            return ""
    
    def _generate_planning_prompt(self) -> str:
        """PLANNING用プロンプト"""
        return """
# 計画作成の専門知識・手順書

## 計画作成の手順
1. 要求の分析と分解（最大3つのステップ）
2. 必要なリソースの特定
3. リスク評価（低/中/高）
4. 成功基準の設定（具体的で測定可能）

## 出力形式
プラン名: [プランの名称]
目的: [達成したいこと]
ステップ:
  1. [ステップ1の詳細]
  2. [ステップ2の詳細]
  3. [ステップ3の詳細]
リスク: [想定されるリスク]
成功基準: [成功の判断基準]
"""
```

##### **ファイル操作責任（File Operation Responsibility）**
```python
# ✅ 正しい設計: ファイル操作専用クラス
class FileOperationManager:
    """唯一の責任: ファイル操作の実行と管理"""
    
    def __init__(self, agent_state_manager: AgentStateManager):
        self.agent_state_manager = agent_state_manager
        self.file_protector = FileProtector()
    
    async def read_file(self, file_path: str) -> str:
        """ファイル読み込み操作"""
        # 安全性チェック
        if not self.file_protector.is_safe_path(file_path):
            raise ValueError(f"安全でないパス: {file_path}")
        
        # ファイル読み込み
        content = self._perform_read(file_path)
        
        # 状態更新
        self.agent_state_manager.update_fixed_five_items(
            context_refs=[f"file:{file_path}"]
        )
        
        return content
    
    async def write_file(self, file_path: str, content: str) -> bool:
        """ファイル書き込み操作"""
        # 安全性チェック
        if not self.file_protector.is_safe_path(file_path):
            raise ValueError(f"安全でないパス: {file_path}")
        
        # 承認チェック
        if self.file_protector.requires_approval(file_path):
            if not await self._request_write_approval(file_path, content):
                raise PermissionError(f"書き込みが承認されませんでした: {file_path}")
        
        # ファイル書き込み
        success = self._perform_write(file_path, content)
        
        # 状態更新
        if success:
            self.agent_state_manager.update_fixed_five_items(
                last_delta=f"ファイル作成: {file_path}"
            )
        
        return success
    
    def list_files(self, directory: str = ".") -> List[str]:
        """ファイル一覧取得"""
        # ディレクトリ内のファイル一覧を取得
        files = self._perform_list(directory)
        
        # 状態更新
        self.agent_state_manager.update_fixed_five_items(
            context_refs=[f"dir:{directory}"]
        )
        
        return files
    
    def _perform_read(self, file_path: str) -> str:
        """実際のファイル読み込み処理"""
        # 実装詳細
        pass
    
    def _perform_write(self, file_path: str, content: str) -> bool:
        """実際のファイル書き込み処理"""
        # 実装詳細
        pass
    
    def _perform_list(self, directory: str) -> List[str]:
        """実際のファイル一覧取得処理"""
        # 実装詳細
        pass
    
    async def _request_write_approval(self, file_path: str, content: str) -> bool:
        """書き込み承認の要求"""
        # 承認処理の実装
        pass
```

##### **LLM統合責任（LLM Integration Responsibility）**
```python
# ✅ 正しい設計: LLM統合専用クラス
class LLMIntegrationManager:
    """唯一の責任: LLMとの統合と通信"""
    
    def __init__(self, prompt_generator: PromptGenerator):
        self.prompt_generator = prompt_generator
        self.llm_client = llm_manager
    
    async def generate_response(self, user_message: str, step: Step) -> str:
        """LLMによる応答生成"""
        # プロンプト生成
        base_prompt = self.prompt_generator.generate_base_prompt()
        main_prompt = self.prompt_generator.generate_main_prompt()
        specialized_prompt = self.prompt_generator.generate_specialized_prompt(step)
        
        # プロンプト統合
        system_prompt = f"{base_prompt}\n\n{main_prompt}\n\n{specialized_prompt}".strip()
        
        # LLM呼び出し
        response = await self.llm_client.generate(
            prompt=user_message,
            metadata={'system_prompt': system_prompt}
        )
        
        return response
    
    async def extract_file_path(self, user_message: str) -> str:
        """LLMによるファイルパス抽出"""
        extraction_prompt = f"""
以下のユーザーメッセージから、操作対象のファイル名を正確に抽出してください。

ユーザーメッセージ: {user_message}

以下のJSON形式で回答してください:
{{
    "file_target": "ファイル名（例: game_doc.md）",
    "action": "実行するアクション（例: read_file）",
    "reasoning": "なぜこのファイル名を抽出したかの理由"
}}
"""
        
        response = await self.llm_client.generate(extraction_prompt)
        return self._parse_file_path_response(response)
    
    def _parse_file_path_response(self, response: str) -> str:
        """LLM応答からファイルパスを抽出"""
        # JSON解析の実装
        pass
```

#### **1.1.4 責任分離の実装パターン**

##### **パターン1: 委譲による責任分離**
```python
# ✅ 正しい設計: 責任を委譲
class EnhancedDualLoopSystem:
    """メインクラス: 統合と調整のみ"""
    
    def __init__(self):
        # 各責任を専用クラスに委譲
        self.agent_state_manager = AgentStateManager()
        self.prompt_generator = PromptGenerator(self.agent_state_manager)
        self.file_operation_manager = FileOperationManager(self.agent_state_manager)
        self.llm_integration_manager = LLMIntegrationManager(self.prompt_generator)
        
        # ループの初期化
        self.chat_loop = EnhancedChatLoop(
            agent_state_manager=self.agent_state_manager,
            llm_integration_manager=self.llm_integration_manager
        )
        self.task_loop = EnhancedTaskLoop(
            agent_state_manager=self.agent_state_manager,
            file_operation_manager=self.file_operation_manager
        )
    
    def start(self):
        """システム起動（調整のみ）"""
        self.chat_loop.start()
        self.task_loop.start()
    
    def stop(self):
        """システム停止（調整のみ）"""
        self.chat_loop.stop()
        self.task_loop.stop()
```

##### **パターン2: インターフェースによる責任分離**
```python
# ✅ 正しい設計: インターフェースによる分離
from abc import ABC, abstractmethod

class IStateManager(ABC):
    """状態管理のインターフェース"""
    
    @abstractmethod
    def update_step(self, new_step: Step) -> None: ...
    
    @abstractmethod
    def update_status(self, new_status: Status) -> None: ...
    
    @abstractmethod
    def get_state_summary(self) -> Dict[str, Any]: ...

class IPromptGenerator(ABC):
    """プロンプト生成のインターフェース"""
    
    @abstractmethod
    def generate_base_prompt(self) -> str: ...
    
    @abstractmethod
    def generate_main_prompt(self) -> str: ...
    
    @abstractmethod
    def generate_specialized_prompt(self, step: Step) -> str: ...

class IFileOperationManager(ABC):
    """ファイル操作のインターフェース"""
    
    @abstractmethod
    async def read_file(self, file_path: str) -> str: ...
    
    @abstractmethod
    async def write_file(self, file_path: str, content: str) -> bool: ...
    
    @abstractmethod
    def list_files(self, directory: str = ".") -> List[str]: ...

# 実装クラス
class AgentStateManager(IStateManager):
    """状態管理の実装"""
    # 実装詳細

class PromptGenerator(IPromptGenerator):
    """プロンプト生成の実装"""
    # 実装詳細

class FileOperationManager(IFileOperationManager):
    """ファイル操作の実装"""
    # 実装詳細
```

#### **1.1.5 責任の変更理由の単一化**

##### **変更理由の分析**
```python
# ❌ 問題のある設計: 複数の変更理由
class EnhancedCompanionCore:
    """変更理由が複数あるクラス"""
    
    # 変更理由1: 状態管理の仕様変更
    def update_agent_state(self): ...
    
    # 変更理由2: プロンプト生成の仕様変更
    def generate_prompt(self): ...
    
    # 変更理由3: ファイル操作の仕様変更
    def handle_file_operation(self): ...
    
    # 変更理由4: LLM統合の仕様変更
    def call_llm(self): ...
    
    # 変更理由5: 承認システムの仕様変更
    def request_approval(self): ...

# ✅ 正しい設計: 変更理由が1つのクラス
class AgentStateManager:
    """変更理由: 状態管理の仕様変更のみ"""
    
    def update_step(self): ...      # 状態管理関連
    def update_status(self): ...    # 状態管理関連
    def update_goal(self): ...      # 状態管理関連
    def get_state(self): ...        # 状態管理関連

class PromptGenerator:
    """変更理由: プロンプト生成の仕様変更のみ"""
    
    def generate_base_prompt(self): ...      # プロンプト関連
    def generate_main_prompt(self): ...      # プロンプト関連
    def generate_specialized_prompt(self): ... # プロンプト関連
```

#### **1.1.6 責任分離のテスト方法**

##### **単一責任のテスト**
```python
def test_single_responsibility():
    """各クラスが単一責任を持つことを確認"""
    
    # 状態管理クラスのテスト
    state_manager = AgentStateManager()
    assert hasattr(state_manager, 'update_step')
    assert hasattr(state_manager, 'update_status')
    assert not hasattr(state_manager, 'generate_prompt')  # 他の責任を持たない
    assert not hasattr(state_manager, 'read_file')        # 他の責任を持たない
    
    # プロンプト生成クラスのテスト
    prompt_generator = PromptGenerator()
    assert hasattr(prompt_generator, 'generate_base_prompt')
    assert hasattr(prompt_generator, 'generate_main_prompt')
    assert not hasattr(prompt_generator, 'update_step')   # 他の責任を持たない
    assert not hasattr(prompt_generator, 'read_file')     # 他の責任を持たない
    
    # ファイル操作クラスのテスト
    file_manager = FileOperationManager()
    assert hasattr(file_manager, 'read_file')
    assert hasattr(file_manager, 'write_file')
    assert not hasattr(file_manager, 'update_step')       # 他の責任を持たない
    assert not hasattr(file_manager, 'generate_prompt')   # 他の責任を持たない
```

#### **1.1.7 責任分離のメリット**

##### **保守性の向上**
- **変更の影響範囲が限定される**: 状態管理の変更がプロンプト生成に影響しない
- **バグの特定が容易**: 問題が発生したクラスの責任が明確
- **テストが簡単**: 各責任を独立してテスト可能

##### **再利用性の向上**
- **独立した再利用**: 状態管理クラスを他のシステムで再利用可能
- **組み合わせの柔軟性**: 必要な責任のみを組み合わせて使用可能
- **拡張性**: 新しい責任を追加する際の影響範囲が限定される

##### **理解しやすさの向上**
- **コードの可読性**: 各クラスの役割が明確
- **新規開発者の学習コスト**: 責任が分離されているため理解しやすい
- **ドキュメント化**: 各責任の説明が明確

---

### **1.2 状態管理の一元化**

#### **1.2.1 現在の問題**
```python
# ❌ 問題のある状態管理（現在）
class EnhancedDualLoopSystem:
    def __init__(self):
        # 状態管理の二重化
        self.state_machine = StateMachine()                    # 状態管理A
        self.enhanced_companion = EnhancedCompanionCore()      # 内部にAgentState
        self.agent_state = self.enhanced_companion.get_agent_state()  # 状態管理B
        
        # 同期が必要（問題の根源）
        self.state_machine.add_state_change_callback(self._sync_state_to_agent_state)
```

#### **1.2.2 解決後の設計**
```python
# ✅ 正しい状態管理（一元化後）
class EnhancedDualLoopSystem:
    def __init__(self):
        # 状態管理の一元化
        self.agent_state = AgentState()                        # 唯一の状態ソース
        
        # 各責任を専用クラスに委譲
        self.state_manager = AgentStateManager(self.agent_state)
        self.prompt_generator = PromptGenerator(self.state_manager)
        self.file_operation_manager = FileOperationManager(self.state_manager)
        self.llm_integration_manager = LLMIntegrationManager(self.prompt_generator)
        
        # ループの初期化（状態を直接参照）
        self.chat_loop = EnhancedChatLoop(
            agent_state=self.agent_state,                      # 直接参照
            llm_integration_manager=self.llm_integration_manager
        )
        self.task_loop = EnhancedTaskLoop(
            agent_state=self.agent_state,                      # 直接参照
            file_operation_manager=self.file_operation_manager
        )
```

---

### **1.3 依存関係の方向性統一**

#### **1.3.1 依存関係の階層構造**
```
Core Layer (最下層)
├── AgentState (唯一の状態管理)
├── Step/Status enums
└── 基本ユーティリティ

Processing Layer (中間層)
├── AgentStateManager (状態管理)
├── PromptGenerator (プロンプト生成)
├── FileOperationManager (ファイル操作)
└── LLMIntegrationManager (LLM統合)

System Layer (最上層)
├── EnhancedDualLoopSystem (統合・調整)
├── EnhancedChatLoop (通信)
└── EnhancedTaskLoop (処理)
```

#### **1.3.2 依存関係の制限**
```python
# ✅ 許可される依存関係（5個以下）
from .state.agent_state import AgentState
from .memory.conversation_memory import conversation_memory
from .prompts.prompt_compiler import prompt_compiler
from .base.llm_client import llm_manager
from .ui import rich_ui

# ❌ 禁止される依存関係
from companion.state.agent_state import AgentState  # 外部パッケージ
from .legacy_companion import CompanionCore        # レガシーシステム
from .state_machine import StateMachine            # 削除予定
```

---

## 📋 **リファクタリング手順ガイドライン**

### **2.1 Phase 1: 状態管理統一（即座実行）**

#### **2.1.1 StateMachine削除**
```python
# companion/enhanced_dual_loop.py
# 削除する行
- self.state_machine = StateMachine()
- self.state_machine.add_state_change_callback(self._sync_state_to_agent_state)
- self._sync_state_to_agent_state(self.state_machine.current_step, self.state_machine.current_status, "init")

# 削除するインポート
- from .state_machine import StateMachine

# 削除するメソッド
- def _sync_state_to_agent_state(self, new_step: Step, new_status: Status, trigger: str):
```

#### **2.1.2 AgentState一本化**
```python
# companion/enhanced_dual_loop.py
# 変更後の設計
+ self.agent_state = AgentState()                        # 唯一の状態
+ self.agent_state.step = Step.PLANNING                  # 直接設定
+ self.agent_state.status = Status.IN_PROGRESS           # 直接設定
```

#### **2.1.3 依存関係削減**
```python
# companion/enhanced_core.py
# 削除するインポート
- from companion.state.agent_state import AgentState
- from companion.validators.llm_output import LLMOutputFormatter
- from companion.prompts.context_assembler import ContextAssembler
- from companion.state.agent_state import Step
- from .core import CompanionCore, ActionType
- from .simple_approval import ApprovalMode
- from .shared_context_manager import SharedContextManager
- from .plan_tool import PlanTool, MessageRef

# 内部モジュールに統一
+ from .state.agent_state import AgentState
+ from .validators.llm_output import LLMOutputFormatter
+ from .prompts.context_assembler import ContextAssembler
```

---

### **2.2 Phase 2: Enhanced専用ループ作成**

#### **2.2.1 Enhanced専用ChatLoop**
```python
# companion/enhanced/chat_loop.py
class EnhancedChatLoop:
    """Enhanced v2.0専用ChatLoop"""
    
    def __init__(self, agent_state: AgentState, llm_integration_manager: LLMIntegrationManager):
        self.agent_state = agent_state          # 直接参照
        self.llm_integration_manager = llm_integration_manager
        
        # v4.0 Final版の機能を移植
        # ただし、状態管理はAgentStateに統一
```

#### **2.2.2 Enhanced専用TaskLoop**
```python
# companion/enhanced/task_loop.py
class EnhancedTaskLoop:
    """Enhanced v2.0専用TaskLoop"""
    
    def __init__(self, agent_state: AgentState, file_operation_manager: FileOperationManager):
        self.agent_state = agent_state          # 直接参照
        self.file_operation_manager = file_operation_manager
        
        # v4.0 Final版の機能を移植
        # ただし、状態管理はAgentStateに統一
```

---

### **2.3 Phase 3: 依存関係整理**

#### **2.3.1 不要なインポート削除**
```python
# companion/enhanced_core.py
# 削除するインポート
- from companion.state.agent_state import AgentState
- from companion.validators.llm_output import LLMOutputFormatter
- from companion.prompts.context_assembler import ContextAssembler
- from companion.state.agent_state import Step
- from .core import CompanionCore, ActionType
- from .simple_approval import ApprovalMode
- from .shared_context_manager import SharedContextManager
- from .plan_tool import PlanTool, MessageRef

# 内部モジュールに統一
+ from .state.agent_state import AgentState
+ from .validators.llm_output import LLMOutputFormatter
+ from .prompts.context_assembler import ContextAssembler
```

#### **2.3.2 循環参照の解消**
```python
# 依存関係の方向統一
# 1. Core Layer → Processing Layer → System Layer
# 2. 逆方向の依存は禁止
# 3. 必要に応じてインターフェースを導入
```

---

## 📋 **品質保証ガイドライン**

### **3.1 コード品質チェック**

#### **3.1.1 依存関係チェック**
- **依存関係数**: 5個以下
- **循環参照**: 完全排除
- **外部パッケージ依存**: 最小限

#### **3.1.2 クラス責任チェック**
- **単一責任**: 各クラスの責任が1つ
- **変更理由**: 変更理由が1つ
- **責任の明確性**: 責任が明確に定義

#### **3.1.3 状態管理チェック**
- **状態ソース**: AgentStateのみ
- **状態更新**: 直接更新のみ
- **同期処理**: 完全排除

### **3.2 パフォーマンス要件**

#### **3.2.1 初期化時間**
- **目標**: 2秒以下
- **測定方法**: システム起動から最初の応答まで

#### **3.2.2 メモリ使用量**
- **目標**: 100MB以下
- **測定方法**: プロセスメモリ使用量

#### **3.2.3 応答時間**
- **目標**: 1秒以下（基本操作）
- **測定方法**: ユーザー入力から応答表示まで

### **3.3 保守性要件**

#### **3.3.1 コード行数**
- **各クラス**: 500行以下
- **各メソッド**: 50行以下
- **全体**: 5000行以下

#### **3.3.2 複雑度**
- **循環複雑度**: 10以下
- **ネスト深さ**: 3以下
- **引数数**: 5個以下

#### **3.3.3 テストカバレッジ**
- **目標**: 80%以上
- **単体テスト**: 各クラス
- **統合テスト**: システム全体

---

## 📋 **成功指標**

### **4.1 短期目標（1-2週間）**

#### **4.1.1 状態管理の統一**
- [ ] StateMachine完全削除
- [ ] AgentState一本化完了
- [ ] 状態の二重化完全解消

#### **4.1.2 依存関係の削減**
- [ ] 依存関係を18個→5個以下に削減
- [ ] 循環参照の完全排除
- [ ] 外部パッケージ依存の最小化

#### **4.1.3 基本動作の安定性**
- [ ] システム起動の安定性確保
- [ ] 基本的な対話機能の動作確認
- [ ] エラー率の50%以下への改善

### **4.2 中期目標（2-4週間）**

#### **4.2.1 Enhanced専用ループ**
- [ ] Enhanced専用ChatLoop実装完了
- [ ] Enhanced専用TaskLoop実装完了
- [ ] v4.0 Final版の完全削除

#### **4.2.2 統合テスト強化**
- [ ] 単体テストの80%以上カバレッジ
- [ ] 統合テストの動作確認
- [ ] 回帰テストの完了

#### **4.2.3 エラーハンドリング改善**
- [ ] エラー率の30%以下への改善
- [ ] エラー復旧機能の実装
- [ ] ログ機能の強化

### **4.3 長期目標（1-2ヶ月）**

#### **4.3.1 設計ドキュメント要求**
- [ ] 設計ドキュメント要求100%実装
- [ ] 3層プロンプトシステム完全実装
- [ ] 状態管理システム完全実装

#### **4.3.2 保守性指標**
- [ ] 保守性指標A評価達成
- [ ] コード品質指標の向上
- [ ] 開発効率の向上

#### **4.3.3 パフォーマンス要件**
- [ ] パフォーマンス要件満足
- [ ] ユーザビリティの向上
- [ ] システム安定性の向上

---

## 📋 **次のアクションアイテム**

### **5.1 即座に実行**

#### **5.1.1 状態管理統一**
1. **StateMachine削除開始** - companion/enhanced_dual_loop.py更新
2. **AgentState一本化** - 状態管理の二重化解消
3. **基本動作確認** - システムの安定性確保

#### **5.1.2 依存関係マッピング**
1. **全モジュールの関係性調査** - 依存関係の可視化
2. **不要インポートの特定** - 削除対象の明確化
3. **循環参照の調査** - 問題箇所の特定

### **5.2 準備作業**

#### **5.2.1 Enhanced専用ループ設計**
1. **v4.0 Final版からの機能移植計画** - 機能移行の詳細設計
2. **状態管理統一設計** - AgentStateとの統合方針
3. **リファクタリング影響分析** - 各変更の影響範囲詳細調査

#### **5.2.2 テスト計画**
1. **単体テスト計画** - 各クラスのテストケース設計
2. **統合テスト計画** - システム全体のテストケース設計
3. **回帰テスト計画** - 既存機能の動作確認計画

---

このガイドラインに従って、Enhanced v2.0のリファクタリングを段階的に進めることで、安定性・保守性の高いシステムを構築できます。

**次のステップ**: このガイドラインに基づいて、Phase 1の状態管理統一から開始しますか？
