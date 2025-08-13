"""
TaskProfile分類システム

ユーザー要求を6種類のTaskProfileに分類する決定論的システム
LLM依存を最小化し、パターンマッチングとキーワード分析を使用
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from ..templates import TaskProfileType


@dataclass
class ClassificationResult:
    """分類結果を表現するクラス"""
    
    profile_type: TaskProfileType
    confidence: float  # 0.0-1.0
    detected_patterns: List[str]  # マッチしたパターン
    extracted_targets: List[str]  # 抽出された対象（ファイル名等）
    reasoning: str  # 分類理由


class TaskProfileClassifier:
    """TaskProfile分類器
    
    ユーザーの要求文を解析し、6種類のTaskProfileのいずれかに分類する
    """
    
    def __init__(self):
        """分類器を初期化"""
        self.patterns = self._build_classification_patterns()
    
    def classify(self, user_request: str) -> ClassificationResult:
        """ユーザー要求をTaskProfileに分類
        
        Args:
            user_request: ユーザーからの要求文
            
        Returns:
            分類結果
        """
        user_request_lower = user_request.lower()
        
        # 各TaskProfileに対してスコア計算
        scores = {}
        pattern_matches = {}
        
        for profile_type, pattern_config in self.patterns.items():
            score, matches = self._calculate_score(user_request_lower, pattern_config)
            scores[profile_type] = score
            pattern_matches[profile_type] = matches
        
        # 最高スコアのTaskProfileを選択
        best_profile = max(scores.keys(), key=lambda k: scores[k])
        best_score = scores[best_profile]
        
        # ファイル名等の対象を抽出
        extracted_targets = self._extract_targets(user_request)
        
        return ClassificationResult(
            profile_type=best_profile,
            confidence=min(best_score, 1.0),
            detected_patterns=pattern_matches[best_profile],
            extracted_targets=extracted_targets,
            reasoning=self._generate_reasoning(best_profile, pattern_matches[best_profile], best_score)
        )
    
    def _build_classification_patterns(self) -> Dict[TaskProfileType, Dict]:
        """分類用パターン辞書を構築 (5ノードアーキテクチャ統合版)"""
        return {
            # === 新しいユーザー要求ベース分類 ===
            TaskProfileType.INFORMATION_REQUEST: {
                "primary_keywords": [
                    "説明", "教えて", "内容", "について", "とは", "どんな", "確認",
                    "見て", "読み", "表示", "チェック", "概要", "情報", "参照して",
                    "レビューして", "内容をレビュー"
                ],
                "secondary_keywords": [
                    "ファイル", "クラス", "関数", "メソッド", "設定", "構造", "ドキュメント"
                ],
                "negative_keywords": [
                    "作成", "変更", "修正", "削除", "追加", "実装", "インストール",
                    "問題", "課題", "改善", "最適化"
                ],
                "base_score": 0.8  # スコアを上げて優先度向上
            },
            
            TaskProfileType.ANALYSIS_REQUEST: {
                "primary_keywords": [
                    "分析", "調べ", "問題", "課題", "ボトルネック", "リスク", "改善",
                    "評価", "診断", "検証", "監査", "品質分析", "コード分析"
                ],
                "secondary_keywords": [
                    "パフォーマンス", "セキュリティ", "品質", "効率", "最適化",
                    "アーキテクチャ", "設計", "構造", "バグ", "エラー"
                ],
                "negative_keywords": [
                    "作成", "実装", "インストール", "説明だけ", "内容を", "参照して",
                    "見て", "読み", "表示"
                ],
                "base_score": 0.7  # スコアを下げて、内容確認との差別化
            },
            
            TaskProfileType.CREATION_REQUEST: {
                "primary_keywords": [
                    "作成", "作って", "生成", "新規", "追加", "実装", "開発",
                    "書いて", "構築", "セットアップ"
                ],
                "secondary_keywords": [
                    "ファイル", "クラス", "関数", "テスト", "ドキュメント",
                    "設定", "スクリプト", "機能"
                ],
                "negative_keywords": [
                    "説明", "確認", "見るだけ", "表示"
                ],
                "base_score": 0.9
            },
            
            TaskProfileType.MODIFICATION_REQUEST: {
                "primary_keywords": [
                    "修正", "変更", "更新", "編集", "直して", "改修", "調整",
                    "リファクタリング", "改良", "アップデート"
                ],
                "secondary_keywords": [
                    "バグ", "エラー", "不具合", "機能", "コード", "設定"
                ],
                "negative_keywords": [
                    "新規", "作成", "説明だけ"
                ],
                "base_score": 0.9
            },
            
            TaskProfileType.SEARCH_REQUEST: {
                "primary_keywords": [
                    "探して", "検索", "見つけて", "探す", "発見", "特定", "特検",
                    "どこ", "場所", "箇所"
                ],
                "secondary_keywords": [
                    "ファイル", "コード", "関数", "クラス", "使用", "呼び出し",
                    "定義", "実装"
                ],
                "negative_keywords": [
                    "作成", "修正", "説明だけ"
                ],
                "base_score": 0.8
            },
            
            TaskProfileType.GUIDANCE_REQUEST: {
                "primary_keywords": [
                    "実行", "使い方", "方法", "手順", "やり方", "コマンド",
                    "操作", "動かし", "起動", "デプロイ", "インストール"
                ],
                "secondary_keywords": [
                    "テスト", "ビルド", "設定", "環境", "依存", "要件"
                ],
                "negative_keywords": [
                    "作成", "修正", "分析"
                ],
                "base_score": 0.7
            },
            
            # === 従来のサービス指向分類 (自動マッピング) ===
            TaskProfileType.FILE_ANALYSIS: {
                "primary_keywords": [
                    "分析", "説明", "ファイル", "コード", "構造", "内容",
                    "詳細", "見て", "確認"
                ],
                "secondary_keywords": [
                    "python", ".py", "クラス", "関数", "メソッド", "インポート"
                ],
                "negative_keywords": [
                    "作成", "修正", "削除", "変更", "実装"
                ],
                "base_score": 0.8
            },
            
            TaskProfileType.CODE_EXPLANATION: {
                "primary_keywords": [
                    "解説", "説明", "どう動く", "仕組み", "動作", "処理",
                    "理解", "わから", "教えて"
                ],
                "secondary_keywords": [
                    "コード", "アルゴリズム", "ロジック", "フロー", "流れ"
                ],
                "negative_keywords": [
                    "作成", "修正", "実装", "テスト"
                ],
                "base_score": 0.8
            },
            
            TaskProfileType.PROJECT_EXPLORATION: {
                "primary_keywords": [
                    "探索", "調査", "全体", "プロジェクト", "構成", "概観",
                    "マップ", "把握"
                ],
                "secondary_keywords": [
                    "ディレクトリ", "フォルダ", "ファイル一覧", "構造"
                ],
                "negative_keywords": [
                    "個別", "特定", "一つ"
                ],
                "base_score": 0.7
            },
            
            TaskProfileType.DEBUGGING_SUPPORT: {
                "primary_keywords": [
                    "デバッグ", "エラー", "バグ", "問題", "不具合", "動かない",
                    "修正", "直し"
                ],
                "secondary_keywords": [
                    "例外", "トレース", "ログ", "検証", "テスト"
                ],
                "negative_keywords": [
                    "新規", "作成", "説明だけ"
                ],
                "base_score": 0.9
            },
            
            TaskProfileType.IMPLEMENTATION_TASK: {
                "primary_keywords": [
                    "実装", "作成", "開発", "構築", "作って", "書いて",
                    "追加", "機能"
                ],
                "secondary_keywords": [
                    "新規", "新しい", "設計", "計画", "仕様"
                ],
                "negative_keywords": [
                    "修正", "分析", "説明だけ"
                ],
                "base_score": 0.9
            },
            
            TaskProfileType.CONSULTATION: {
                "primary_keywords": [
                    "相談", "アドバイス", "どうすべき", "推奨", "ベストプラクティス",
                    "意見", "判断", "悩み"
                ],
                "secondary_keywords": [
                    "設計", "アーキテクチャ", "方針", "戦略", "選択"
                ],
                "negative_keywords": [
                    "具体的", "実装", "コード"
                ],
                "base_score": 0.8
            },
            
            TaskProfileType.GENERAL_CHAT: {
                "primary_keywords": [
                    "雑談", "質問", "話", "教え", "知り", "聞き"
                ],
                "secondary_keywords": [
                    "プログラミング", "技術", "コンピューター", "開発"
                ],
                "negative_keywords": [
                    "具体的", "詳細", "実装", "作成"
                ],
                "base_score": 0.5  # 最低スコア（他がマッチしない場合のフォールバック）
            }
        }
    
    def _calculate_score(self, user_request: str, pattern_config: Dict) -> Tuple[float, List[str]]:
        """パターン設定に基づいてスコアを計算
        
        Args:
            user_request: ユーザー要求（小文字変換済み）
            pattern_config: パターン設定辞書
            
        Returns:
            (スコア, マッチしたパターンのリスト)
        """
        score = 0.0
        matches = []
        
        # Primary keywordsのマッチ
        primary_matches = 0
        for keyword in pattern_config["primary_keywords"]:
            if keyword in user_request:
                primary_matches += 1
                matches.append(f"primary:{keyword}")
        
        if primary_matches > 0:
            score += pattern_config["base_score"]
            score += min(primary_matches * 0.1, 0.2)  # 複数マッチボーナス
        
        # Secondary keywordsのマッチ
        secondary_matches = 0
        for keyword in pattern_config["secondary_keywords"]:
            if keyword in user_request:
                secondary_matches += 1
                matches.append(f"secondary:{keyword}")
        
        if secondary_matches > 0:
            score += min(secondary_matches * 0.05, 0.15)
        
        # Negative keywordsのペナルティ（強化）
        negative_matches = 0
        for keyword in pattern_config["negative_keywords"]:
            if keyword in user_request:
                negative_matches += 1
                matches.append(f"negative:{keyword}")
        
        if negative_matches > 0:
            # ネガティブキーワードのペナルティを強化
            penalty = min(negative_matches * 0.4, 0.7)
            score -= penalty
        
        # 特定パターンの優先度調整
        if "参照して" in user_request and "内容" in user_request:
            # 「参照して内容を」パターンはinformation_requestを優先
            if pattern_config.get("base_score", 0) == 0.8:  # information_request
                score += 0.2  # ボーナス
        
        return max(score, 0.0), matches
    
    def _extract_targets(self, user_request: str) -> List[str]:
        """要求文から対象（ファイル名等）を抽出
        
        Args:
            user_request: ユーザー要求文
            
        Returns:
            抽出された対象のリスト
        """
        targets = []
        
        # ファイル名パターン（拡張子付き）
        file_patterns = [
            r'([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z]{1,4})',  # filename.ext
            r'([a-zA-Z_][a-zA-Z0-9_]*\.py)',  # Python files
            r'([a-zA-Z_][a-zA-Z0-9_]*\.js)',  # JavaScript files
            r'([a-zA-Z_][a-zA-Z0-9_]*\.ts)',  # TypeScript files
            r'([a-zA-Z_][a-zA-Z0-9_]*\.md)',  # Markdown files
            r'([a-zA-Z_][a-zA-Z0-9_]*\.json)',  # JSON files
            r'([a-zA-Z_][a-zA-Z0-9_]*\.yaml)',  # YAML files
            r'([a-zA-Z_][a-zA-Z0-9_]*\.yml)',  # YAML files
        ]
        
        for pattern in file_patterns:
            matches = re.findall(pattern, user_request)
            targets.extend(matches)
        
        # クラス名・関数名パターン
        code_patterns = [
            r'([A-Z][a-zA-Z0-9_]*)',  # PascalCase (クラス名)
            r'([a-z_][a-zA-Z0-9_]*)\(',  # function_name( (関数呼び出し)
        ]
        
        for pattern in code_patterns:
            matches = re.findall(pattern, user_request)
            targets.extend(matches)
        
        # 重複を除去して返す
        return list(set(targets))
    
    def _generate_reasoning(self, profile_type: TaskProfileType, matches: List[str], score: float) -> str:
        """分類理由を生成
        
        Args:
            profile_type: 分類されたTaskProfileType
            matches: マッチしたパターンのリスト
            score: 計算されたスコア
            
        Returns:
            分類理由の説明文
        """
        primary_matches = [m for m in matches if m.startswith("primary:")]
        secondary_matches = [m for m in matches if m.startswith("secondary:")]
        negative_matches = [m for m in matches if m.startswith("negative:")]
        
        reasoning_parts = [
            f"TaskProfile: {profile_type.value}",
            f"信頼度: {score:.2f}"
        ]
        
        if primary_matches:
            keywords = [m.split(":", 1)[1] for m in primary_matches]
            reasoning_parts.append(f"主要キーワード検出: {', '.join(keywords)}")
        
        if secondary_matches:
            keywords = [m.split(":", 1)[1] for m in secondary_matches]
            reasoning_parts.append(f"補助キーワード検出: {', '.join(keywords)}")
        
        if negative_matches:
            keywords = [m.split(":", 1)[1] for m in negative_matches]
            reasoning_parts.append(f"ネガティブキーワード検出: {', '.join(keywords)}")
        
        return " | ".join(reasoning_parts)


# グローバルな分類器インスタンス
task_classifier = TaskProfileClassifier()