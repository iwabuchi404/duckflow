# Duckflow 実装詳細: 現実的なアプローチ

## 🤔 思考過程のリアルタイム表示 - 実装の現実

### 理想と現実のギャップ

**理想的なビジョン:**
```
ユーザー: "hello.py を作って"
AI: "うーん、hello.pyを作るんですね..." (リアルタイム)
AI: "まずファイルを作成して..." (ストリーミング)
AI: "次にコードを書いて..." (継続表示)
```

**技術的な現実:**
- LLMのAPI呼び出しは基本的に**一括レスポンス**
- ストリーミングAPIは存在するが、「思考過程」を段階的に出力するわけではない
- 真のリアルタイム思考表示は、現在のLLM技術では困難

### 実現可能なアプローチ

#### アプローチ1: 疑似ストリーミング（推奨）
```python
def think_aloud_pseudo_streaming(self, user_message: str):
    """疑似的な思考過程表示"""
    
    # 1. 即座に思考開始を表示
    rich_ui.print_thinking("考え中...")
    
    # 2. 段階的な状況報告
    rich_ui.print_thinking("メッセージを分析しています...")
    time.sleep(0.5)
    
    # 3. LLM呼び出し
    rich_ui.print_thinking("最適な対応を検討中...")
    response = llm.chat(prompt)
    
    # 4. 結果の段階的表示
    rich_ui.print_thinking("対応方法が決まりました")
    return response
```

#### アプローチ2: 真のストリーミング（複雑）
```python
def think_aloud_real_streaming(self, user_message: str):
    """OpenAI Streaming APIを使用"""
    
    stream = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": user_message}],
        stream=True
    )
    
    for chunk in stream:
        if chunk.choices[0].delta.content:
            rich_ui.print_streaming(chunk.choices[0].delta.content)
```

### 推奨実装: Phase 1では疑似ストリーミング

**理由:**
- 実装が簡単で確実
- ユーザー体験は十分向上
- 後でストリーミングAPIに移行可能

**Phase 1での実装:**
```python
class CompanionCore:
    def process_message(self, user_message: str):
        # 疑似思考過程表示
        self._show_thinking_process(user_message)
        
        # 実際の処理
        result = self._actual_processing(user_message)
        
        # 結果の表示
        self._show_result(result)
    
    def _show_thinking_process(self, message: str):
        """段階的な状況表示"""
        rich_ui.print_thinking("🤔 メッセージを読んでいます...")
        time.sleep(0.3)
        
        if "ファイル" in message:
            rich_ui.print_thinking("📁 ファイル操作が必要そうですね...")
            time.sleep(0.3)
        
        rich_ui.print_thinking("💭 どう対応するか考えています...")
```

## 📚 learnings.md とは何か

### コンセプト
プロジェクト固有の知識や教訓を、AIとユーザーが協力して蓄積するMarkdownファイル

### 具体例
```markdown
# プロジェクト学習ノート

## 環境設定
- このプロジェクトではPython 3.10が必要
- 依存関係は requirements.txt で管理
- テストは pytest で実行

## よくあるエラーと解決法
- ImportError: モジュールが見つからない
  → `pip install -r requirements.txt` を実行
  
## ユーザーの好み
- コメントは日本語で書く
- 関数名は snake_case を使用
- テストファイルは test_ プレフィックス

## 失敗パターン
- 2024-08-14: ファイル権限エラーで書き込み失敗
  → 事前に権限チェックを追加
```

### 実装方法
```python
class LearningSystem:
    def __init__(self):
        self.learning_file = "learnings.md"
    
    def learn_lesson(self, category: str, lesson: str, user_confirmed: bool = False):
        """教訓を学習"""
        if user_confirmed:
            self._append_to_learnings(category, lesson)
    
    def get_relevant_knowledge(self, context: str) -> List[str]:
        """関連する知識を取得"""
        # learnings.mdから関連する情報を検索
        pass
```

## 🧠 高度機能の実現方法（簡単な説明）

### 1. プロジェクト固有知識の蓄積
```python
# 実装アプローチ: ファイルベースの簡単な知識ベース
class ProjectKnowledge:
    def observe_pattern(self, action: str, result: str):
        """パターンを観察して学習"""
        if result == "success":
            self.successful_patterns.append(action)
        else:
            self.failed_patterns.append(action)
    
    def suggest_based_on_history(self, current_action: str) -> str:
        """過去の経験に基づく提案"""
        # 類似のアクションで成功したパターンを検索
        pass
```

### 2. プロジェクトの進捗認識
```python
# 実装アプローチ: ファイル変更の追跡
class ProgressTracker:
    def track_file_changes(self):
        """ファイル変更を追跡"""
        current_files = self._scan_project_files()
        changes = self._compare_with_last_scan(current_files)
        return changes
    
    def assess_progress(self) -> str:
        """進捗を評価"""
        changes = self.track_file_changes()
        return f"新しいファイル: {len(changes.new_files)}個, 更新: {len(changes.modified)}個"
```

### 3. 継続的なタスク管理
```python
# 実装アプローチ: シンプルなタスクリスト
class TaskManager:
    def __init__(self):
        self.pending_tasks = []
        self.completed_tasks = []
    
    def add_task(self, task: str, priority: int = 1):
        """タスクを追加"""
        self.pending_tasks.append({"task": task, "priority": priority})
    
    def suggest_next_task(self) -> str:
        """次のタスクを提案"""
        if self.pending_tasks:
            return max(self.pending_tasks, key=lambda x: x["priority"])["task"]
        return "新しいタスクを考えてみましょう"
```

### 4. 失敗パターンの認識と回避
```python
# 実装アプローチ: エラーログの分析
class FailureAnalyzer:
    def __init__(self):
        self.error_history = []
    
    def record_failure(self, action: str, error: str):
        """失敗を記録"""
        self.error_history.append({
            "action": action,
            "error": error,
            "timestamp": datetime.now()
        })
    
    def check_for_known_issues(self, planned_action: str) -> Optional[str]:
        """既知の問題をチェック"""
        similar_failures = [f for f in self.error_history if planned_action in f["action"]]
        if similar_failures:
            return f"注意: 類似のアクションで過去に失敗しています: {similar_failures[-1]['error']}"
        return None
```

### 5. ユーザーの好みの学習
```python
# 実装アプローチ: 選択履歴の追跡
class PreferenceTracker:
    def __init__(self):
        self.preferences = {}
    
    def observe_choice(self, situation: str, choice: str):
        """ユーザーの選択を観察"""
        if situation not in self.preferences:
            self.preferences[situation] = {}
        
        if choice not in self.preferences[situation]:
            self.preferences[situation][choice] = 0
        
        self.preferences[situation][choice] += 1
    
    def suggest_preferred_option(self, situation: str) -> str:
        """好みに基づく提案"""
        if situation in self.preferences:
            return max(self.preferences[situation], key=self.preferences[situation].get)
        return None
```

### 6. プロジェクト特有の慣習の理解
```python
# 実装アプローチ: コードスタイルの分析
class ConventionAnalyzer:
    def analyze_code_style(self, file_path: str) -> Dict[str, str]:
        """コードスタイルを分析"""
        with open(file_path, 'r') as f:
            content = f.read()
        
        conventions = {}
        
        # インデントスタイル
        if '\t' in content:
            conventions['indent'] = 'tabs'
        elif '    ' in content:
            conventions['indent'] = '4_spaces'
        
        # 命名規則
        if re.search(r'def [a-z_]+\(', content):
            conventions['function_naming'] = 'snake_case'
        
        return conventions
```

### 7. コードベース全体の理解
```python
# 実装アプローチ: 依存関係グラフの構築
class CodebaseAnalyzer:
    def build_dependency_graph(self) -> Dict[str, List[str]]:
        """依存関係グラフを構築"""
        dependencies = {}
        
        for py_file in glob.glob("**/*.py", recursive=True):
            imports = self._extract_imports(py_file)
            dependencies[py_file] = imports
        
        return dependencies
    
    def _extract_imports(self, file_path: str) -> List[str]:
        """インポート文を抽出"""
        with open(file_path, 'r') as f:
            content = f.read()
        
        imports = re.findall(r'from (\w+) import|import (\w+)', content)
        return [imp[0] or imp[1] for imp in imports]
```

### 8. アーキテクチャレベルの提案
```python
# 実装アプローチ: パターン認識
class ArchitectureAdvisor:
    def analyze_project_structure(self) -> Dict[str, Any]:
        """プロジェクト構造を分析"""
        structure = {
            "has_tests": os.path.exists("tests/") or os.path.exists("test/"),
            "has_docs": os.path.exists("docs/") or os.path.exists("doc/"),
            "has_config": os.path.exists("config.py") or os.path.exists("settings.py"),
            "file_count": len(glob.glob("**/*.py", recursive=True))
        }
        
        return structure
    
    def suggest_improvements(self, structure: Dict[str, Any]) -> List[str]:
        """改善提案"""
        suggestions = []
        
        if not structure["has_tests"]:
            suggestions.append("テストディレクトリの作成を推奨します")
        
        if structure["file_count"] > 10 and not structure["has_config"]:
            suggestions.append("設定ファイルの分離を検討してください")
        
        return suggestions
```

### 9. モチベーション低下の検知
```python
# 実装アプローチ: 行動パターンの分析
class MotivationDetector:
    def __init__(self):
        self.session_history = []
    
    def analyze_session_pattern(self) -> str:
        """セッションパターンを分析"""
        recent_sessions = self.session_history[-5:]
        
        if len(recent_sessions) < 3:
            return "normal"
        
        # セッション時間の短縮
        avg_duration = sum(s["duration"] for s in recent_sessions) / len(recent_sessions)
        if avg_duration < 10:  # 10分未満
            return "low_motivation"
        
        # エラー率の増加
        error_rate = sum(s["errors"] for s in recent_sessions) / len(recent_sessions)
        if error_rate > 0.5:
            return "frustrated"
        
        return "normal"
    
    def suggest_motivation_boost(self, mood: str) -> str:
        """モチベーション向上の提案"""
        if mood == "low_motivation":
            return "小さなタスクから始めてみませんか？成功体験を積み重ねましょう"
        elif mood == "frustrated":
            return "少し休憩しませんか？難しい問題は一緒に整理してみましょう"
        return "順調に進んでいますね！"
```

## 🚀 Phase 1 の見直し提案

### 削除すべき機能（Phase 2以降に延期）
- **思考過程のリアルタイム表示** → 疑似ストリーミングに簡素化
- **高度な学習機能** → 基本的な履歴記録のみ
- **複雑な個性表現** → シンプルな感情表現のみ

### Phase 1 の現実的な範囲
```python
# Phase 1: 最小限の相棒機能
class MinimalCompanion:
    def __init__(self):
        self.conversation_history = []
        self.simple_preferences = {}
    
    def process_message(self, user_message: str) -> str:
        # 1. 簡単な状況表示
        print("🤔 考えています...")
        
        # 2. 基本的な意図分析
        intent = self._analyze_intent(user_message)
        
        # 3. アクション実行または直接応答
        if intent == "file_operation":
            result = self._handle_file_operation(user_message)
        else:
            result = self._generate_response(user_message)
        
        # 4. 履歴に記録
        self.conversation_history.append({
            "user": user_message,
            "assistant": result,
            "timestamp": datetime.now()
        })
        
        return result
```

## 📋 修正された実装ロードマップ

### Phase 1: 基本的な相棒（1週間）
- ✅ シンプルな対話ループ
- ✅ 基本的なファイル操作
- ✅ 疑似思考過程表示（"考えています..."レベル）
- ✅ 基本的な履歴記録
- ❌ リアルタイムストリーミング（延期）
- ❌ 高度な個性表現（延期）

### Phase 2: 記憶と学習（2週間）
- ✅ learnings.md実装
- ✅ セッション間記憶
- ✅ 基本的な好み学習
- ✅ 簡単な失敗パターン記録

### Phase 3: 高度な理解（継続的）
- ✅ コードベース分析
- ✅ アーキテクチャ提案
- ✅ モチベーション検知
- ✅ 真のストリーミング表示

この現実的なアプローチにより、確実に動作する基盤を構築してから、段階的に高度な機能を追加できます。