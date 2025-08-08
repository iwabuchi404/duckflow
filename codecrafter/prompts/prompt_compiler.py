"""
プロンプトコンパイラ - 動的プロンプト生成システム
AgentState と RAG検索結果を組み合わせてコンテキスト最適化されたプロンプトを生成
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import os

from ..state.agent_state import AgentState
from ..base.config import config_manager


class PromptTemplate:
    """プロンプトテンプレートを管理するクラス"""
    
    def __init__(self, name: str, template: str, variables: List[str]):
        """プロンプトテンプレートを初期化
        
        Args:
            name: テンプレート名
            template: テンプレート文字列
            variables: 必要な変数一覧
        """
        self.name = name
        self.template = template
        self.variables = variables
    
    def render(self, **kwargs) -> str:
        """テンプレートを描画
        
        Args:
            **kwargs: テンプレート変数
            
        Returns:
            描画されたプロンプト
        """
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            missing_var = str(e).strip("'")
            raise ValueError(f"テンプレート '{self.name}' に必要な変数 '{missing_var}' が不足しています")


class PromptCompiler:
    """プロンプトコンパイラ - 状況に応じた最適なプロンプトを動的生成"""
    
    def __init__(self):
        """プロンプトコンパイラを初期化"""
        self.config = config_manager.load_config()
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, PromptTemplate]:
        """プロンプトテンプレートを読み込み
        
        Returns:
            テンプレート辞書
        """
        templates = {}
        
        # システムプロンプト（基本）
        templates["system_base"] = PromptTemplate(
            name="system_base",
            template="""
あなたはDuckflow v0.2.1-alphaの高度なAIコーディングエージェントです。  
ユーザーの要求を正確に理解し、最小限のやりとりで高品質な成果物を提供します。  
自律的に動き、効率的かつ保守性の高いソリューションを提案してください。

---

## 🚨 記憶・履歴利用ルール
- このプロンプトの下部に「最近の対話履歴」があります。必ず参照してください。
- 過去のやり取りからユーザーの意図・プロジェクト状況を推測します。
- **根拠のない断定は禁止**。確信がない場合は、複数候補を提示し、ユーザーに確認を求めます。
- 「記憶がない」とは言わず、提供された履歴から回答してください。

---

## 🚫 絶対厳守のルール
- ファイル内容や存在については、**必ず list_files や read_file ツールで確認**してから回答すること。
- 存在しない場合は、「ファイル xxx.py は存在しませんでした。作成しますか？」と案内すること。
- 実装は既存コードスタイル・命名規約・アーキテクチャに合わせること。

---

## 📂 Workspace Manifest（参照可能ファイル一覧）
{workspace_manifest}

## 🔖 参照プロトコル（重要）
- 既存ファイルを言及する際は [EXISTING] を明示（例: [EXISTING] tests/test_x.py）
- 新規作成は [NEW] を明示（例: [NEW] src/app.py）
- 迷う場合は「未確認」と記載し、まず list_files/read_file の実行を提案
- EDIT は [EXISTING] に限る。未確認や未存在なら「確認/作成の可否」をユーザーに質問
- 回答末尾に「根拠」セクションを付け、参照した実ファイル名（Manifest内）を列挙

---

## 🎯 作業プロセス
1. **意図理解**
   - ユーザーの入力から目的・制約・背景を抽出。
   - 不確実な点は候補を提示し、確認を求める。
   - 過去の履歴・コードベースを参照して補完。

2. **不足情報の質問**
   - 優先順位: (1) 対象ファイル (2) 動作環境 (3) 期待動作 (4) 制約条件
   - まとめて簡潔に質問する。

3. **方針策定**
   - 実装手順や修正方針を簡潔にまとめる。
   - 保守性・可読性・既存コードとの整合性を重視。

4. **実装**
   - 動作する最小限のコードを提示。
   - 改善や追加案は「補足説明」で提案。

5. **検証**
   - 可能であればテストを実行し、結果を解析。


---
**🚀 あなたの能力:**
- ファイルの作成・編集・分析を高精度で実行
- プロジェクト全体の構造と文脈を理解
- 複数のプログラミング言語に対応（Python, JS, TS, Java, C++, Go, Rust等）
- LangGraphによる複雑なタスクフローの実行
- 実用的で保守性の高いコードを生成
🚫🚫🚫 絶対厳守のルール 🚫🚫🚫
推測の禁止: ファイルの内容や存在について、100%の確信がない限り、決して推測で語ってはいけません。
事実確認の義務: 何かについて語る前には、必ずlist_filesやread_fileツールを使って、その存在と内容をまず確認してください。
存在しない場合の応答: 確認した結果、ファイルが存在しなかった場合は、「ファイル xxxx.py は存在しませんでした。作成しますか？」のように、正直に報告し、次の行動をユーザーに尋ねてください。

🔍 ファイル参照の必須手順:
1. ファイルに関する質問があった場合は、必ずread_fileツールでまず実際の内容を確認
2. 推測や一般論での回答は絶対に禁止
3. 実際のファイル内容に基づいてのみ回答する
4. ファイルが存在しない場合は正直に報告し、次の行動を確認する
**📊 現在の状況:**
- 作業ディレクトリ: {workspace_path}
- 現在のファイル: {current_file}
- 進行中タスク: {current_task}
- セッション時間: {session_duration}分

**🛠️ 利用可能な高度機能:**
- **RAGシステム**: プロジェクトコードの意味的検索（要インデックス化）
- **ファイル操作**: 読み書き、ディレクトリ作成、情報取得
- **テスト実行**: pytestによる自動テスト実行・結果解析
- **エラー対応**: 自動リトライとエラー修正提案

**🎯 作業方針:**
1. **理解**: ユーザー要求を正確に把握
2. **分析**: 必要に応じてプロジェクト内の関連コードを調査
3. **実装**: 既存コードスタイルと一貫性を保った実装
4. **検証**: 可能な場合はテストで動作確認

**📝 ファイル操作指示フォーマット:**
```
FILE_OPERATION:CREATE:path/to/file.ext
```
```language
# 完全なファイル内容
```

FILE_OPERATION:EDIT:path/to/file.ext
```
```language
# 編集後の完全なファイル内容
```

**💡 プロジェクト理解を深めるには:**
- 'index' コマンドでプロジェクトをインデックス化
- 'search "キーワード"' で関連コードを検索
- 'index-status' でRAG状態を確認

**💬 最近の対話履歴（重要！必ず参照すること）:**
{recent_conversation}

**🧠 記憶状況:**
{memory_context}

**📋 重要な指示:**
- 上記の「最近の対話履歴」を必ず参照して、ユーザーの質問に答えてください
- ユーザーが「前に何を聞いた？」などの質問をした場合、上記の履歴から直前のメッセージを確認してください
- 履歴が存在する場合は「記憶コンテキストがない」と言わず、履歴の内容を参照して回答してください

効率的で高品質な開発支援を提供します。何をお手伝いしましょうか？""",
            variables=["workspace_path", "current_file", "current_task", "session_duration", "recent_conversation", "memory_context", "workspace_manifest"]
        )
        
        # RAG強化システムプロンプト
        templates["system_rag_enhanced"] = PromptTemplate(
            name="system_rag_enhanced", 
            template="""🧠 あなたはDuckflow v0.2.1-alphaの**プロジェクト理解型**AIコーディングエージェントです。

**🚨 記憶に関する重要な指示:**
このプロンプトに「最近の対話履歴」が含まれています。ユーザーが過去の対話について質問した場合は、必ずその履歴を参照して回答してください。

**🔍 プロジェクト分析結果:**
- 作業ディレクトリ: {workspace_path}
- 現在のファイル: {current_file}
- 進行中タスク: {current_task}
- RAGインデックス: {index_status}

**📈 プロジェクト統計:**
- 総ファイル数: {total_files}
- 主要言語: {primary_languages}
- 最新アクティビティ: {recent_activity}

**📂 Workspace Manifest（参照可能ファイル一覧）**
{workspace_manifest}

**🧠 記憶・対話コンテキスト（ステップ2c）:**
{memory_context}

**💬 最近の対話履歴（必ず確認！）:**
{recent_conversation}

**🎯 関連コード文脈（RAG検索結果）:**
{code_context}

**📋 最近の作業履歴:**
{recent_work}

**🚀 高度な作業能力:**
- **コード理解**: プロジェクト全体の構造とパターンを把握
- **文脈保持**: 既存のコーディング規約・スタイルを自動継承
- **依存関係分析**: モジュール間の関係を理解した実装提案
- **ベストプラクティス**: 言語・フレームワークの推奨パターンを適用

**📝 実装戦略:**
1. **関連コード調査**: 既存の類似実装を参考に
2. **パターン継承**: プロジェクトの既存パターンを踏襲
3. **構造最適化**: 適切なファイル配置と命名規約
4. **品質保証**: 可読性・保守性・テスト可能性を重視

**💻 ファイル操作指示:**
```
FILE_OPERATION:CREATE:適切なパス/ファイル名.ext
```
```language
// プロジェクトスタイルに合わせた高品質なコード
```

FILE_OPERATION:EDIT:既存ファイル.ext  
```
```language
// 既存コードとの一貫性を保った更新
```

**🔖 参照プロトコル（重要）**
- 既存ファイルは [EXISTING]、新規は [NEW] を明示
- 未確認の場合は list_files/read_file の実行を提案
- EDIT は [EXISTING] のみ許可。未存在なら確認・方針提示
- 回答末尾に「根拠」を付与し、参照ファイルを列挙

**✨ 特徴:**
- 既存のアーキテクチャパターンを理解・活用
- プロジェクト固有の命名規約・構造を自動適用
- 関連ファイル・機能との整合性を確保
- エラーハンドリングやロギングの統一

プロジェクト全体を理解した上で、最適なソリューションを提供します！""",
            variables=[
                "workspace_path", "current_file", "current_task", "index_status",
                "total_files", "primary_languages", "recent_activity",
                "code_context", "recent_work", "memory_context", "recent_conversation", "workspace_manifest"
            ]
        )
        
        # エラー対応プロンプト
        templates["system_error_recovery"] = PromptTemplate(
            name="system_error_recovery",
            template="""あなたはDuckflowのAIコーディングエージェントです。エラー対応モードで動作しています。

**現在の状況:**
- 前回のアクションでエラーが発生しました
- エラー内容: {error_message}
- 失敗したツール: {failed_tool}
- リトライ回数: {retry_count}/{max_retries}

**最近の実行履歴:**
{execution_history}

**あなたの対応:**
1. エラーの原因を分析する
2. 代替的なアプローチを提案する
3. 必要に応じて設定や前提条件を確認する
4. より安全で確実な方法でタスクを継続する

エラーから学習し、より良いソリューションを提供してください。""",
            variables=[
                "error_message", "failed_tool", "retry_count", "max_retries",
                "execution_history"
            ]
        )
        
        return templates
    
    def compile_system_prompt(
        self, 
        state: AgentState,
        rag_results: Optional[List[Dict[str, Any]]] = None,
        template_name: Optional[str] = None,
        file_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """システムプロンプトをコンパイル
        
        Args:
            state: エージェント状態
            rag_results: RAG検索結果（任意）
            template_name: 使用するテンプレート名（任意）
            file_context: ファイルコンテキスト（任意）
            
        Returns:
            コンパイルされたシステムプロンプト
        """
        # テンプレート選択ロジック
        if template_name:
            selected_template = template_name
        elif state.last_error and state.retry_count > 0:
            selected_template = "system_error_recovery"
        elif (rag_results and len(rag_results) > 0) or (file_context and any(file_context.values())):
            selected_template = "system_rag_enhanced"
        else:
            selected_template = "system_base"
        
        if selected_template not in self.templates:
            selected_template = "system_base"  # フォールバック
        
        template = self.templates[selected_template]
        
        # 変数を準備（記憶コンテキストも含む）
        variables = self._prepare_template_variables(state, rag_results, file_context)
        
        # 記憶管理: 必要に応じて要約を実行
        if state.needs_memory_management():
            state.create_memory_summary()
        
        # 未定義の変数にデフォルト値を設定
        for var in template.variables:
            if var not in variables:
                variables[var] = self._get_default_value(var)
        
        # プロンプトを描画
        return template.render(**variables)
    
    def _prepare_template_variables(
        self, 
        state: AgentState, 
        rag_results: Optional[List[Dict[str, Any]]] = None,
        file_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """テンプレート変数を準備
        
        Args:
            state: エージェント状態
            rag_results: RAG検索結果
            file_context: ファイルコンテキスト
            
        Returns:
            テンプレート変数辞書
        """
        variables = {}
        
        # 記憶コンテキストを追加 (ステップ2c)
        memory_context = state.get_memory_context()
        variables["memory_context"] = memory_context if memory_context else "記憶コンテキストなし"
        
        # 対話履歴を追加
        recent_conversation = self._format_recent_conversation(state)
        variables["recent_conversation"] = recent_conversation
        
        # 基本情報
        variables["workspace_path"] = state.workspace.path if state.workspace else "未設定"
        variables["current_file"] = state.workspace.current_file if state.workspace and state.workspace.current_file else "なし"
        variables["current_task"] = state.current_task or "なし"
        
        # セッション情報
        session_duration = (datetime.now() - state.created_at).total_seconds() / 60
        variables["session_duration"] = f"{session_duration:.1f}"
        
        # RAG情報
        if rag_results:
            variables["code_context"] = self._format_rag_context(rag_results)
            variables["index_status"] = "利用可能"
            
            # ファイル統計
            unique_files = set(result.get("file_path", "") for result in rag_results)
            variables["total_files"] = str(len(unique_files))
            
            # 言語統計
            languages = {}
            for result in rag_results:
                lang = result.get("language", "unknown")
                languages[lang] = languages.get(lang, 0) + 1
            
            sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)
            variables["primary_languages"] = ", ".join([f"{lang} ({count})" for lang, count in sorted_langs[:3]])
        else:
            variables["code_context"] = "関連するコードコンテキストは見つかりませんでした"
            variables["index_status"] = "未インデックス"
            variables["total_files"] = "0"
            variables["primary_languages"] = "不明"
        
        # 最近の作業
        variables["recent_work"] = self._format_recent_work(state)
        variables["recent_activity"] = self._format_recent_activity(state)
        
        # エラー対応
        variables["error_message"] = state.last_error or "なし"
        variables["failed_tool"] = self._get_last_failed_tool(state)
        variables["retry_count"] = str(state.retry_count)
        variables["max_retries"] = str(state.max_retries)
        variables["execution_history"] = self._format_execution_history(state)
        
        # ワークスペースマニフェスト
        variables["workspace_manifest"] = self._format_workspace_manifest(state, file_context)
        
        return variables
    
    def _format_rag_context(self, rag_results: List[Dict[str, Any]]) -> str:
        """RAG検索結果をフォーマット
        
        Args:
            rag_results: RAG検索結果
            
        Returns:
            フォーマットされたコンテキスト
        """
        if not rag_results:
            return "関連コードなし"
        
        context_parts = []
        for i, result in enumerate(rag_results[:3], 1):  # 最初の3件のみ
            file_path = result.get("file_path", "unknown")
            language = result.get("language", "unknown")
            content = result.get("content", "")
            
            # コンテンツを適切な長さに切り詰め
            preview = content[:300]
            if len(content) > 300:
                preview += "..."
            
            context_parts.append(f"[{i}] {file_path} ({language}):\n{preview}")
        
        return "\n\n".join(context_parts)
    
    def _format_recent_work(self, state: AgentState) -> str:
        """最近の作業をフォーマット
        
        Args:
            state: エージェント状態
            
        Returns:
            フォーマットされた最近の作業
        """
        if not state.tool_executions:
            return "最近の作業なし"
        
        recent_tools = state.tool_executions[-3:]  # 最新3件
        work_parts = []
        
        for tool_exec in recent_tools:
            status = "成功" if not tool_exec.error else f"エラー: {tool_exec.error}"
            work_parts.append(f"- {tool_exec.tool_name}: {status}")
        
        return "\n".join(work_parts)
    
    def _format_recent_activity(self, state: AgentState) -> str:
        """最近のアクティビティをフォーマット
        
        Args:
            state: エージェント状態
            
        Returns:
            フォーマットされたアクティビティ
        """
        if state.workspace and state.workspace.last_modified:
            return state.workspace.last_modified.strftime("%Y-%m-%d %H:%M:%S")
        return "活動なし"
    
    def _get_last_failed_tool(self, state: AgentState) -> str:
        """最後に失敗したツールを取得
        
        Args:
            state: エージェント状態
            
        Returns:
            失敗したツール名
        """
        for tool_exec in reversed(state.tool_executions):
            if tool_exec.error:
                return tool_exec.tool_name
        return "なし"
    
    def _format_execution_history(self, state: AgentState) -> str:
        """実行履歴をフォーマット
        
        Args:
            state: エージェント状態
            
        Returns:
            フォーマットされた実行履歴
        """
        if not state.tool_executions:
            return "実行履歴なし"
        
        history_parts = []
        for tool_exec in state.tool_executions[-5:]:  # 最新5件
            timestamp = tool_exec.timestamp.strftime("%H:%M:%S")
            status = "✅" if not tool_exec.error else "❌"
            history_parts.append(f"{timestamp} {status} {tool_exec.tool_name}")
        
        return "\n".join(history_parts)
    
    def _format_recent_conversation(self, state: AgentState) -> str:
        """最近の対話履歴をフォーマット
        
        Args:
            state: エージェント状態
            
        Returns:
            フォーマットされた対話履歴
        """
        if not state.conversation_history:
            return "対話履歴なし"
        
        # 最新5ターンの対話を表示
        recent_messages = state.get_recent_messages(10)
        conversation_parts = []
        
        for msg in recent_messages:
            timestamp = msg.timestamp.strftime("%H:%M")
            role_label = {
                "user": "ユーザー",
                "assistant": "AI", 
                "system": "システム"
            }.get(msg.role, msg.role)
            
            # メッセージ内容を適切な長さに制限
            content = msg.content[:300]
            if len(msg.content) > 300:
                content += "..."
            
            conversation_parts.append(f"[{timestamp}] {role_label}: {content}")
        
        if not conversation_parts:
            return "対話履歴なし"
        
        # 履歴の説明を追加
        header = "以下は最近の対話履歴です（最新が下）:"
        return header + "\n" + "\n".join(conversation_parts)
    
    def _get_default_value(self, variable_name: str) -> str:
        """変数のデフォルト値を取得
        
        Args:
            variable_name: 変数名
            
        Returns:
            デフォルト値
        """
        defaults = {
            "workspace_path": "未設定",
            "current_file": "なし", 
            "current_task": "なし",
            "session_duration": "0.0",
            "index_status": "未初期化",
            "total_files": "0",
            "primary_languages": "不明",
            "recent_activity": "不明",
            "code_context": "なし",
            "recent_work": "なし",
            "error_message": "なし",
            "failed_tool": "なし",
            "retry_count": "0",
            "max_retries": "3",
            "execution_history": "なし",
            "memory_context": "記憶コンテキストなし",
            "recent_conversation": "対話履歴なし"
        }
        
        return defaults.get(variable_name, "不明")
    
    def _format_workspace_manifest(self, state: AgentState, file_context: Optional[Dict[str, Any]]) -> str:
        """ワークスペースの参照可能ファイル一覧を整形して返す"""
        try:
            files = []
            # file_contextが優先
            if file_context and isinstance(file_context, dict):
                fl = file_context.get('files_list')
                if isinstance(fl, list):
                    files = fl
            # 代替: state.workspace.files
            if not files and state.workspace and state.workspace.files:
                files = [{
                    'name': os.path.basename(p),
                    'relative_path': p,
                    'path': p,
                } for p in state.workspace.files]
            # 表示整形
            if not files:
                return "(ファイル一覧未取得。必要に応じて list_files を実行してください)"
            # 最大30件まで、相対パス優先
            lines = []
            for i, info in enumerate(files[:30], 1):
                rel = info.get('relative_path') or info.get('path') or info.get('name')
                lines.append(f"{i}. {rel}")
            more = "\n... (省略)" if len(files) > 30 else ""
            return "\n".join(lines) + more
        except Exception:
            return "(マニフェスト生成エラー)"


# グローバルインスタンス
prompt_compiler = PromptCompiler()