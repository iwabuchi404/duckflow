"""
テンプレートシステム

5ノードアーキテクチャの応答生成ノードで使用される
TaskProfileベースのテンプレートとデータ変換機能
"""

from .task_profile_templates import (
    TaskProfileType,
    TaskProfileTemplate,
    TASK_PROFILE_TEMPLATES,
    get_template,
    list_available_profiles,
    validate_template_data
)

__all__ = [
    'TaskProfileType',
    'TaskProfileTemplate', 
    'TASK_PROFILE_TEMPLATES',
    'get_template',
    'list_available_profiles',
    'validate_template_data'
]