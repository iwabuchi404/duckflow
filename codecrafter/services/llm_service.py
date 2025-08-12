"""
LLMService - タスク別に最適化されたLLMアクセスサービス

統合タスクループアーキテクチャの中核となる、専門化されたLLMサービス層
各タスクの性質に応じて最適なLLMを選択し、再利用可能な形で提供する
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass

from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate

from ..base.llm_client import llm_manager
from ..base.config import config_manager
from ..schemas import ContentPlan, ComplexityLevel


@dataclass
class RequirementItem:
    """個別要件の追跡"""
    requirement: str                    # 要件内容
    satisfaction_level: float = 0.0    # 達成度 (0.0-1.0)
    evidence: List[str] = None         # 満たす証拠情報
    priority: int = 1                  # 優先度 (1=高, 2=中, 3=低)
    
    def __post_init__(self):
        if self.evidence is None:
            self.evidence = []
        elif isinstance(self.evidence, str):
            # 文字列の場合はリストに変換
            self.evidence = [self.evidence]
        elif not isinstance(self.evidence, list):
            # 想定外の型の場合は空リストに
            self.evidence = []


@dataclass 
class SatisfactionEvaluation:
    """満足度評価結果"""
    overall_score: float                    # 全体満足度 (0.0-1.0)
    requirement_scores: Dict[str, float]    # 要件別満足度
    missing_aspects: List[str]              # 不足している側面
    quality_assessment: str                 # 品質評価コメント
    completion_recommendation: bool         # 完了推奨フラグ
    
    def __post_init__(self):
        if not hasattr(self, 'requirement_scores') or self.requirement_scores is None:
            self.requirement_scores = {}
        
        # missing_aspectsが文字列で来る場合があるので、リストに変換
        if not hasattr(self, 'missing_aspects') or self.missing_aspects is None:
            self.missing_aspects = []
        elif isinstance(self.missing_aspects, str):
            # 文字列の場合はリストに変換
            self.missing_aspects = [self.missing_aspects]
        elif not isinstance(self.missing_aspects, list):
            # 想定外の型の場合は空リストに
            self.missing_aspects = []


@dataclass
class MissingInfoAnalysis:
    """不足情報分析結果"""
    missing_items: List[str]           # 不足している具体的項目
    priority_order: List[str]          # 優先順位付けされた不足項目
    suggested_actions: List[str]       # 推奨アクション
    constraints: List[str]             # 特定された制約
    alternative_approaches: List[str]  # 代替アプローチ
    
    def __post_init__(self):
        for field in ['missing_items', 'priority_order', 'suggested_actions', 'constraints', 'alternative_approaches']:
            if not hasattr(self, field) or getattr(self, field) is None:
                setattr(self, field, [])
            else:
                value = getattr(self, field)
                if isinstance(value, str):
                    # 文字列の場合はリストに変換
                    setattr(self, field, [value])
                elif not isinstance(value, list):
                    # 想定外の型の場合は空リストに
                    setattr(self, field, [])


@dataclass
class TaskContext:
    """タスク実行コンテキスト"""
    workspace_info: Optional[Any] = None
    available_tools: List[str] = None
    previous_attempts: List[Any] = None
    learned_constraints: List[str] = None
    
    def __post_init__(self):
        for field in ['available_tools', 'previous_attempts', 'learned_constraints']:
            if getattr(self, field) is None:
                setattr(self, field, [])
            else:
                value = getattr(self, field)
                if isinstance(value, str):
                    # 文字列の場合はリストに変換
                    setattr(self, field, [value])
                elif not isinstance(value, list):
                    # 想定外の型の場合は空リストに（previous_attemptsは例外）
                    if field != 'previous_attempts':
                        setattr(self, field, [])


class LLMService:
    """タスク別に最適化されたLLMサービス"""
    
    def __init__(self):
        """LLMサービスを初期化"""
        self.config = config_manager.load_config()
        
        # 3層LLM構成
        # 注意: 現在のllm_managerは単一LLMのため、実装時は同じクライアントを使用
        # 将来的にはconfig.yamlベースで異なるLLMを割り当て
        self.creative_llm = llm_manager      # 複雑な計画立案・創造的思考
        self.fast_llm = llm_manager          # 高速評価・分類・要約  
        self.evaluator_llm = llm_manager     # 深い分析・客観的判定
    
    # === 計画立案サービス ===
    
    def plan_initial_execution(self, user_request: str, context: TaskContext) -> Dict[str, Any]:
        """
        初回実行計画の立案
        
        Args:
            user_request: ユーザーの要求
            context: タスク実行コンテキスト
            
        Returns:
            実行計画の辞書
        """
        try:
            planning_prompt = self._build_initial_planning_prompt(user_request, context)
            
            response = self.creative_llm.chat(planning_prompt, system_prompt=self._get_planning_system_prompt())
            
            return self._parse_execution_plan(response)
            
        except Exception as e:
            return self._create_fallback_plan(user_request, str(e))
    
    def generate_content_plan(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        TaskProfile特化のコンテンツ計画生成（PydanticOutputParser使用）
        
        Args:
            request: コンテンツ計画要求（user_request, task_profile_type, detected_targets等）
            
        Returns:
            コンテンツ計画の辞書 or None
        """
        try:
            user_request = request.get("user_request", "")
            task_profile_type = request.get("task_profile_type", "information_request")
            detected_targets = request.get("detected_targets", [])
            detected_files = request.get("detected_files", [])
            context_info = request.get("context", {})
            
            # PydanticOutputParserの設定
            parser = PydanticOutputParser(pydantic_object=ContentPlan)
            
            # 動的プロンプトテンプレートの構築
            template = """TaskProfile「{task_profile_type}」に基づいて、詳細なコンテンツ分析計画を立案してください。

**ユーザー要求:** {user_request}

**TaskProfile種別:** {task_profile_type}
**検出された対象:** {detected_targets}
**対象ファイル:** {detected_files}

**TaskProfile別の分析重点:**
{task_analysis_focus}

**分析すべき項目:**
1. **要求の詳細分析**: ユーザーが真に求めている情報の特定
2. **コンテンツ構造計画**: 最終応答で提供すべき情報の構造
3. **実行ステップ**: 情報収集から応答生成までの具体的手順
4. **必要ツール**: 使用すべきツール群（読み取り専用推奨）
5. **データ優先度**: 収集すべきデータの重要度順位

{format_instructions}
"""
            
            prompt = PromptTemplate(
                template=template,
                input_variables=[
                    "user_request", 
                    "task_profile_type", 
                    "detected_targets", 
                    "detected_files",
                    "task_analysis_focus"
                ],
                partial_variables={"format_instructions": parser.get_format_instructions()}
            )
            
            # プロンプトデータの準備
            prompt_input = {
                "user_request": user_request,
                "task_profile_type": task_profile_type,
                "detected_targets": str(detected_targets) if detected_targets else "なし",
                "detected_files": str(detected_files) if detected_files else "なし", 
                "task_analysis_focus": self._get_taskprofile_analysis_focus(task_profile_type)
            }
            
            # プロンプト生成
            formatted_prompt = prompt.format(**prompt_input)
            
            # LLM実行
            response = self.fast_llm.chat(
                formatted_prompt,
                system_prompt=f"あなたは{task_profile_type}タスクの専門家です。ユーザー要求を深く分析し、指定された構造化形式で最適なコンテンツ計画を立案してください。"
            )
            
            print(f"[PYDANTIC] LLMレスポンス受信: {len(response)}文字")
            
            # PydanticOutputParserで解析
            try:
                parsed_plan: ContentPlan = parser.parse(response)
                print(f"[PYDANTIC] 構造化出力成功: {parsed_plan.summary}")
                
                # 検出ファイルを優先して設定（必須）- デバッグログ付き
                primary_files = detected_files or detected_targets or []
                print(f"[PYDANTIC_DEBUG] detected_files: {detected_files}")
                print(f"[PYDANTIC_DEBUG] detected_targets: {detected_targets}")
                print(f"[PYDANTIC_DEBUG] primary_files: {primary_files}")
                print(f"[PYDANTIC_DEBUG] parsed_plan.expected_files (LLM出力): {parsed_plan.expected_files}")
                
                # LLMが設定したexpected_filesをチェック
                if parsed_plan.expected_files:
                    # 有効なファイル（実在するファイル）のみを保持
                    valid_files = []
                    for file_path in parsed_plan.expected_files:
                        print(f"[PYDANTIC_DEBUG] LLMファイル検証: '{file_path}' -> {isinstance(file_path, str)} / {file_path.strip() if isinstance(file_path, str) else 'N/A'}")
                        if (isinstance(file_path, str) and 
                            file_path.strip() and
                            ('/' in file_path or '\\' in file_path or '.' in file_path)):
                            valid_files.append(file_path)
                            print(f"[PYDANTIC_DEBUG] 有効ファイル追加: '{file_path}'")
                    
                    print(f"[PYDANTIC_DEBUG] 有効ファイル一覧: {valid_files}")
                    
                    # 有効なファイルがある場合は検出ファイルと結合
                    if valid_files:
                        # 重複を除去しつつ検出ファイルを優先
                        combined_files = list(dict.fromkeys(primary_files + valid_files))
                        print(f"[PYDANTIC_DEBUG] 結合ファイル: primary({primary_files}) + valid({valid_files}) = {combined_files}")
                        parsed_plan.expected_files = combined_files
                    else:
                        print(f"[PYDANTIC_DEBUG] 有効ファイル無し、primary_filesを使用: {primary_files}")
                        parsed_plan.expected_files = primary_files
                else:
                    # expected_filesが空の場合は検出ファイルを設定
                    print(f"[PYDANTIC_DEBUG] LLMがexpected_files未設定、primary_filesを使用: {primary_files}")
                    parsed_plan.expected_files = primary_files
                
                print(f"[PYDANTIC] 最終ファイルリスト: {parsed_plan.expected_files}")
                
                # 重要：ターゲットファイルが含まれているか最終確認
                if primary_files:
                    target_found = any(target in str(parsed_plan.expected_files) for target in primary_files)
                    print(f"[PYDANTIC_CRITICAL] ターゲットファイル含有確認: {target_found} (primary: {primary_files})")
                
                # Pydanticモデルを辞書に変換
                return parsed_plan.dict()
                
            except Exception as parse_error:
                print(f"[PYDANTIC] 構造化パースエラー: {parse_error}")
                print(f"[PYDANTIC] レスポンス内容: {response[:500]}...")
                
                # フォールバック: 従来のJSON解析を試行
                return self._fallback_json_parse(response, user_request, task_profile_type, detected_files or detected_targets or [])
                
        except Exception as e:
            print(f"[PYDANTIC] コンテンツ計画生成エラー: {e}")
            return self._create_direct_fallback_plan(user_request, task_profile_type, detected_files or detected_targets or [])
    
    def _fallback_json_parse(self, response: str, user_request: str, task_profile_type: str, detected_files: List[str]) -> Dict[str, Any]:
        """従来のJSON解析フォールバック（PydanticParser失敗時）"""
        try:
            import re
            import json
            
            # 複数のJSON抽出パターンを試行
            json_patterns = [
                r'```json\s*(\{.*?\})\s*```',
                r'```\s*(\{.*?\})\s*```',
                r'(\{.*?\})'
            ]
            
            json_str = None
            for pattern in json_patterns:
                match = re.search(pattern, response, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    break
            
            if not json_str:
                raise json.JSONDecodeError("JSON形式が見つかりません", response, 0)
            
            # JSON文字列のクリーニング
            json_str = json_str.strip()
            json_str = re.sub(r'//.*?(?=\n|$)', '', json_str, flags=re.MULTILINE)
            json_str = re.sub(r'\s*\n\s*', '\n', json_str)
            json_str = json_str.strip()
            
            parsed_plan = json.loads(json_str)
            
            # 必須フィールドの検証
            required_fields = {
                "requirement_analysis": "ユーザー要求の分析",
                "summary": "タスクの概要",
                "steps": ["情報収集", "分析", "応答生成"],
                "required_tools": ["read_file"],
                "expected_files": detected_files,
                "complexity": "medium",
                "success_criteria": "タスク完了"
            }
            
            for field, default in required_fields.items():
                if field not in parsed_plan or not parsed_plan[field]:
                    parsed_plan[field] = default
            
            print(f"[FALLBACK] JSON解析成功: {parsed_plan.get('summary', 'N/A')}")
            return parsed_plan
            
        except Exception as e:
            print(f"[FALLBACK] JSON解析も失敗: {e}")
            return self._create_direct_fallback_plan(user_request, task_profile_type, detected_files)
    
    def _create_direct_fallback_plan(self, user_request: str, task_profile_type: str, detected_files: List[str]) -> Dict[str, Any]:
        """TaskProfile特化の直接フォールバック計画"""
        
        if task_profile_type == "search_request":
            return {
                "requirement_analysis": f"ユーザーは「{user_request}」で特定のファイルまたは要素の検索・説明を求めています",
                "summary": "対象ファイルの位置特定と詳細な内容説明",
                "steps": [
                    "対象ファイルの読み取り",
                    "コード構造の分析",
                    "機能と使用方法の整理",
                    "分かりやすい説明文の作成"
                ],
                "required_tools": ["read_file", "llm_analysis"],
                "expected_files": detected_files,
                "complexity": "medium",
                "success_criteria": "対象の位置・機能・使用方法を明確に説明",
                "risks": ["ファイル読み取りエラー"],
                "information_needs": ["ファイル内容", "依存関係"],
                "content_structure": {
                    "primary_sections": ["ファイル概要", "詳細分析", "使用方法"],
                    "data_priorities": ["コード内容", "機能説明"],
                    "presentation_style": "user_friendly"
                },
                "confidence": 0.85
            }
        else:
            # 他のTaskProfile用のフォールバック
            return {
                "requirement_analysis": f"ユーザーは「{user_request}」の{task_profile_type}を求めています",
                "summary": f"{task_profile_type}タスクの実行",
                "steps": ["要求分析", "データ収集", "処理実行", "結果提供"],
                "required_tools": ["read_file"],
                "expected_files": detected_files,
                "complexity": "medium",
                "success_criteria": f"{task_profile_type}の適切な実行",
                "risks": ["処理エラーの可能性"],
                "information_needs": ["基本データ"],
                "content_structure": {
                    "primary_sections": ["概要", "詳細"],
                    "data_priorities": ["主要データ"],
                    "presentation_style": "user_friendly"
                },
                "confidence": 0.7
            }
    
    def _get_taskprofile_analysis_focus(self, task_profile_type: str) -> str:
        """TaskProfile別の分析重点を取得"""
        focus_map = {
            "information_request": """
- 対象の基本情報（メタデータ、構造、目的）
- 詳細内容（実装、設定、データ）
- 関連要素（依存関係、使用箇所）
- 使用例・実行方法""",
            
            "analysis_request": """
- 現状評価（品質、パフォーマンス、設計）
- 問題・課題の特定（バグ、ボトルネック、リスク）
- 改善提案（最適化、リファクタリング、セキュリティ）
- 優先度・影響度の評価""",
            
            "creation_request": """
- 作成方針・アプローチの決定
- 実装詳細・技術選択
- リスク・制約の考慮
- テスト・検証計画""",
            
            "modification_request": """
- 変更対象・影響範囲の特定
- 変更詳細・実装方法
- 互換性・副作用の分析
- バックアップ・安全対策""",
            
            "search_request": """
- 検索対象・条件の明確化
- 発見ファイル・コードの整理
- 関連性・重要度の評価
- 検索結果の統計・サマリー""",
            
            "guidance_request": """
- 前提条件・環境要件
- 段階的手順・操作方法
- トラブルシューティング情報
- ベストプラクティス・注意点"""
        }
        
        return focus_map.get(task_profile_type, "一般的な分析項目")
    
    def _create_fallback_content_plan(self, user_request: str, task_profile_type: str, detected_targets: List[str]) -> Dict[str, Any]:
        """コンテンツ計画生成失敗時のフォールバック"""
        
        # TaskProfile別のフォールバック計画
        if task_profile_type == "information_request":
            return {
                "requirement_analysis": f"'{user_request}'の情報要求を分析中",
                "summary": f"対象の詳細情報を収集・整理して提供",
                "steps": ["対象ファイル読み取り", "メタデータ分析", "内容要約", "関連情報収集"],
                "required_tools": ["read_file"],
                "expected_files": detected_targets or [],
                "complexity": "medium",
                "success_criteria": "対象の詳細情報を正確に提供",
                "risks": ["ファイル読み取りエラーの可能性"],
                "information_needs": ["ファイル内容", "メタデータ"],
                "content_structure": {
                    "primary_sections": ["基本情報", "詳細内容", "関連要素"],
                    "data_priorities": ["ファイル内容", "メタデータ"],
                    "presentation_style": "user_friendly"
                },
                "confidence": 0.7
            }
        else:
            return {
                "requirement_analysis": f"'{user_request}'の{task_profile_type}要求を分析中",
                "summary": f"{task_profile_type}タスクの実行計画",
                "steps": ["要求分析", "データ収集", "処理実行", "結果整理"],
                "required_tools": ["read_file"],
                "expected_files": detected_targets or [],
                "complexity": "medium", 
                "success_criteria": f"{task_profile_type}要求の適切な処理",
                "risks": ["処理中のエラーの可能性"],
                "information_needs": ["基本データ"],
                "content_structure": {
                    "primary_sections": ["分析結果", "詳細情報"],
                    "data_priorities": ["主要データ"],
                    "presentation_style": "technical"
                },
                "confidence": 0.6
            }
    
    def plan_task_execution(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        タスク実行計画の立案（理解・計画ノード用）
        
        Args:
            request: 実行計画要求（user_request, detected_files, operation_type等）
            
        Returns:
            実行計画の辞書 or None
        """
        try:
            user_request = request.get("user_request", "")
            detected_files = request.get("detected_files", [])
            operation_type = request.get("operation_type", "chat")
            needs_file_access = request.get("needs_file_access", False)
            context_info = request.get("context", {})
            
            # 読み取り専用操作かどうかを判定
            is_read_only_request = any(keyword in user_request.lower() for keyword in [
                '説明', '確認', '内容', '分析', '調べ', '見て', '読み', 'について', 'とは', 'どんな'
            ])
            
            # 専用プロンプトを構築
            read_only_instruction = """
**重要: この要求は読み取り専用操作です**
- ファイルの変更・作成・削除は行いません
- 既存ファイルの内容を読み取り、分析・説明のみを行います
- required_toolsには読み取り専用ツール（read_file, list_files, get_file_info, llm_analysis）のみを含めてください
""" if is_read_only_request else ""
            
            planning_prompt = f"""
ユーザーの要求を分析し、実行計画を立案してください。

**ユーザー要求:** {user_request}
{read_only_instruction}
**検出された情報:**
- 対象ファイル: {detected_files if detected_files else "なし"}  
- 操作種別: {operation_type}
- ファイルアクセス: {"必要" if needs_file_access else "不要"}

**分析すべき項目:**
1. **要求の本質**: ユーザーが真に求めていること
2. **実行ステップ**: 具体的な処理手順
3. **必要ツール**: 使用すべきツール群（読み取り専用の場合: read_file, llm_analysis等のみ）
4. **複雑度**: low/medium/high
5. **成功基準**: 何をもって成功とするか

**利用可能ツール:**
- 読み取り専用: read_file, list_files, get_file_info, llm_analysis
- 書き込み系: write_file, create_directory（ファイル変更が必要な場合のみ）

以下のJSON形式で応答してください：
```json
{{
    "requirement_analysis": "要求分析結果",
    "summary": "実行計画の概要",  
    "steps": ["ステップ1", "ステップ2", ...],
    "required_tools": ["tool1", "tool2", ...],
    "expected_files": ["file1", "file2", ...],
    "complexity": "medium",
    "success_criteria": "成功基準",
    "risks": ["リスク1", "リスク2"],
    "information_needs": ["必要情報1", "必要情報2"],
    "confidence": 0.8
}}
```
"""
            
            response = self.fast_llm.chat(
                planning_prompt,
                system_prompt="あなたはタスク分析・実行計画の専門家です。ユーザー要求を正確に理解し、適切な実行計画を立案してください。JSON形式で回答する必要があります。"
            )
            
            # JSONパースを試行
            try:
                import re
                # JSON部分を抽出
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    # JSON形式が見つからない場合、全体をJSONとして試行
                    json_str = response.strip()
                
                execution_plan = json.loads(json_str)
                return execution_plan
                
            except (json.JSONDecodeError, AttributeError) as e:
                # JSONパースに失敗した場合、基本的な計画を作成
                return self._create_basic_plan_from_request(request, response)
            
        except Exception as e:
            print(f"plan_task_execution error: {e}")
            return None
    
    def _create_basic_plan_from_request(self, request: Dict[str, Any], llm_response: str) -> Dict[str, Any]:
        """リクエストから基本的な実行計画を作成"""
        user_request = request.get("user_request", "")
        detected_files = request.get("detected_files", [])
        needs_file_access = request.get("needs_file_access", False)
        
        # 説明・分析系のキーワードを検出
        requires_analysis = any(keyword in user_request.lower() for keyword in 
            ['説明', 'explain', 'describe', '分析', 'analyze', '処理内容', 'summary'])
        
        if requires_analysis and detected_files:
            return {
                "requirement_analysis": f"ファイル {detected_files[0]} の処理内容を分析・説明する",
                "summary": f"ファイル内容の読み取りと詳細分析",
                "steps": [
                    f"ファイル読み取り: {detected_files[0]}",
                    "ファイル内容の分析",
                    "処理内容の説明生成",
                    "ユーザーへの回答"
                ],
                "required_tools": ["read_file", "llm_analysis"],
                "expected_files": detected_files,
                "complexity": "medium",
                "success_criteria": "ファイルの処理内容が明確に説明されている",
                "risks": ["ファイル読み取りエラー"],
                "information_needs": ["ファイル内容"],
                "confidence": 0.8
            }
        else:
            return {
                "requirement_analysis": llm_response[:200] if llm_response else "基本的なタスク処理",
                "summary": "ユーザー要求への対応",
                "steps": ["要求の処理", "結果の提供"],
                "required_tools": ["read_file"] if needs_file_access else [],
                "expected_files": detected_files,
                "complexity": "low",
                "success_criteria": "ユーザー要求の満足",
                "risks": [],
                "information_needs": [],
                "confidence": 0.6
            }
    
    def plan_continuation_execution(self, user_request: str, 
                                   previous_attempts: List[Dict[str, Any]],
                                   missing_info: MissingInfoAnalysis) -> Dict[str, Any]:
        """
        継続実行計画の立案
        
        Args:
            user_request: 元のユーザー要求
            previous_attempts: 過去の試行結果
            missing_info: 不足情報分析
            
        Returns:
            改良された実行計画
        """
        try:
            continuation_prompt = self._build_continuation_planning_prompt(
                user_request, previous_attempts, missing_info
            )
            
            response = self.creative_llm.chat(continuation_prompt, 
                                            system_prompt=self._get_continuation_planning_system_prompt())
            
            plan = self._parse_execution_plan(response)
            plan["strategy"] = "continuation"
            plan["improvements"] = missing_info.suggested_actions
            
            return plan
            
        except Exception as e:
            return self._create_fallback_plan(user_request, str(e))
    
    # === 評価サービス ===
    
    def evaluate_task_satisfaction(self, original_request: str, 
                                 accumulated_results: Dict[str, Any],
                                 operation_type: str = "chat") -> SatisfactionEvaluation:
        """
        ユーザー要求満足度の客観的評価
        
        Args:
            original_request: 元のユーザー要求
            accumulated_results: 蓄積された実行結果
            operation_type: タスク種別（拡張版）
            
        Returns:
            満足度評価結果
        """
        try:
            print(f"[SATISFACTION_DEBUG] 評価開始")
            print(f"[SATISFACTION_DEBUG] 元要求: {original_request}")
            print(f"[SATISFACTION_DEBUG] 蓄積結果キー: {list(accumulated_results.keys())}")
            
            # 蓄積結果の詳細確認（ファイル読み取り結果があるか？）- エラーハンドリング強化版
            try:
                if 'gathered_info' in accumulated_results:
                    gathered = accumulated_results['gathered_info']
                    print(f"[SATISFACTION_DEBUG] gathered_info type: {type(gathered)}")
                    print(f"[SATISFACTION_DEBUG] gathered_info keys: {list(gathered.keys()) if isinstance(gathered, dict) else 'N/A'}")
                    
                    # 新形式: 直接collected_files をまずチェック
                    if isinstance(gathered, dict) and 'collected_files' in gathered:
                        collected_files = gathered['collected_files']
                        print(f"[SATISFACTION_DEBUG] 直接collected_files発見")
                        print(f"[SATISFACTION_DEBUG] 収集ファイル数: {len(collected_files)}")
                        print(f"[SATISFACTION_DEBUG] 収集ファイル: {list(collected_files.keys())}")
                        
                        # ターゲットファイルの内容チェック
                        target_found = any('test_step2d_graph' in str(path) for path in collected_files.keys())
                        print(f"[SATISFACTION_CRITICAL] ターゲットファイル収集確認: {target_found}")
                        
                        if target_found:
                            target_file = next((path for path in collected_files.keys() if 'test_step2d_graph' in str(path)), None)
                            print(f"[SATISFACTION_DEBUG] ターゲットファイル特定: {target_file}")
                            
                            if target_file and isinstance(collected_files[target_file], dict):
                                file_info = collected_files[target_file]
                                print(f"[SATISFACTION_DEBUG] ターゲットファイル情報keys: {list(file_info.keys())}")
                                
                                if 'content' in file_info:
                                    content_length = len(file_info['content'])
                                    print(f"[SATISFACTION_DEBUG] ターゲットファイル内容長: {content_length}文字")
                                    print(f"[SATISFACTION_DEBUG] ターゲットファイル内容サンプル: {file_info['content'][:100]}...")
                                else:
                                    print(f"[SATISFACTION_DEBUG] ターゲットファイルにcontentなし")
                            else:
                                print(f"[SATISFACTION_DEBUG] ターゲットファイル情報type: {type(collected_files[target_file]) if target_file else 'None'}")
                                
                    # gathered_info_detailed形式
                    elif isinstance(gathered, dict) and 'gathered_info_detailed' in gathered:
                        detailed = gathered['gathered_info_detailed']
                        print(f"[SATISFACTION_DEBUG] gathered_info_detailed keys: {list(detailed.keys())}")
                        
                        if 'collected_files' in detailed:
                            collected_files = detailed['collected_files']
                            print(f"[SATISFACTION_DEBUG] 収集ファイル数: {len(collected_files)}")
                            print(f"[SATISFACTION_DEBUG] 収集ファイル: {list(collected_files.keys())}")
                            
                            # ターゲットファイルの内容チェック
                            target_found = any('test_step2d_graph' in str(path) for path in collected_files.keys())
                            print(f"[SATISFACTION_CRITICAL] ターゲットファイル収集確認: {target_found}")
                            
                            if target_found:
                                target_file = next((path for path in collected_files.keys() if 'test_step2d_graph' in str(path)), None)
                                if target_file and isinstance(collected_files[target_file], dict) and 'content' in collected_files[target_file]:
                                    content_length = len(collected_files[target_file]['content'])
                                    print(f"[SATISFACTION_DEBUG] ターゲットファイル内容長: {content_length}文字")
                                else:
                                    print(f"[SATISFACTION_DEBUG] ターゲットファイル情報: {collected_files[target_file] if target_file else 'None'}")
                        else:
                            print(f"[SATISFACTION_DEBUG] gathered_info_detailedにcollected_filesなし")
                    # 旧形式: 直接collected_files
                    elif hasattr(gathered, 'collected_files'):
                        print(f"[SATISFACTION_DEBUG] 旧形式collected_files検出")
                        print(f"[SATISFACTION_DEBUG] 収集ファイル数: {len(gathered.collected_files)}")
                        print(f"[SATISFACTION_DEBUG] 収集ファイル: {list(gathered.collected_files.keys())}")
                        
                        # ターゲットファイルの内容チェック
                        target_found = any('test_step2d_graph' in str(path) for path in gathered.collected_files.keys())
                        print(f"[SATISFACTION_CRITICAL] ターゲットファイル収集確認: {target_found}")
                        
                        if target_found:
                            target_file = next((path for path in gathered.collected_files.keys() if 'test_step2d_graph' in str(path)), None)
                            if target_file:
                                content_length = len(gathered.collected_files[target_file].content) if hasattr(gathered.collected_files[target_file], 'content') else 0
                                print(f"[SATISFACTION_DEBUG] ターゲットファイル内容長: {content_length}文字")
                    else:
                        print(f"[SATISFACTION_DEBUG] 認識できる形式のcollected_filesなし")
                else:
                    print(f"[SATISFACTION_DEBUG] accumulated_resultsにgathered_infoなし")
            except Exception as debug_error:
                print(f"[SATISFACTION_DEBUG_ERROR] 詳細確認エラー: {debug_error}")
                print(f"[SATISFACTION_DEBUG_ERROR] accumulated_results: {accumulated_results}")
            
            evaluation_prompt = self._build_satisfaction_evaluation_prompt(
                original_request, accumulated_results, operation_type
            )
            
            response = self.evaluator_llm.chat(evaluation_prompt, 
                                             system_prompt=self._get_evaluation_system_prompt())
            
            print(f"[SATISFACTION_DEBUG] LLM評価レスポンス長: {len(response)}文字")
            
            result = self._parse_satisfaction_evaluation(response)
            print(f"[SATISFACTION_DEBUG] 評価結果 - スコア: {result.overall_score:.2f}, 完了推奨: {result.completion_recommendation}")
            print(f"[SATISFACTION_DEBUG] 不足要素: {result.missing_aspects}")
            
            return result
            
        except Exception as e:
            print(f"[SATISFACTION_ERROR] 評価エラー: {e}")
            return SatisfactionEvaluation(
                overall_score=0.3,
                requirement_scores={},
                missing_aspects=[f"評価エラー: {str(e)}"],
                quality_assessment="評価実行中にエラーが発生しました",
                completion_recommendation=False
            )
    
    def extract_missing_information(self, original_request: str,
                                   current_results: Dict[str, Any]) -> MissingInfoAnalysis:
        """
        不足情報の特定と優先順位付け
        
        Args:
            original_request: 元のユーザー要求
            current_results: 現在の結果
            
        Returns:
            不足情報分析結果
        """
        try:
            analysis_prompt = self._build_missing_info_prompt(original_request, current_results)
            
            response = self.fast_llm.chat(analysis_prompt, 
                                        system_prompt=self._get_analysis_system_prompt())
            
            return self._parse_missing_info_analysis(response)
            
        except Exception as e:
            return MissingInfoAnalysis(
                missing_items=[f"分析エラー: {str(e)}"],
                priority_order=[],
                suggested_actions=["エラーを解決してから再実行"],
                constraints=["評価実行の技術的問題"],
                alternative_approaches=["手動での情報提供を検討"]
            )
    
    def extract_task_requirements(self, user_request: str) -> List[RequirementItem]:
        """
        ユーザー要求からの要件抽出
        
        Args:
            user_request: ユーザー要求
            
        Returns:
            要件項目のリスト
        """
        try:
            extraction_prompt = self._build_requirement_extraction_prompt(user_request)
            
            response = self.fast_llm.chat(extraction_prompt, 
                                        system_prompt=self._get_extraction_system_prompt())
            
            return self._parse_requirement_items(response)
            
        except Exception as e:
            return [RequirementItem(
                requirement=f"要件抽出エラー: {str(e)}",
                satisfaction_level=0.0,
                priority=1
            )]
    
    # === プロンプト構築メソッド ===
    
    def _build_initial_planning_prompt(self, user_request: str, context: TaskContext) -> str:
        """初回計画立案プロンプトの構築"""
        return f"""
ユーザー要求の分析と実行計画の立案をお願いします。

**ユーザー要求:**
{user_request}

**利用可能なコンテキスト:**
- ワークスペース情報: {context.workspace_info is not None}
- 利用可能ツール: {len(context.available_tools)}個

**求められる出力:**
1. 要求の理解・分析
2. 具体的な実行手順
3. 必要なツールとファイル
4. 成功の判定基準
5. 想定される課題と対策

JSON形式で構造化して回答してください。
"""
    
    def _build_continuation_planning_prompt(self, user_request: str, 
                                          previous_attempts: List[Dict[str, Any]],
                                          missing_info: MissingInfoAnalysis) -> str:
        """継続計画立案プロンプトの構築"""
        return f"""
過去の試行結果を踏まえた改良計画の立案をお願いします。

**元のユーザー要求:**
{user_request}

**過去の試行状況:**
- 実行回数: {len(previous_attempts)}回
- 主な問題: {', '.join(missing_info.missing_items[:3])}

**特定された不足情報:**
{chr(10).join([f"- {item}" for item in missing_info.missing_items])}

**推奨される改善アクション:**
{chr(10).join([f"- {action}" for action in missing_info.suggested_actions])}

**求められる出力:**
1. 前回の問題点分析
2. 改良された実行戦略
3. 新たに試す具体的手順
4. 回避すべき失敗パターン
5. 成功確率向上のための工夫

前回と同じ失敗を繰り返さない、より確実な計画を立案してください。
"""
    
    def _build_satisfaction_evaluation_prompt(self, original_request: str, 
                                            accumulated_results: Dict[str, Any],
                                            operation_type: str = "chat") -> str:
        """満足度評価プロンプトの構築（タスク種別対応）"""
        
        results_summary = self._summarize_results(accumulated_results)
        
        # 基本評価観点
        base_evaluation = """**評価観点:**
1. 要求された情報が十分に提供されているか？
2. 回答の品質と詳細度は適切か？
3. ユーザーが求めていた具体的な内容が含まれているか？
4. 追加で必要な情報は何か？"""

        # タスク種別に応じた評価観点の追加
        task_specific_guidance = self._get_task_specific_evaluation_guidance(operation_type)
        
        return f"""
ユーザー要求の満足度を客観的に評価してください。

**元のユーザー要求:**
{original_request}

**蓄積された実行結果:**
{results_summary}

**タスク種別:** {self._get_operation_type_description(operation_type)}

{base_evaluation}

{task_specific_guidance}

**出力形式:**
- overall_score: 0.0-1.0の数値
- missing_aspects: 不足している側面のリスト
- quality_assessment: 品質評価コメント
- completion_recommendation: 完了推奨の真偽値

JSON形式で構造化して評価してください。
"""
    
    # === システムプロンプト ===
    
    def _get_planning_system_prompt(self) -> str:
        """計画立案用システムプロンプト"""
        return """あなたは優秀なタスク計画立案AIです。
ユーザー要求を正確に理解し、実行可能で具体的な計画を立案してください。
特に以下の点を重視してください:

1. 要求の核心を正確に把握する
2. 実行可能な具体的手順を提示する
3. 必要なリソースを明確にする
4. 成功の判定基準を定義する
5. 想定リスクと対策を含める

回答は必ずJSON形式で構造化してください。"""
    
    def _get_evaluation_system_prompt(self) -> str:
        """評価用システムプロンプト"""
        return """あなたは公平で客観的な評価専門AIです。
ユーザー要求がどの程度満たされているかを数値的に評価してください。

評価基準:
- 0.8以上: 要求が十分満たされている（完了推奨）
- 0.5-0.7: 部分的に満たされているが改善余地あり
- 0.5未満: 要求が十分に満たされていない

感情や主観を排除し、事実に基づいた評価を行ってください。
タスクの性質を十分に考慮し、適切な完了基準で判定してください。"""
    
    def _get_operation_type_description(self, operation_type: str) -> str:
        """タスク種別の説明を取得"""
        descriptions = {
            "information_search": "情報検索・参照（ファイル読み取り、調査、確認）",
            "code_generation": "コード生成・編集（ファイル作成、修正、実装）",
            "analysis_report": "分析・レポート（分析、要約、レポート生成）",
            "command_execution": "コマンド実行（テスト実行、ビルド、デプロイ）",
            "chat": "対話（質問回答、説明、議論）"
        }
        return descriptions.get(operation_type, "対話")
    
    def _get_task_specific_evaluation_guidance(self, operation_type: str) -> str:
        """タスク種別に応じた評価ガイダンス"""
        
        if operation_type == "information_search":
            return """
**情報検索・参照タスクの特別な評価観点:**
- ファイルの内容が正常に読み取られ、表示されているか
- ユーザーが「参照してください」と言った場合、ファイル内容の表示自体が主目的
- 内容の詳細分析は明示的に求められていない限り二次的な要求
- 調査対象が適切に特定され、必要な情報が取得できているか"""
            
        elif operation_type == "code_generation":
            return """
**コード生成・編集タスクの特別な評価観点:**
- 実際にファイルが作成・修正されているか
- 生成されたコードが要求仕様を満たしているか
- コードの品質（構文、スタイル、保守性）が適切か
- エラーハンドリングや安全性が考慮されているか"""
            
        elif operation_type == "analysis_report":
            return """
**分析・レポートタスクの特別な評価観点:**
- 分析対象が適切に特定され、包括的に検討されているか
- 分析結果が論理的で根拠が明確か
- レポート形式が読みやすく構造化されているか
- 結論や推奨事項が明確に示されているか"""
            
        elif operation_type == "command_execution":
            return """
**コマンド実行タスクの特別な評価観点:**
- 実際にコマンドが安全に実行されているか
- 実行結果が適切に取得・表示されているか
- エラーが発生した場合の対処が適切か
- 実行環境や依存関係が考慮されているか"""
            
        else:  # chat
            return """
**対話タスクの特別な評価観点:**
- 質問に対して適切で有用な回答が提供されているか
- 説明が分かりやすく、必要な詳細度で記述されているか
- 関連する補足情報や注意点が適切に含まれているか"""
    
    # === パーサーメソッド ===
    
    def _parse_execution_plan(self, response: str) -> Dict[str, Any]:
        """実行計画のパース（簡略版）"""
        try:
            # JSONパースを試行
            if '{' in response and '}' in response:
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                json_str = response[json_start:json_end]
                return json.loads(json_str)
        except:
            pass
        
        # フォールバック: 基本構造を返す
        return {
            "summary": response[:200] + "..." if len(response) > 200 else response,
            "steps": ["解析されたレスポンスに基づく実行"],
            "required_tools": ["read_file", "list_files"],
            "expected_files": [],
            "estimated_complexity": "medium"
        }
    
    def _parse_satisfaction_evaluation(self, response: str) -> SatisfactionEvaluation:
        """満足度評価のパース（簡略版）"""
        try:
            if '{' in response and '}' in response:
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                return SatisfactionEvaluation(
                    overall_score=float(data.get('overall_score', 0.5)),
                    requirement_scores=data.get('requirement_scores', {}),
                    missing_aspects=data.get('missing_aspects', []),
                    quality_assessment=data.get('quality_assessment', '評価完了'),
                    completion_recommendation=bool(data.get('completion_recommendation', False))
                )
        except:
            pass
        
        # フォールバック評価
        score = 0.7 if "完了" in response or "満足" in response else 0.4
        return SatisfactionEvaluation(
            overall_score=score,
            requirement_scores={},
            missing_aspects=["詳細分析が必要"],
            quality_assessment=response[:100] + "..." if len(response) > 100 else response,
            completion_recommendation=score >= 0.8
        )
    
    # === ユーティリティメソッド ===
    
    def _summarize_results(self, results: Dict[str, Any]) -> str:
        """結果の要約生成（ファイル内容を重視）"""
        if not results:
            return "結果なし"
        
        summary_parts = []
        
        # ファイル情報を優先的に抽出・表示
        if 'gathered_info' in results:
            gathered = results['gathered_info']
            
            # 直接collected_files形式（修正版）
            if isinstance(gathered, dict) and 'collected_files' in gathered:
                collected_files = gathered['collected_files']
                summary_parts.append(f"**収集されたファイル情報** ({len(collected_files)}件):")
                
                for file_path, file_info in collected_files.items():
                    if isinstance(file_info, dict) and 'content' in file_info:
                        content = file_info['content']
                        # ターゲットファイルは詳細表示、その他は概要のみ
                        if 'test_step2d_graph' in file_path:
                            summary_parts.append(f"  ● **{file_path}** ({len(content)}文字):")
                            summary_parts.append(f"```python\n{content[:5000]}{'...[残り' + str(len(content) - 5000) + '文字省略]' if len(content) > 5000 else ''}\n```")
                        else:
                            summary_parts.append(f"  ● {file_path}: {len(content)}文字")
                    else:
                        summary_parts.append(f"  ● {file_path}: {file_info}")
            
            # 旧形式: gathered_info_detailed
            elif isinstance(gathered, dict) and 'gathered_info_detailed' in gathered:
                detailed = gathered['gathered_info_detailed']
                if 'collected_files' in detailed:
                    collected_files = detailed['collected_files']
                    summary_parts.append(f"**収集されたファイル情報** ({len(collected_files)}件):")
                    
                    for file_path, file_info in collected_files.items():
                        if isinstance(file_info, dict) and 'content' in file_info:
                            content = file_info['content']
                            # ターゲットファイルは詳細表示、その他は概要のみ
                            if 'test_step2d_graph' in file_path:
                                summary_parts.append(f"  ● **{file_path}** ({len(content)}文字):")
                                summary_parts.append(f"```python\n{content[:5000]}{'...[残り' + str(len(content) - 5000) + '文字省略]' if len(content) > 5000 else ''}\n```")
                            else:
                                summary_parts.append(f"  ● {file_path}: {len(content)}文字")
                        else:
                            summary_parts.append(f"  ● {file_path}: {file_info}")
        
        # その他の結果情報
        for key, value in results.items():
            if key != 'gathered_info':  # ファイル情報は既に処理済み
                if isinstance(value, str):
                    preview = value[:200] + "..." if len(value) > 200 else value
                else:
                    preview = str(value)[:200]
                summary_parts.append(f"- {key}: {preview}")
        
        return "\n".join(summary_parts)
    
    def _create_fallback_plan(self, user_request: str, error: str) -> Dict[str, Any]:
        """フォールバック計画の生成"""
        return {
            "summary": f"基本計画: {user_request[:100]}",
            "steps": [
                "ユーザー要求の分析",
                "関連情報の収集",
                "結果の整理と回答"
            ],
            "required_tools": ["read_file", "list_files"],
            "expected_files": [],
            "estimated_complexity": "low",
            "fallback_reason": error
        }
    
    # === 未実装メソッドのスタブ ===
    
    def _build_missing_info_prompt(self, original_request: str, current_results: Dict[str, Any]) -> str:
        return f"不足情報を分析: {original_request}, 結果: {len(current_results)}件"
    
    def _parse_missing_info_analysis(self, response: str) -> MissingInfoAnalysis:
        return MissingInfoAnalysis(
            missing_items=["詳細分析が必要"],
            priority_order=["優先度分析"],
            suggested_actions=["追加情報収集"],
            constraints=["制約分析"],
            alternative_approaches=["代替アプローチ検討"]
        )
    
    def _build_requirement_extraction_prompt(self, user_request: str) -> str:
        return f"要件抽出: {user_request}"
    
    def _parse_requirement_items(self, response: str) -> List[RequirementItem]:
        return [RequirementItem(
            requirement="基本要件",
            satisfaction_level=0.0,
            priority=1
        )]
    
    def _get_continuation_planning_system_prompt(self) -> str:
        return self._get_planning_system_prompt()
    
    def _get_analysis_system_prompt(self) -> str:
        return "分析専門AIとして客観的な分析を行ってください。"
    
    def _get_extraction_system_prompt(self) -> str:
        return "要件抽出専門AIとして、ユーザー要求から具体的要件を抽出してください。"
    
    # === Phase 1: 知的ファイル探索機能 ===
    
    def prioritize_files_for_task(self, task_description: str, file_list: List[str]) -> List[str]:
        """
        タスク説明に基づき、調査すべきファイルの優先順位リストを生成する
        高速モデルを使用して効率的にファイル優先順位付けを実行
        
        Args:
            task_description: ユーザーのタスク説明
            file_list: 対象ファイルのリスト
            
        Returns:
            優先順位付けされたファイルパスのリスト（最大10ファイル）
        """
        try:
            # 特定ファイル名が明示的に指定されている場合の検出
            explicit_files = self._extract_explicit_filenames(task_description, file_list)
            
            # ファイルリストが多すぎる場合は重要そうなものを事前フィルタリング
            filtered_files = self._pre_filter_important_files(file_list)
            
            # 明示的に指定されたファイルを最優先に設定
            if explicit_files:
                # 明示ファイルを最上位に配置し、残りを一般的な優先順位付けで追加
                remaining_files = [f for f in filtered_files if f not in explicit_files]
                prioritized_files = explicit_files + remaining_files[:10 - len(explicit_files)]
                return prioritized_files[:10]
            else:
                # 明示ファイルが見つからない場合の拡張探索
                extended_files = self._extended_file_search(task_description, file_list)
                if extended_files:
                    remaining_files = [f for f in filtered_files if f not in extended_files]
                    prioritized_files = extended_files + remaining_files[:10 - len(extended_files)]
                    return prioritized_files[:10]
            
            # ファイル優先順位付けプロンプトの構築
            prioritization_prompt = self._build_file_prioritization_prompt(
                task_description, filtered_files[:100]  # 最大100ファイルに制限
            )
            
            # 高速LLMで優先順位付けを実行
            response = self.fast_llm.chat(
                prioritization_prompt,
                system_prompt=self._get_file_prioritization_system_prompt()
            )
            
            # レスポンスからファイルリストを抽出
            prioritized_files = self._parse_prioritized_files(response, filtered_files)
            
            return prioritized_files[:10]  # 最大10ファイルを返す
            
        except Exception as e:
            # エラー時はフォールバック戦略を使用
            return self._fallback_file_prioritization(task_description, file_list)
    
    def _pre_filter_important_files(self, file_list: List[str]) -> List[str]:
        """重要そうなファイルを事前フィルタリング"""
        import os
        
        # 重要度スコアリング
        scored_files = []
        for file_path in file_list:
            score = self._calculate_file_importance_score(file_path)
            if score > 0:  # スコア0以下は除外
                scored_files.append((file_path, score))
        
        # スコア順でソート
        scored_files.sort(key=lambda x: x[1], reverse=True)
        
        return [file_path for file_path, _ in scored_files[:200]]  # 上位200ファイル
    
    def _calculate_file_importance_score(self, file_path: str) -> int:
        """ファイルの重要度スコアを計算"""
        import os
        
        score = 0
        filename = os.path.basename(file_path).lower()
        dirname = os.path.dirname(file_path).lower()
        
        # 除外ファイル（スコア0）
        if any(exclude in file_path.lower() for exclude in [
            '__pycache__', '.pyc', '.git', 'node_modules', '.env', 
            'venv', '.vscode', 'dist', 'build'
        ]):
            return 0
        
        # 高スコアファイル
        high_priority_names = [
            'readme', 'main.py', '__init__.py', 'setup.py', 'requirements.txt',
            'config', 'orchestrator', 'manager', 'engine', 'service'
        ]
        for name in high_priority_names:
            if name in filename:
                score += 10
        
        # 中スコアファイル  
        mid_priority_names = [
            'test', 'example', 'demo', 'docs', 'util', 'helper',
            'client', 'api', 'model'
        ]
        for name in mid_priority_names:
            if name in filename:
                score += 5
        
        # ディレクトリによるスコア調整
        important_dirs = ['src', 'lib', 'core', 'main', 'app', 'services']
        for dir_name in important_dirs:
            if dir_name in dirname:
                score += 3
        
        # ファイル拡張子によるスコア
        if file_path.endswith(('.py', '.md', '.yaml', '.yml', '.json')):
            score += 2
        elif file_path.endswith(('.txt', '.cfg', '.ini')):
            score += 1
        
        return score
    
    def _build_file_prioritization_prompt(self, task_description: str, file_list: List[str]) -> str:
        """ファイル優先順位付けプロンプトの構築"""
        
        files_section = "\n".join([f"- {file_path}" for file_path in file_list])
        
        return f"""
ユーザーのタスクを解決するために最も重要なファイルを特定してください。

**ユーザーのタスク:**
{task_description}

**利用可能なファイル一覧:**
{files_section}

**選択基準:**
1. README、設計ドキュメント、プログレス文書を最優先
2. メインエントリーポイント（main.py、__init__.py等）
3. 中核的な実装ファイル（orchestrator、engine、service等）
4. テストファイル（実行例として有用）
5. 設定ファイル（構成理解に重要）

**出力形式:**
最も重要だと思われる10個のファイルパスを、重要度の高い順に1行ずつリストしてください。
ファイルパスのみを出力し、説明や番号は不要です。
"""
    
    def _get_file_prioritization_system_prompt(self) -> str:
        """ファイル優先順位付け用システムプロンプト"""
        return """あなたは経験豊富なソフトウェアアーキテクトです。
プロジェクトのファイル構造を分析し、ユーザーのタスクに最も関連の高いファイルを特定することが得意です。

重要なポイント:
1. ドキュメント系ファイル（README、設計書等）は全体理解に最重要
2. エントリーポイントファイルはアーキテクチャ理解の鍵
3. テストファイルは実行例・使用方法の理解に有用
4. ファイル名から機能を推測し、タスクとの関連度を判断
5. 無関係なファイル（キャッシュ、設定ファイル等）は避ける

出力は指定されたファイルパスのみとし、余計な説明は付けないでください。"""
    
    def _parse_prioritized_files(self, response: str, original_files: List[str]) -> List[str]:
        """LLMレスポンスから優先順位付きファイルリストを抽出"""
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        
        # レスポンスから有効なファイルパスのみを抽出
        prioritized_files = []
        original_files_set = set(original_files)
        
        for line in lines:
            # 先頭の記号や番号を除去
            clean_line = line.lstrip('- 1234567890. ')
            
            # 元のファイルリストに存在するかチェック
            if clean_line in original_files_set:
                prioritized_files.append(clean_line)
            else:
                # 部分マッチを試行
                for original_file in original_files:
                    if clean_line in original_file or original_file.endswith(clean_line):
                        if original_file not in prioritized_files:
                            prioritized_files.append(original_file)
                        break
        
        return prioritized_files
    
    def _fallback_file_prioritization(self, task_description: str, file_list: List[str]) -> List[str]:
        """LLM呼び出し失敗時のフォールバック戦略"""
        # スコアベースの単純な優先順位付け
        scored_files = []
        for file_path in file_list:
            score = self._calculate_file_importance_score(file_path)
            scored_files.append((file_path, score))
        
        # スコア順でソートして上位10ファイルを返す
        scored_files.sort(key=lambda x: x[1], reverse=True)
        return [file_path for file_path, _ in scored_files[:10]]
    
    # === Phase 2: 統合理解エンジン ===
    
    def synthesize_insights_from_files(self, task_description: str, files_with_content: Dict[str, str]) -> str:
        """
        複数のファイル内容を横断的に分析し、タスクに対する包括的な見解や要約を生成する
        高性能モデル（創造的LLM）を使用して深い洞察を提供
        
        Args:
            task_description: ユーザーの最終的なタスク
            files_with_content: {filepath: content} の辞書
            
        Returns:
            統合分析結果の文字列
        """
        try:
            if not files_with_content:
                return "分析対象ファイルが提供されていません。"
            
            # プロンプトのコンテキスト部分を作成
            context_str = self._build_files_context(files_with_content)
            
            # 統合分析プロンプトの構築
            synthesis_prompt = self._build_synthesis_prompt_v2(task_description, context_str, files_with_content)
            
            # 創造的LLMで統合分析を実行
            response = self.creative_llm.chat(
                synthesis_prompt,
                system_prompt=self._get_synthesis_system_prompt_v2()
            )
            
            return response
            
        except Exception as e:
            return f"統合分析エラー: {str(e)}\n\n利用可能なファイル: {', '.join(files_with_content.keys())}"
    
    def _build_files_context(self, files_with_content: Dict[str, str]) -> str:
        """ファイル内容をコンテキスト文字列に変換"""
        context_parts = []
        
        for file_path, content in files_with_content.items():
            # ファイル内容の要約（長すぎる場合）
            if len(content) > 3000:
                content = self._smart_truncate_file_content(file_path, content)
            
            context_parts.append(f"--- FILE: {file_path} ---\n{content}\n--- END OF {file_path} ---\n")
        
        return "\n".join(context_parts)
    
    def _smart_truncate_file_content(self, file_path: str, content: str) -> str:
        """ファイル内容の賢い切り詰め"""
        lines = content.split('\n')
        
        if file_path.endswith('.md'):
            # Markdownの場合: セクションヘッダーを優先
            important_lines = []
            for line in lines:
                if (line.startswith('#') or len(line.strip()) < 100 or 
                    any(keyword in line.lower() for keyword in ['概要', 'summary', '目的', 'purpose', 'usage'])):
                    important_lines.append(line)
                if len('\n'.join(important_lines)) > 2500:
                    break
            return '\n'.join(important_lines) + '\n\n[... 内容は切り詰められました ...]'
            
        elif file_path.endswith('.py'):
            # Pythonファイルの場合: docstring、クラス・関数定義を優先
            important_lines = []
            in_docstring = False
            
            for line in lines:
                if '"""' in line:
                    in_docstring = not in_docstring
                    important_lines.append(line)
                elif in_docstring or line.strip().startswith(('class ', 'def ', 'async def ', 'import ', 'from ')):
                    important_lines.append(line)
                elif line.strip().startswith('#') and len(line.strip()) < 100:
                    important_lines.append(line)
                    
                if len('\n'.join(important_lines)) > 2500:
                    break
                    
            return '\n'.join(important_lines) + '\n\n[... 実装詳細は切り詰められました ...]'
            
        else:
            # その他のファイル: 単純に先頭部分を取得
            return '\n'.join(lines[:100]) + '\n\n[... 内容は切り詰められました ...]'
    
    def _build_synthesis_prompt_v2(self, task_description: str, context_str: str, files_info: Dict[str, str]) -> str:
        """統合分析用プロンプトの構築（v2）"""
        
        file_list = ', '.join(files_info.keys())
        
        return f"""
あなたはシニアソフトウェアアーキテクト兼システム分析の専門家です。
以下の複数ファイルの内容を横断的に分析し、ユーザーのタスクに対する包括的で実用的な回答を生成してください。

**ユーザーのタスク:**
{task_description}

**分析対象ファイル一覧:**
{file_list}

**ファイル内容:**
{context_str}

**分析指針:**
1. **全体像の把握**: プロジェクトの目的、アーキテクチャ、主要コンポーネントを理解する
2. **関係性の分析**: ファイル間の依存関係、データフロー、相互作用を分析する
3. **具体例の抽出**: 実際の使用方法、実行例、シナリオを特定する
4. **実用的な回答**: ユーザーの質問に直接関連する具体的で実用的な情報を提供する

**回答構成:**
## プロジェクト概要
[プロジェクトの目的と全体像]

## アーキテクチャ・設計
[システム構成と主要コンポーネント]

## ユーザー質問への回答
[「{task_description}」に対する具体的で詳細な回答]

## 使用例・実行方法
[実際の使用方法やシナリオ]

## 関連情報
[さらに調査すべき点や参考情報]

断片的な情報の羅列ではなく、全体を俯瞰した統合的な理解を提供してください。
"""
    
    def _get_synthesis_system_prompt_v2(self) -> str:
        """統合分析用システムプロンプト（v2）"""
        return """あなたは経験豊富なシニアソフトウェアアーキテクトです。
複数の断片的なファイル情報から、システム全体の包括的理解を構築することが得意です。

重要な能力:
1. **統合的思考**: 個別情報を統合して全体像を構築
2. **実用的分析**: 技術的詳細と実用的価値のバランス  
3. **文脈理解**: ファイル間の関係性と依存関係の把握
4. **具体性**: 抽象的でなく具体的で実行可能な情報提供
5. **明確性**: 複雑な内容をわかりやすく構造化

回答指針:
- ファイルの内容を単純に要約するのではなく、全体像を統合的に分析
- ユーザーの質問に直接関連する部分を重点的に説明
- 技術者が実際に活用できる具体的で実用的な情報を提供
- 不明な点は推測せず「不明」と明記
- Markdown形式で構造化された読みやすい回答を作成"""
    
    # === 統合理解サービス（既存のメソッドを統合） ===
    
    def synthesize_system_understanding(self, user_query: str, 
                                      collected_files: Dict[str, str],
                                      context_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        複数ファイル情報を統合してシステム全体理解を生成
        
        Args:
            user_query: ユーザーの質問
            collected_files: {filepath: content} の辞書
            context_info: 追加コンテキスト情報
            
        Returns:
            統合理解結果
        """
        try:
            # ファイル情報を整理
            file_summaries = self._create_file_summaries(collected_files)
            
            # 統合理解プロンプトの構築
            synthesis_prompt = self._build_synthesis_prompt(
                user_query, file_summaries, context_info
            )
            
            # クリエイティブLLMで統合理解を実行
            response = self.creative_llm.chat(
                synthesis_prompt, 
                system_prompt=self._get_synthesis_system_prompt()
            )
            
            return self._parse_synthesis_result(response)
            
        except Exception as e:
            return {
                "system_overview": f"統合理解エラー: {str(e)}",
                "key_components": [],
                "architecture": "不明",
                "scenarios": [],
                "recommendations": ["エラーを解決してから再実行"]
            }
    
    def _create_file_summaries(self, collected_files: Dict[str, str]) -> List[Dict[str, str]]:
        """ファイル内容を要約"""
        summaries = []
        
        for filepath, content in collected_files.items():
            # ファイルタイプ別の要約戦略
            if filepath.endswith('.md'):
                summary = self._summarize_documentation(filepath, content)
            elif filepath.endswith('.py'):
                summary = self._summarize_code_file(filepath, content)
            elif filepath.endswith(('.yaml', '.yml', '.json')):
                summary = self._summarize_config_file(filepath, content)
            else:
                summary = content[:500] + "..." if len(content) > 500 else content
            
            summaries.append({
                "filepath": filepath,
                "type": self._classify_file_type(filepath),
                "summary": summary,
                "importance": self._assess_file_importance(filepath, content)
            })
        
        # 重要度でソート
        summaries.sort(key=lambda x: x["importance"], reverse=True)
        return summaries[:20]  # 最大20ファイル
    
    def _build_synthesis_prompt(self, user_query: str, 
                              file_summaries: List[Dict[str, str]], 
                              context_info: Dict[str, Any] = None) -> str:
        """統合理解プロンプトの構築"""
        
        files_section = "\n".join([
            f"**{summary['filepath']}** ({summary['type']}, 重要度: {summary['importance']})\n{summary['summary']}\n"
            for summary in file_summaries[:10]  # 上位10ファイル
        ])
        
        return f"""
複数ファイルの情報を統合して、ユーザーの質問に包括的に回答してください。

**ユーザーの質問:**
{user_query}

**収集されたファイル情報:**
{files_section}

**求められる出力:**
1. **システム全体概要**: 何をするシステムなのか
2. **主要コンポーネント**: 重要な機能・モジュール
3. **アーキテクチャ**: システムの構成・設計
4. **ユーザー質問への直接回答**: 特に「シナリオ」「使用例」「実行方法」について
5. **関連情報への案内**: さらに調べるべき点

断片的な情報ではなく、全体像を踏まえた統合的な理解を提供してください。
"""
    
    def _get_synthesis_system_prompt(self) -> str:
        """統合理解用システムプロンプト"""
        return """あなたは優秀なシステム分析・統合理解の専門家です。
複数の断片的なファイル情報から、システム全体の包括的理解を構築してください。

重要なポイント:
1. 個別ファイルの内容を羅列するのではなく、全体像を統合的に説明する
2. ユーザーの質問に直接関連する部分を重点的に説明する
3. 技術的詳細と概念的理解のバランスを取る
4. 実際の使用方法やシナリオを具体的に示す
5. 不明な点は素直に「不明」と記載し、推測を避ける

回答は構造化された形で、実用的な情報を提供してください。"""
    
    # === ヘルパーメソッド ===
    
    def _extract_explicit_filenames(self, task_description: str, file_list: List[str]) -> List[str]:
        """タスク説明から明示的に指定されたファイル名を抽出する
        
        Args:
            task_description: タスク説明文
            file_list: 利用可能なファイルリスト
            
        Returns:
            明示的に指定されたファイルのリスト
        """
        import re
        
        explicit_files = []
        task_lower = task_description.lower()
        
        # ファイル拡張子パターンでファイル名を検索
        file_patterns = [
            r'([a-zA-Z0-9_\-]+\.md)',      # .md ファイル
            r'([a-zA-Z0-9_\-]+\.py)',      # .py ファイル
            r'([a-zA-Z0-9_\-]+\.yaml)',    # .yaml ファイル
            r'([a-zA-Z0-9_\-]+\.yml)',     # .yml ファイル
            r'([a-zA-Z0-9_\-]+\.json)',    # .json ファイル
            r'([a-zA-Z0-9_\-]+\.txt)',     # .txt ファイル
            r'([a-zA-Z0-9_\-]+\.cfg)',     # .cfg ファイル
            r'([a-zA-Z0-9_\-]+\.ini)',     # .ini ファイル
        ]
        
        # パターンマッチングでファイル名を抽出
        for pattern in file_patterns:
            matches = re.findall(pattern, task_description, re.IGNORECASE)
            for match in matches:
                # 実際のファイルリストから完全一致または部分一致を探す
                for file_path in file_list:
                    file_name = file_path.split('/')[-1].split('\\')[-1]  # ファイル名のみ抽出
                    if match.lower() == file_name.lower() or match.lower() in file_path.lower():
                        if file_path not in explicit_files:
                            explicit_files.append(file_path)
        
        # 特定の重要ファイル名パターンもチェック
        important_patterns = [
            ('design-doc', 'design'),
            ('readme', 'readme'),
            ('progress', 'progress'),
            ('config', 'config'),
            ('claude', 'claude')
        ]
        
        for pattern, keyword in important_patterns:
            if pattern in task_lower or keyword in task_lower:
                for file_path in file_list:
                    if pattern in file_path.lower():
                        if file_path not in explicit_files:
                            explicit_files.append(file_path)
        
        return explicit_files
    
    def _extended_file_search(self, task_description: str, file_list: List[str]) -> List[str]:
        """明示的ファイルが見つからない場合の拡張探索
        
        Args:
            task_description: タスク説明文
            file_list: 利用可能なファイルリスト
            
        Returns:
            拡張検索で発見されたファイルのリスト
        """
        import os
        import glob
        from pathlib import Path
        
        task_lower = task_description.lower()
        found_files = []
        
        # タスクからキーワードを抽出
        keywords_to_search = []
        
        # 1. ファイル名キーワードの抽出
        if 'design' in task_lower:
            keywords_to_search.extend(['design', 'architecture', 'spec'])
        if 'config' in task_lower:
            keywords_to_search.extend(['config', 'settings', 'setup'])
        if 'readme' in task_lower:
            keywords_to_search.extend(['readme', 'getting-started', 'guide'])
        if 'progress' in task_lower or '進捗' in task_lower:
            keywords_to_search.extend(['progress', 'changelog', 'history'])
        if 'claude' in task_lower:
            keywords_to_search.extend(['claude', 'ai', 'prompt'])
        
        # 2. 直接的なファイル探索（現在のディレクトリから）
        if keywords_to_search:
            try:
                cwd = os.getcwd()
                for keyword in keywords_to_search:
                    # 複数のパターンで探索
                    search_patterns = [
                        f"*{keyword}*",
                        f"**/*{keyword}*",
                        f"{keyword}*",
                        f"*{keyword}*.md",
                        f"*{keyword}*.txt",
                        f"docs/*{keyword}*",
                    ]
                    
                    for pattern in search_patterns:
                        try:
                            matches = glob.glob(pattern, recursive=True)
                            for match in matches:
                                # ファイルが存在し、リストに含まれているかチェック
                                if os.path.isfile(match):
                                    relative_path = str(Path(match).as_posix())
                                    if relative_path in file_list and relative_path not in found_files:
                                        found_files.append(relative_path)
                        except Exception:
                            continue  # パターンエラーは無視
                            
            except Exception as e:
                print(f"拡張ファイル検索エラー: {e}")
        
        # 3. ファイル名類似度による検索
        if not found_files and 'design-doc' in task_lower:
            # design-docに類似するファイルを探索
            for file_path in file_list:
                file_name_lower = file_path.lower()
                if any(keyword in file_name_lower for keyword in ['design', 'doc', 'spec', 'architecture']):
                    if file_path not in found_files:
                        found_files.append(file_path)
        
        return found_files[:5]  # 最大5ファイル
    
    def _summarize_documentation(self, filepath: str, content: str) -> str:
        """ドキュメントファイルの要約"""
        lines = content.split('\n')
        
        # 重要セクションを抽出
        important_sections = []
        current_section = []
        
        for line in lines[:100]:  # 最初の100行
            if line.startswith('#') and len(line.strip()) > 1:
                if current_section:
                    important_sections.append('\n'.join(current_section))
                current_section = [line]
            elif current_section:
                current_section.append(line)
        
        if current_section:
            important_sections.append('\n'.join(current_section))
        
        return '\n\n'.join(important_sections[:5])  # 最大5セクション
    
    def _summarize_code_file(self, filepath: str, content: str) -> str:
        """Pythonファイルの要約"""
        lines = content.split('\n')
        
        summary_parts = []
        
        # docstring抽出
        if '"""' in content:
            start = content.find('"""')
            end = content.find('"""', start + 3)
            if end != -1:
                docstring = content[start:end+3]
                summary_parts.append(f"モジュールdocstring: {docstring}")
        
        # クラス・関数定義抽出
        for line in lines:
            if line.strip().startswith(('class ', 'def ', 'async def ')):
                summary_parts.append(line.strip())
        
        return '\n'.join(summary_parts[:15])  # 最大15行
    
    def _summarize_config_file(self, filepath: str, content: str) -> str:
        """設定ファイルの要約"""
        return content[:300] + "..." if len(content) > 300 else content
    
    def _classify_file_type(self, filepath: str) -> str:
        """ファイルタイプの分類"""
        if 'test' in filepath.lower():
            return "テスト"
        elif filepath.endswith('.md'):
            return "ドキュメント"
        elif 'config' in filepath.lower() or filepath.endswith(('.yaml', '.yml')):
            return "設定"
        elif filepath.endswith('.py'):
            return "実装"
        else:
            return "その他"
    
    def _assess_file_importance(self, filepath: str, content: str) -> int:
        """ファイル重要度の評価（1-10）"""
        score = 5  # ベーススコア
        
        # ファイル名による重要度
        if 'main.py' in filepath or '__init__.py' in filepath:
            score += 2
        if 'orchestrator' in filepath.lower():
            score += 3
        if 'README' in filepath or 'PROGRESS' in filepath:
            score += 3
        if 'test' in filepath and 'end' in filepath:
            score += 2
        
        # 内容による重要度
        content_lower = content.lower()
        if 'class' in content_lower and 'def' in content_lower:
            score += 1
        if len(content) > 1000:  # 長いファイルは重要
            score += 1
        if 'promptsmith' in content_lower and 'scenario' in content_lower:
            score += 2
        
        return min(score, 10)
    
    def _parse_synthesis_result(self, response: str) -> Dict[str, Any]:
        """統合理解結果のパース"""
        return {
            "system_overview": response,  # 簡略版では全体をそのまま返す
            "key_components": [],
            "architecture": "詳細は統合理解結果を参照",
            "scenarios": [],
            "recommendations": []
        }
    
    # ===== The Pecking Order 関連メソッド =====
    
    def analyze_task_hierarchy(self, user_request: str, context: str = "", is_continuation: bool = False) -> Optional[Dict[str, Any]]:
        """ユーザー要求を階層的タスク構造に分析する
        
        Args:
            user_request: ユーザーの要求
            context: 追加コンテキスト
            is_continuation: 継続実行かどうか
            
        Returns:
            タスク構造の辞書、失敗時はNone
        """
        try:
            # LLMプロンプトの構築
            prompt = self._build_task_hierarchy_prompt(user_request, context, is_continuation)
            
            # Fast LLM で高速分析
            response = self.fast_llm.chat(prompt)
            
            if not response:
                return None
                
            # レスポンスをパースしてタスク構造に変換
            task_structure = self._parse_task_hierarchy_response(response)
            
            return task_structure
            
        except Exception as e:
            print(f"タスク階層分析エラー: {e}")
            return None
    
    def _build_task_hierarchy_prompt(self, user_request: str, context: str, is_continuation: bool) -> str:
        """タスク階層分析のプロンプトを構築"""
        
        if is_continuation:
            prompt_type = "継続実行のためのタスク分析"
            instruction = """
既存のタスクに追加するサブタスクや修正点を分析してください。
"""
        else:
            prompt_type = "新規タスクの階層分析"
            instruction = """
ユーザーの要求を階層的なタスクに分解してください。
メインゴールと、それを達成するための3-5個のサブタスクを定義してください。
"""
        
        return f"""# {prompt_type}

## ユーザー要求:
{user_request}

## コンテキスト:
{context if context else '(なし)'}

## 指示:
{instruction}

以下の形式でJSON構造を返してください:

```json
{{
    "main_goal": "メインゴールの簡潔な説明",
    "root_task": "ルートタスクの説明",
    "sub_tasks": [
        "サブタスク1の説明",
        "サブタスク2の説明", 
        "サブタスク3の説明"
    ],
    "additional_sub_tasks": [
        "追加のサブタスク1",
        "追加のサブタスク2"
    ]
}}
```

注意:
- main_goalは50文字以内
- 各タスクは具体的で実行可能な内容にしてください
- is_continuationが true の場合は additional_sub_tasks を重視してください
- 複雑すぎるタスクは適切に分割してください
"""

    def _parse_task_hierarchy_response(self, response: str) -> Dict[str, Any]:
        """LLMレスポンスからタスク構造をパース"""
        try:
            # JSON部分を抽出
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                task_structure = json.loads(json_str)
            else:
                # JSONブロックがない場合は直接パース試行
                task_structure = json.loads(response)
            
            # 必須フィールドの検証と補完
            if 'main_goal' not in task_structure:
                task_structure['main_goal'] = "ユーザー要求の実現"
            
            if 'root_task' not in task_structure:
                task_structure['root_task'] = task_structure['main_goal']
                
            if 'sub_tasks' not in task_structure:
                task_structure['sub_tasks'] = []
                
            if 'additional_sub_tasks' not in task_structure:
                task_structure['additional_sub_tasks'] = []
            
            # リスト型の保証
            for key in ['sub_tasks', 'additional_sub_tasks']:
                if not isinstance(task_structure[key], list):
                    task_structure[key] = []
                    
            return task_structure
            
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            print(f"タスク構造パースエラー: {e}")
            
            # フォールバック: シンプルな構造を生成
            return {
                "main_goal": "ユーザー要求の実現",
                "root_task": "ユーザー要求を処理する",
                "sub_tasks": [
                    "要求を分析する",
                    "必要な情報を収集する", 
                    "実行計画を立てる",
                    "計画を実行する"
                ],
                "additional_sub_tasks": []
            }


# グローバルLLMサービスインスタンス
llm_service = LLMService()