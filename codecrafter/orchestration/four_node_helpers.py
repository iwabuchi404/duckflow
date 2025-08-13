"""
4ノードオーケストレーター用のヘルパーメソッド実装

各ノードで使用される詳細な処理ロジックを提供します。
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from ..base.llm_client import llm_manager
from ..state.agent_state import AgentState
from ..tools.file_tools import file_tools
from ..tools.rag_tools import rag_tools
from ..ui.rich_ui import rich_ui
from ..prompts.four_node_context import (
    UnderstandingResult, GatheredInfo, ExecutionResult, EvaluationResult,
    FileContent, ProjectContext, RiskAssessment, ApprovalStatus, ToolResult,
    ExecutionError, ErrorAnalysis, ExecutionPlan, RiskLevel, NextAction
)
from ..ui.rich_ui import rich_ui


class FourNodeHelpers:
    """4ノードオーケストレーター用のヘルパーメソッド集"""
    
    def __init__(self, prompt_compiler, routing_engine):
        """
        ヘルパーを初期化
        
        Args:
            prompt_compiler: FourNodePromptCompiler インスタンス
            routing_engine: RoutingEngine インスタンス
        """
        self.prompt_compiler = prompt_compiler
        self.routing_engine = routing_engine
    
    # ===== 理解・計画ノード用ヘルパー =====
    
    def prepare_lightweight_context(self, state_obj: AgentState) -> None:
        """
        軽量なワークスペースコンテキストを準備
        
        Args:
            state_obj: AgentState オブジェクト
        """
        try:
            if not hasattr(state_obj, 'workspace') or not state_obj.workspace:
                # ワークスペース情報がない場合は簡易的に作成
                workspace_info = self._create_basic_workspace_info()
                state_obj.workspace = workspace_info
            
            # ファイルリストの軽量化（最大20ファイル）
            if hasattr(state_obj.workspace, 'files') and len(state_obj.workspace.files) > 20:
                state_obj.workspace.files = state_obj.workspace.files[:20]
                
        except Exception as e:
            rich_ui.print_warning(f"軽量コンテキスト準備で問題: {e}")
    
    def analyze_user_intent(self, state_obj: AgentState) -> Dict[str, Any]:
        """
        RoutingEngineを使用した意図分析
        
        Args:
            state_obj: AgentState オブジェクト
            
        Returns:
            意図分析結果の辞書
        """
        try:
            # 最新のユーザーメッセージを取得
            last_user_message = self._get_last_user_message(state_obj)
            if not last_user_message:
                return {"needs_file_read": False, "operation_type": "chat"}
            
            # ワークスペースファイル一覧を取得
            workspace_files = []
            if state_obj.workspace and hasattr(state_obj.workspace, 'files'):
                workspace_files = state_obj.workspace.files or []
            
            # ワークスペース情報がない場合はfile_toolsを使って動的に取得
            if not workspace_files:
                try:
                    file_list_result = file_tools.list_files(".", recursive=True)
                    if isinstance(file_list_result, list):
                        workspace_files = [f.get('path', f.get('name', str(f))) for f in file_list_result if isinstance(f, dict)]
                    elif isinstance(file_list_result, dict) and 'files' in file_list_result:
                        workspace_files = [f.get('path', f.get('name', str(f))) for f in file_list_result['files'] if isinstance(f, dict)]
                    
                    # デバッグ: ワークスペースファイル数を表示
                    rich_ui.print_message(f"[DEBUG] ワークスペースファイル数: {len(workspace_files)}", "info")
                    
                    
                except Exception as e:
                    rich_ui.print_warning(f"ワークスペースファイル取得エラー: {e}")
                    workspace_files = []
            
            # RoutingEngineによる分析
            routing_decision = self.routing_engine.analyze_user_intent(
                last_user_message, workspace_files
            )
            
            # デバッグ: ルーティング結果を表示
            rich_ui.print_message(f"[DEBUG] ルーティング結果: needs_file_read={routing_decision.needs_file_read}, target_files={len(routing_decision.target_files)}件", "info")
            if routing_decision.target_files:
                rich_ui.print_message(f"[DEBUG] 対象ファイル: {routing_decision.target_files[:3]}", "info")
            
            return {
                "needs_file_read": routing_decision.needs_file_read,
                "operation_type": routing_decision.operation_type,
                "target_files": routing_decision.target_files,
                "confidence": routing_decision.confidence
            }
            
        except Exception as e:
            rich_ui.print_warning(f"意図分析で問題: {e}")
            return {"needs_file_read": False, "operation_type": "chat"}
    
    def is_retry_context(self, state_obj: AgentState) -> bool:
        """
        再試行コンテキストの判定
        
        Args:
            state_obj: AgentState オブジェクト
            
        Returns:
            再試行かどうかの真偽値
        """
        try:
            # エラー履歴があるかチェック
            if hasattr(state_obj, 'error_history') and state_obj.error_history:
                return True
            
            # 過去のツール実行でエラーがあったかチェック
            if hasattr(state_obj, 'tool_executions'):
                for execution in state_obj.tool_executions[-3:]:  # 直近3件をチェック
                    if execution.error:  # エラーがある場合は失敗と判定
                        return True
            
            return False
            
        except Exception as e:
            rich_ui.print_warning(f"再試行判定で問題: {e}")
            return False
    
    def execute_understanding_prompt(self, state_obj: AgentState, four_node_context, routing_decision: Dict[str, Any], is_retry: bool) -> UnderstandingResult:
        """
        理解・計画プロンプトの実行
        
        Args:
            state_obj: AgentState オブジェクト
            four_node_context: FourNodePromptContext オブジェクト
            routing_decision: 意図分析結果
            is_retry: 再試行かどうか
            
        Returns:
            理解結果
        """
        try:
            # タスク種別情報をfour_node_contextに設定
            operation_type = routing_decision.get("operation_type", "chat")
            four_node_context.operation_type = operation_type
            rich_ui.print_message(f"[TASK_TYPE] 設定完了: {operation_type}", "info")
            
            # タスクチェーンが空の場合はエラーにしない
            if not hasattr(four_node_context, 'task_chain') or not four_node_context.task_chain:
                rich_ui.print_warning("タスクチェーンが空です - フォールバック応答を使用")
                return self._create_fallback_understanding_result(state_obj)
            
            # プロンプトの生成
            try:
                prompt = self.prompt_compiler.compile_node_prompt(four_node_context)
            except Exception as pe:
                rich_ui.print_warning(f"プロンプト生成エラー: {pe} - シンプルプロンプトを使用")
                # シンプルなフォールバックプロンプト
                last_message = self._get_last_user_message(state_obj)
                prompt = f"ユーザー要求: {last_message}\n\nこの要求を理解し、実行計画を立案してください。"
            
            # LLMの実行
            response = llm_manager.chat(prompt)
            
            # レスポンスの解析
            understanding_result = self._parse_understanding_response(response, routing_decision, is_retry)
            
            return understanding_result
            
        except Exception as e:
            rich_ui.print_error(f"理解プロンプト実行エラー: {e}")
            # フォールバック結果を返す
            return self._create_fallback_understanding_result(state_obj)
    
    # ===== 情報収集ノード用ヘルパー =====
    
    def determine_collection_strategy(self, understanding_result: UnderstandingResult) -> str:
        """
        情報収集戦略の決定
        
        Args:
            understanding_result: 理解結果
            
        Returns:
            収集戦略の文字列
        """
        complexity = understanding_result.execution_plan.estimated_complexity
        info_needs = len(understanding_result.information_needs)
        
        if complexity == "high" or info_needs > 5:
            return "comprehensive"
        elif complexity == "medium" or info_needs > 2:
            return "focused"
        else:
            return "minimal"
    
    def collect_file_information(self, understanding_result: UnderstandingResult, state_obj: AgentState) -> Dict[str, FileContent]:
        """
        ファイル情報の収集
        
        Args:
            understanding_result: 理解結果
            state_obj: AgentState オブジェクト
            
        Returns:
            収集されたファイル情報の辞書
        """
        collected_files = {}
        
        try:
            # デバッグ: 実行計画の詳細を表示
            rich_ui.print_message(f"[DEBUG] 実行計画のファイル数: {len(understanding_result.execution_plan.expected_files)}", "info")
            rich_ui.print_message(f"[DEBUG] 実行計画のファイル: {understanding_result.execution_plan.expected_files}", "info")
            
            # 実行計画で指定されたファイルを収集
            raw_target_files = understanding_result.execution_plan.expected_files or []
            
            # 重複パスの除去処理
            target_files = self._deduplicate_file_paths(raw_target_files)
            
            # デバッグ情報
            if len(raw_target_files) != len(target_files):
                rich_ui.print_message(f"[FILE_DEDUP] 重複除去: {len(raw_target_files)} → {len(target_files)} ファイル", "info")
                removed_duplicates = set(raw_target_files) - set(target_files)
                rich_ui.print_message(f"[FILE_DEDUP] 除去されたファイル: {list(removed_duplicates)}", "warning")
            
            # 対象ファイルが含まれているかチェック（詳細デバッグ）
            rich_ui.print_message(f"[FILE_COLLECTION_DEBUG] 収集対象ファイル: {target_files}", "info")
            
            # ターゲットファイル検査（test_step2d_graph.pyが含まれているかチェック）
            test_file_pattern = "test_step2d_graph"
            target_file_found = any(test_file_pattern in str(f) for f in target_files)
            rich_ui.print_message(f"[FILE_COLLECTION_CRITICAL] '{test_file_pattern}' 含有確認: {target_file_found}", "warning" if not target_file_found else "info")
            
            if not target_file_found:
                rich_ui.print_message(f"[FILE_COLLECTION_ERROR] ターゲットファイルが見つかりません！計画に問題があります", "error")
            
            for file_path in target_files:
                try:
                    rich_ui.print_message(f"[FILE_READ] ファイル読み取り開始: {file_path}", "info")
                    
                    # パスの正規化（バックスラッシュエスケープ問題の修正）
                    from pathlib import Path
                    import os
                    
                    # バックスラッシュエスケープを修正
                    safe_path = file_path.replace('\\\\', '\\')  # 二重バックスラッシュを単一に
                    normalized_path = str(Path(safe_path).resolve())
                    
                    rich_ui.print_message(f"[FILE_READ] 正規化パス: {normalized_path}", "info")
                    
                    # ファイル存在確認
                    if not Path(normalized_path).exists():
                        rich_ui.print_warning(f"[FILE_READ] ファイルが存在しません: {normalized_path}")
                        # 相対パスで再試行
                        relative_path = Path(safe_path)
                        if relative_path.exists():
                            normalized_path = str(relative_path.resolve())
                            rich_ui.print_message(f"[FILE_READ] 相対パスで発見: {normalized_path}", "info")
                        else:
                            rich_ui.print_error(f"[FILE_READ] ファイルが見つかりません: {file_path}")
                            continue
                    
                    # ファイル読み取り
                    rich_ui.print_message(f"[FILE_READ] 読み取り実行中...", "info")
                    content = file_tools.read_file(normalized_path)
                    
                    rich_ui.print_message(f"[FILE_READ] 読み取り結果: {len(content) if content else 0}文字", "info")
                    
                    if content:
                        # ファイル情報の取得
                        try:
                            file_info = file_tools.get_file_info(normalized_path)
                            size = file_info.get('size', len(content))
                        except Exception as info_error:
                            rich_ui.print_warning(f"[FILE_READ] ファイル情報取得失敗: {info_error}")
                            size = len(content)
                        
                        # FileContentオブジェクト作成
                        file_content = FileContent(
                            path=normalized_path,
                            content=content[:8000],  # 最大8000文字に制限
                            encoding="utf-8",
                            size=size,
                            last_modified=datetime.now(),
                            relevance_score=0.9
                        )
                        
                        collected_files[file_path] = file_content
                        rich_ui.print_success(f"[FILE_READ] 完了: {normalized_path} ({len(content)}文字 → {len(file_content.content)}文字)")
                    else:
                        rich_ui.print_warning(f"[FILE_READ] ファイルが空: {normalized_path}")
                        
                except Exception as e:
                    rich_ui.print_warning(f"ファイル {file_path} の読み取りに失敗: {e}")
                    # 読み取りに失敗しても、空の内容で追加
                    # パスの正規化を試行
                    try:
                        from pathlib import Path
                        normalized_path = str(Path(file_path).resolve())
                    except:
                        normalized_path = file_path
                    
                    collected_files[file_path] = FileContent(
                        path=normalized_path,
                        content=f"[読み取りエラー: {str(e)}]",
                        encoding="utf-8",
                        size=0,
                        last_modified=datetime.now(),
                        relevance_score=0.1
                    )
                    
            # 関連ファイルの自動発見（必要に応じて）
            if understanding_result.execution_plan.estimated_complexity in ["medium", "high"]:
                related_files = self._discover_related_files(understanding_result, state_obj)
                collected_files.update(related_files)
                
        except Exception as e:
            rich_ui.print_error(f"ファイル情報収集エラー: {e}")
        
        return collected_files
    
    def perform_rag_search(self, understanding_result: UnderstandingResult, state_obj: AgentState):
        """
        RAG検索の実行
        
        Args:
            understanding_result: 理解結果
            state_obj: AgentState オブジェクト
            
        Returns:
            RAG検索結果のリスト
        """
        rag_results = []
        
        try:
            # 要求分析からキーワードを抽出
            search_queries = self._extract_search_queries(understanding_result)
            
            for query in search_queries[:3]:  # 最大3クエリに制限
                try:
                    # RAG検索実行
                    results = rag_tools.search_code(query)
                    if results:
                        rag_results.append({
                            "query": query,
                            "results": results[:5],  # 上位5件に制限
                            "confidence": 0.8,  # 簡略化
                            "total_matches": len(results)
                        })
                except Exception as e:
                    rich_ui.print_warning(f"RAG検索 '{query}' で問題: {e}")
                    
        except Exception as e:
            rich_ui.print_error(f"RAG検索実行エラー: {e}")
        
        return rag_results
    
    def build_project_context(self, collected_files: Dict[str, FileContent], state_obj: AgentState) -> ProjectContext:
        """
        プロジェクト文脈の構築
        
        Args:
            collected_files: 収集されたファイル情報
            state_obj: AgentState オブジェクト
            
        Returns:
            プロジェクト文脈
        """
        try:
            # ファイル拡張子から言語を推定
            languages = set()
            for file_path in collected_files.keys():
                ext = Path(file_path).suffix.lower()
                if ext in ['.py', '.pyw']:
                    languages.add('Python')
                elif ext in ['.js', '.jsx']:
                    languages.add('JavaScript')
                elif ext in ['.ts', '.tsx']:
                    languages.add('TypeScript')
                elif ext in ['.java']:
                    languages.add('Java')
                elif ext in ['.cpp', '.c', '.h']:
                    languages.add('C/C++')
            
            # プロジェクトタイプの推定
            project_type = "General"
            if 'Python' in languages:
                if any('django' in content.content.lower() for content in collected_files.values()):
                    project_type = "Django Web Application"
                elif any('flask' in content.content.lower() for content in collected_files.values()):
                    project_type = "Flask Web Application"
                else:
                    project_type = "Python Application"
            
            # フレームワークの検出
            frameworks = []
            for content in collected_files.values():
                content_lower = content.content.lower()
                if 'react' in content_lower:
                    frameworks.append('React')
                if 'vue' in content_lower:
                    frameworks.append('Vue')
                if 'django' in content_lower:
                    frameworks.append('Django')
                if 'flask' in content_lower:
                    frameworks.append('Flask')
            
            return ProjectContext(
                project_type=project_type,
                main_languages=list(languages) or ['Unknown'],
                frameworks=list(set(frameworks)),
                architecture_pattern="Unknown",  # 簡略化
                key_directories=self._identify_key_directories(collected_files),
                recent_changes=[]  # 簡略化
            )
            
        except Exception as e:
            rich_ui.print_error(f"プロジェクト文脈構築エラー: {e}")
            return ProjectContext(
                project_type="Unknown",
                main_languages=["Unknown"],
                frameworks=[],
                architecture_pattern="Unknown",
                key_directories=[],
                recent_changes=[]
            )
    
    # ===== 安全実行ノード用ヘルパー =====
    
    def assess_execution_risks(self, understanding_result: UnderstandingResult, gathered_info: Optional[GatheredInfo], state_obj: AgentState) -> RiskAssessment:
        """
        実行リスクの評価
        
        Args:
            understanding_result: 理解結果
            gathered_info: 収集された情報
            state_obj: AgentState オブジェクト
            
        Returns:
            リスク評価結果
        """
        try:
            risk_factors = []
            overall_risk = RiskLevel.LOW
            
            # 読み取り専用ツールのリスト
            read_only_tools = ['read_file', 'list_files', 'get_file_info', 'llm_analysis']
            
            # ツールベースのリスク評価
            for tool_name in understanding_result.execution_plan.required_tools:
                if tool_name in read_only_tools:
                    # 読み取り専用操作は低リスク
                    risk_factors.append(f"ファイル読み取り・分析: {tool_name}")
                    # overall_riskは変更しない（LOW のまま）
                elif tool_name in ['write_file', 'create_directory']:
                    risk_factors.append(f"ファイルシステム変更: {tool_name}")
                    overall_risk = RiskLevel.MEDIUM
                elif tool_name in ['execute_shell_command']:
                    risk_factors.append(f"シェルコマンド実行: {tool_name}")
                    overall_risk = RiskLevel.HIGH
            
            # ファイル変更のリスク評価（読み取り専用の場合はスキップ）
            is_read_only = all(tool in read_only_tools
                              for tool in understanding_result.execution_plan.required_tools)
            
            if not is_read_only:
                for file_path in understanding_result.execution_plan.expected_files:
                    if gathered_info and file_path in gathered_info.collected_files:
                        risk_factors.append(f"既存ファイル変更: {file_path}")
                        if overall_risk == RiskLevel.LOW:
                            overall_risk = RiskLevel.MEDIUM
            
            # 複雑度ベースのリスク調整
            if understanding_result.execution_plan.estimated_complexity == "high":
                overall_risk = RiskLevel.HIGH
                risk_factors.append("高複雑度タスク")
            
            # 読み取り専用操作は承認不要
            approval_required = False if is_read_only else overall_risk in [RiskLevel.MEDIUM, RiskLevel.HIGH]
            
            return RiskAssessment(
                overall_risk=overall_risk,
                risk_factors=risk_factors,
                mitigation_measures=self._suggest_mitigation_measures(risk_factors),
                approval_required=approval_required,
                reasoning=f"リスクレベル {overall_risk.value}: {len(risk_factors)}個の要因" + (" (読み取り専用)" if is_read_only else "")
            )
            
        except Exception as e:
            rich_ui.print_error(f"リスク評価エラー: {e}")
            return RiskAssessment(
                overall_risk=RiskLevel.HIGH,
                risk_factors=["評価エラーによる高リスク設定"],
                mitigation_measures=["手動確認を推奨"],
                approval_required=True,
                reasoning="エラーのため安全側に設定"
            )
    
    def handle_approval_process(self, risk_assessment: RiskAssessment, understanding_result: UnderstandingResult, state_obj: AgentState) -> ApprovalStatus:
        """
        承認プロセスの処理
        
        Args:
            risk_assessment: リスク評価結果
            understanding_result: 理解結果
            state_obj: AgentState オブジェクト
            
        Returns:
            承認状況
        """
        if not risk_assessment.approval_required:
            # 承認不要の場合
            return ApprovalStatus(
                requested=False,
                granted=True,
                timestamp=datetime.now(),
                approval_message="低リスクのため自動承認"
            )
        
        try:
            # 人間への承認要求
            approval_message = self._create_approval_message(risk_assessment, understanding_result)
            
            rich_ui.print_warning("⚠️  承認が必要な操作があります")
            rich_ui.print_message(approval_message, "info")
            
            # RichUIを使用した承認プロセス
            granted = rich_ui.get_confirmation("続行しますか？", default=False)
            
            return ApprovalStatus(
                requested=True,
                granted=granted,
                timestamp=datetime.now(),
                approval_message=f"ユーザー判断: {'承認' if granted else '拒否'}"
            )
            
        except Exception as e:
            rich_ui.print_error(f"承認プロセスエラー: {e}")
            return ApprovalStatus(
                requested=True,
                granted=False,
                timestamp=datetime.now(),
                approval_message=f"エラーのため拒否: {e}"
            )
    
    # ===== プライベートヘルパーメソッド =====
    
    def _create_basic_workspace_info(self):
        """基本的なワークスペース情報を作成"""
        try:
            current_dir = Path.cwd()
            files = []
            for file_path in current_dir.rglob("*"):
                if file_path.is_file() and len(files) < 20:
                    files.append(str(file_path.relative_to(current_dir)))
            
            return type('WorkspaceInfo', (), {
                'path': str(current_dir),
                'files': files
            })()
        except Exception:
            return None
    
    def _get_last_user_message(self, state_obj: AgentState) -> Optional[str]:
        """最後のユーザーメッセージを取得"""
        try:
            if hasattr(state_obj, 'conversation_history'):
                for msg in reversed(state_obj.conversation_history):
                    if msg.role == 'user':
                        return msg.content
        except Exception:
            pass
        return None
    
    def _parse_understanding_response(self, response: str, routing_decision: Dict[str, Any], is_retry: bool) -> UnderstandingResult:
        """TaskProfile分類と実行計画を作成（5ノードアーキテクチャ対応）"""
        
        # RoutingEngineの結果を基本情報として利用
        operation_type = routing_decision.get("operation_type", "chat")
        needs_file_read = routing_decision.get("needs_file_read", False)
        target_files = routing_decision.get("target_files", [])
        
        try:
            # ユーザーメッセージを取得
            user_message = response
            
            # TaskProfile分類を実行
            from ..services.task_classifier import task_classifier
            classification_result = task_classifier.classify(user_message)
            
            rich_ui.print_message(f"[TaskProfile分類] {classification_result.profile_type.value} (信頼度: {classification_result.confidence:.2f})", "info")
            rich_ui.print_message(f"[分類理由] {classification_result.reasoning}", "info")
            
            # LLMで詳細なコンテンツ計画を生成
            from ..services import llm_service
            
            # TaskProfile特化プロンプトでコンテンツ事前生成
            content_planning_request = {
                "user_request": user_message,
                "task_profile_type": classification_result.profile_type.value,
                "detected_targets": classification_result.extracted_targets,
                "detected_files": target_files,
                "operation_type": operation_type,
                "needs_file_access": needs_file_read,
                "context": {
                    "is_retry": is_retry,
                    "routing_confidence": routing_decision.get("confidence", 0.5),
                    "classification_confidence": classification_result.confidence
                }
            }
            
            rich_ui.print_message("[コンテンツ計画] TaskProfile特化の詳細分析を実行中...", "info")
            content_plan = llm_service.generate_content_plan(content_planning_request)
            
            if content_plan:
                return UnderstandingResult(
                    requirement_analysis=content_plan.get("requirement_analysis", response[:500]),
                    execution_plan=ExecutionPlan(
                        summary=content_plan.get("summary", f"{classification_result.profile_type.value}の実行計画"),
                        steps=content_plan.get("steps", ["情報収集", "データ分析", "応答生成"]),
                        required_tools=content_plan.get("required_tools", ["read_file"] if needs_file_read else []),
                        expected_files=content_plan.get("expected_files", target_files),
                        estimated_complexity=content_plan.get("complexity", "medium"),
                        success_criteria=content_plan.get("success_criteria", "TaskProfileに基づく適切な応答生成")
                    ),
                    identified_risks=content_plan.get("risks", []),
                    information_needs=content_plan.get("information_needs", []),
                    confidence=min(classification_result.confidence, content_plan.get("confidence", 0.8)),
                    complexity_assessment=content_plan.get("complexity", "medium"),
                    # 5ノードアーキテクチャ用の新フィールド
                    task_profile_type=classification_result.profile_type,
                    content_structure_plan=content_plan.get("content_structure", {}),
                    extracted_targets=classification_result.extracted_targets
                )
            
        except Exception as e:
            rich_ui.print_warning(f"LLMService実行計画生成でエラー: {e} - フォールバックを使用")
        
        # フォールバック: 従来の簡単な処理
        if needs_file_read and target_files:
            summary = f"ファイル '{', '.join(target_files)}' の内容を読み取り、分析・説明する"
            steps = [
                f"ファイル読み取り: {', '.join(target_files)}",
                "ファイル内容の分析", 
                "処理内容の説明生成",
                "ユーザーへの回答"
            ]
            required_tools = ["read_file", "llm_analysis"]  # 分析処理を含む
            complexity = "medium"
            
        elif operation_type == "file_list":
            # ファイル一覧が必要な場合
            summary = "ワークスペース内のファイル構造を確認し、一覧を提供する"
            steps = [
                "ファイル一覧の取得",
                "ファイル構造の整理",
                "ユーザーへの結果表示"
            ]
            required_tools = ["list_files"]
            complexity = "low"
            
        else:
            # 通常の対話
            summary = "ユーザーの要求を理解し、適切な回答を提供する"
            steps = [
                "要求の分析",
                "回答の生成"
            ]
            required_tools = []
            complexity = "low"
        
        return UnderstandingResult(
            requirement_analysis=response[:500],  # 最初の500文字
            execution_plan=ExecutionPlan(
                summary=summary,
                steps=steps,
                required_tools=required_tools,
                expected_files=target_files,
                estimated_complexity=complexity,
                success_criteria="ユーザーの要求を正確に満たす"
            ),
            identified_risks=["ファイル読み取りエラーの可能性"] if needs_file_read else ["なし"],
            information_needs=[] if target_files else ["追加情報が必要"],
            confidence=0.9 if needs_file_read else 0.8,
            complexity_assessment=f"{complexity}レベルの複雑さ"
        )
    
    def _create_fallback_understanding_result(self, state_obj: AgentState) -> UnderstandingResult:
        """フォールバック用の理解結果を作成"""
        return UnderstandingResult(
            requirement_analysis="エラーのためフォールバック応答",
            execution_plan=ExecutionPlan(
                summary="エラー回復計画",
                steps=["エラー状況の確認"],
                required_tools=[],
                expected_files=[],
                estimated_complexity="low",
                success_criteria="エラー状況の説明"
            ),
            identified_risks=["エラー状態"],
            information_needs=[],
            confidence=0.3,
            complexity_assessment="エラー状態"
        )
    
    # その他のプライベートメソッドは簡略化
    def _discover_related_files(self, understanding_result: UnderstandingResult, state_obj: AgentState) -> Dict[str, FileContent]:
        return {}
    
    def _extract_search_queries(self, understanding_result: UnderstandingResult) -> List[str]:
        return []
    
    def _identify_key_directories(self, collected_files: Dict[str, FileContent]) -> List[str]:
        return list(set(str(Path(f).parent) for f in collected_files.keys()))
    
    def _suggest_mitigation_measures(self, risk_factors: List[str]) -> List[str]:
        return ["バックアップ作成", "段階的実行", "結果確認"]
    
    def _create_approval_message(self, risk_assessment: RiskAssessment, understanding_result: UnderstandingResult) -> str:
        return f"""
実行計画: {understanding_result.execution_plan.summary}
リスクレベル: {risk_assessment.overall_risk.value}
リスク要因: {', '.join(risk_assessment.risk_factors)}
軽減策: {', '.join(risk_assessment.mitigation_measures)}
"""
    
    def _deduplicate_file_paths(self, file_paths: List[str]) -> List[str]:
        """重複するファイルパスを除去する
        
        Args:
            file_paths: ファイルパスのリスト（重複あり）
            
        Returns:
            重複を除去したファイルパスのリスト（フルパス優先）
        """
        if not file_paths:
            return []
        
        from pathlib import Path
        import os
        
        # パス正規化と重複検出のためのマップ
        path_map = {}  # 正規化パス -> 元のパス
        resolved_paths = {}  # ファイル名 -> (フルパス, 元パス)
        
        for original_path in file_paths:
            try:
                # パスの安全化
                safe_path = original_path.replace('\\\\', '\\')
                
                # ファイル名を取得
                filename = Path(safe_path).name
                
                # パスが存在するか確認
                try:
                    resolved_path = str(Path(safe_path).resolve())
                    path_exists = Path(resolved_path).exists()
                except:
                    resolved_path = safe_path
                    path_exists = False
                
                # 既に同じファイル名が登録されているか確認
                if filename in resolved_paths:
                    existing_full_path, existing_original = resolved_paths[filename]
                    
                    # 現在のパスの方が良い条件か確認
                    current_is_better = (
                        path_exists and not Path(existing_full_path).exists() or  # 現在のパスが存在し、既存が存在しない
                        len(safe_path) > len(existing_original) and path_exists or  # 現在のパスがより詳細で存在する
                        os.path.isabs(safe_path) and not os.path.isabs(existing_original)  # 現在のパスが絶対パス
                    )
                    
                    if current_is_better:
                        resolved_paths[filename] = (resolved_path, original_path)
                        rich_ui.print_message(f"[FILE_DEDUP] {filename}: {existing_original} → {original_path} (より良いパス)", "info")
                else:
                    resolved_paths[filename] = (resolved_path, original_path)
                    
            except Exception as e:
                # エラーが発生した場合はそのまま保持
                rich_ui.print_message(f"[FILE_DEDUP] パス処理エラー {original_path}: {e}", "warning")
                filename = original_path
                resolved_paths[filename] = (original_path, original_path)
        
        # 重複除去されたパスリストを作成
        deduplicated = [original_path for _, original_path in resolved_paths.values()]
        
        return deduplicated