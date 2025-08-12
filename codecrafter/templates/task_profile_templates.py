"""
TaskProfileベースのテンプレートシステム

5ノードアーキテクチャの応答生成ノードで使用される
決定論的なレポート生成テンプレート群
"""

from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class TaskProfileType(Enum):
    """TaskProfileの種別定義"""
    INFORMATION_REQUEST = "information_request"
    ANALYSIS_REQUEST = "analysis_request"
    CREATION_REQUEST = "creation_request"
    MODIFICATION_REQUEST = "modification_request"
    SEARCH_REQUEST = "search_request"
    GUIDANCE_REQUEST = "guidance_request"


@dataclass
class TaskProfileTemplate:
    """TaskProfile用テンプレート定義"""
    
    profile_type: TaskProfileType
    structure: str  # Markdownテンプレート構造
    data_mapping: Dict[str, str]  # テンプレート変数 → データソースのマッピング
    required_data_points: List[str]  # 必須データポイント
    optional_data_points: List[str]  # オプションデータポイント
    fallback_values: Dict[str, str]  # データが取得できない場合のフォールバック値


# TaskProfile別テンプレート定義
TASK_PROFILE_TEMPLATES = {
    
    TaskProfileType.INFORMATION_REQUEST: TaskProfileTemplate(
        profile_type=TaskProfileType.INFORMATION_REQUEST,
        structure="""## 📄 {target_name}

### 📋 基本情報
{basic_info}

### 🔍 詳細内容
{detailed_content}

### 🔗 関連要素
{related_elements}

### 💡 補足事項
{additional_notes}""",
        
        data_mapping={
            "target_name": "target_filename",
            "basic_info": "file_metadata_summary",
            "detailed_content": "file_content_analysis", 
            "related_elements": "dependencies_summary",
            "additional_notes": "usage_examples"
        },
        
        required_data_points=["target_filename", "file_content_analysis"],
        optional_data_points=["file_metadata_summary", "dependencies_summary", "usage_examples"],
        fallback_values={
            "basic_info": "ファイル情報の取得中にエラーが発生しました",
            "detailed_content": "内容の分析中にエラーが発生しました",
            "related_elements": "関連要素の分析は実行されませんでした",
            "additional_notes": "追加情報はありません"
        }
    ),
    
    TaskProfileType.ANALYSIS_REQUEST: TaskProfileTemplate(
        profile_type=TaskProfileType.ANALYSIS_REQUEST,
        structure="""## 🔬 分析レポート: {target_name}

### 📊 現状評価
{current_assessment}

### ⚠️ 発見事項
{findings}

### ✅ 推奨改善策
{recommendations}

### 📈 優先度評価
{priority_analysis}""",
        
        data_mapping={
            "target_name": "analysis_target",
            "current_assessment": "quality_metrics",
            "findings": "identified_issues",
            "recommendations": "improvement_suggestions",
            "priority_analysis": "risk_priority_summary"
        },
        
        required_data_points=["analysis_target", "identified_issues"],
        optional_data_points=["quality_metrics", "improvement_suggestions", "risk_priority_summary"],
        fallback_values={
            "current_assessment": "評価データの収集中にエラーが発生しました",
            "findings": "分析で特筆すべき事項は見つかりませんでした",
            "recommendations": "現時点で推奨する改善策はありません",
            "priority_analysis": "優先度の評価は実行されませんでした"
        }
    ),
    
    TaskProfileType.CREATION_REQUEST: TaskProfileTemplate(
        profile_type=TaskProfileType.CREATION_REQUEST,
        structure="""## 🛠️ 作成プラン: {creation_target}

### 📋 作成方針
{approach}

### 🎯 実装内容
{implementation_plan}

### ⚠️ 注意事項
{considerations}

### 📝 次のステップ
{next_steps}""",
        
        data_mapping={
            "creation_target": "target_name",
            "approach": "creation_approach",
            "implementation_plan": "implementation_details",
            "considerations": "risk_considerations",
            "next_steps": "follow_up_actions"
        },
        
        required_data_points=["target_name", "implementation_details"],
        optional_data_points=["creation_approach", "risk_considerations", "follow_up_actions"],
        fallback_values={
            "approach": "標準的なアプローチで作成します",
            "implementation_plan": "実装詳細の生成中にエラーが発生しました",
            "considerations": "特別な注意事項はありません",
            "next_steps": "作成後にテストと検証を実行してください"
        }
    ),
    
    TaskProfileType.MODIFICATION_REQUEST: TaskProfileTemplate(
        profile_type=TaskProfileType.MODIFICATION_REQUEST,
        structure="""## ✏️ 変更プラン: {target_name}

### 🎯 変更対象
{target_files}

### 📝 変更内容
{change_details}

### ⚠️ 影響範囲
{impact_analysis}

### 🔒 安全対策
{safety_measures}""",
        
        data_mapping={
            "target_name": "modification_target",
            "target_files": "affected_files_list",
            "change_details": "modification_details",
            "impact_analysis": "change_impact_summary",
            "safety_measures": "backup_and_safety_info"
        },
        
        required_data_points=["modification_target", "modification_details"],
        optional_data_points=["affected_files_list", "change_impact_summary", "backup_and_safety_info"],
        fallback_values={
            "target_files": "対象ファイルの特定中にエラーが発生しました",
            "change_details": "変更詳細の分析中にエラーが発生しました",
            "impact_analysis": "影響範囲の分析は実行されませんでした",
            "safety_measures": "標準的なバックアップ手順に従ってください"
        }
    ),
    
    TaskProfileType.SEARCH_REQUEST: TaskProfileTemplate(
        profile_type=TaskProfileType.SEARCH_REQUEST,
        structure="""## 🔍 検索結果: {search_query}

### 📂 発見ファイル
{found_files}

### 💻 関連コード
{relevant_code}

### 📊 検索サマリー
{search_summary}

### 🔗 関連情報
{related_info}""",
        
        data_mapping={
            "search_query": "search_term",
            "found_files": "discovered_files_list",
            "relevant_code": "code_snippets",
            "search_summary": "search_statistics",
            "related_info": "additional_findings"
        },
        
        required_data_points=["search_term", "discovered_files_list"],
        optional_data_points=["code_snippets", "search_statistics", "additional_findings"],
        fallback_values={
            "found_files": "検索条件に一致するファイルは見つかりませんでした",
            "relevant_code": "関連するコードスニペットは見つかりませんでした",
            "search_summary": "検索は実行されましたが、結果の集計中にエラーが発生しました",
            "related_info": "追加の関連情報はありません"
        }
    ),
    
    TaskProfileType.GUIDANCE_REQUEST: TaskProfileTemplate(
        profile_type=TaskProfileType.GUIDANCE_REQUEST,
        structure="""## 📖 ガイド: {topic}

### 🔧 前提条件
{prerequisites}

### 📋 実行手順
{steps}

### ⚠️ よくある問題
{common_issues}

### 💡 ヒントとコツ
{tips_and_tricks}""",
        
        data_mapping={
            "topic": "guidance_topic",
            "prerequisites": "requirement_list",
            "steps": "step_by_step_guide",
            "common_issues": "troubleshooting_info",
            "tips_and_tricks": "best_practices"
        },
        
        required_data_points=["guidance_topic", "step_by_step_guide"],
        optional_data_points=["requirement_list", "troubleshooting_info", "best_practices"],
        fallback_values={
            "prerequisites": "特別な前提条件はありません",
            "steps": "手順の生成中にエラーが発生しました",
            "common_issues": "既知の問題はありません",
            "tips_and_tricks": "追加のヒントは現在利用できません"
        }
    )
}


def get_template(profile_type: TaskProfileType) -> TaskProfileTemplate:
    """TaskProfileTypeに対応するテンプレートを取得
    
    Args:
        profile_type: TaskProfileの種別
        
    Returns:
        対応するテンプレート
        
    Raises:
        KeyError: 未対応のTaskProfileTypeの場合
    """
    if profile_type not in TASK_PROFILE_TEMPLATES:
        raise KeyError(f"未対応のTaskProfileType: {profile_type}")
    
    return TASK_PROFILE_TEMPLATES[profile_type]


def list_available_profiles() -> List[TaskProfileType]:
    """利用可能なTaskProfileTypeのリストを取得
    
    Returns:
        TaskProfileTypeのリスト
    """
    return list(TASK_PROFILE_TEMPLATES.keys())


def validate_template_data(profile_type: TaskProfileType, data: Dict[str, Any]) -> bool:
    """テンプレートに必要なデータが揃っているかを検証
    
    Args:
        profile_type: TaskProfileの種別
        data: テンプレートに埋め込む予定のデータ
        
    Returns:
        必須データが全て揃っている場合True
    """
    template = get_template(profile_type)
    
    for required_point in template.required_data_points:
        if required_point not in data or not data[required_point]:
            return False
    
    return True