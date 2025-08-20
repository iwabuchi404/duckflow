#!/usr/bin/env python3
"""
プロンプトコンパイラ - プロンプトの最適化とコンパイル

codecrafterから分離し、companion内で完結するように調整
"""

import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class PromptTemplate:
    """プロンプトテンプレート"""
    name: str
    content: str
    variables: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'name': self.name,
            'content': self.content,
            'variables': self.variables,
            'metadata': self.metadata
        }


class PromptCompiler:
    """プロンプトコンパイラ"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.templates: Dict[str, PromptTemplate] = {}
        self.compilation_cache: Dict[str, str] = {}
        
        self.logger.info("PromptCompiler初期化完了")
    
    def add_template(self, name: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """テンプレートを追加"""
        try:
            # 変数を抽出
            variables = self._extract_variables(content)
            
            template = PromptTemplate(
                name=name,
                content=content,
                variables=variables,
                metadata=metadata or {}
            )
            
            self.templates[name] = template
            self.logger.info(f"テンプレート追加: {name} (変数: {len(variables)}件)")
            return True
            
        except Exception as e:
            self.logger.error(f"テンプレート追加エラー: {e}")
            return False
    
    def _extract_variables(self, content: str) -> List[str]:
        """テンプレートから変数を抽出"""
        variables = []
        
        # {{variable}} 形式の変数を検索
        pattern = r'\{\{(\w+)\}\}'
        matches = re.findall(pattern, content)
        
        for match in matches:
            if match not in variables:
                variables.append(match)
        
        return variables
    
    def compile_prompt(self, template_name: str, variables: Dict[str, Any]) -> str:
        """プロンプトをコンパイル"""
        try:
            if template_name not in self.templates:
                raise ValueError(f"テンプレートが見つかりません: {template_name}")
            
            template = self.templates[template_name]
            
            # キャッシュキーを生成
            cache_key = f"{template_name}:{hash(str(sorted(variables.items())))}"
            
            if cache_key in self.compilation_cache:
                self.logger.debug(f"キャッシュからプロンプトを取得: {template_name}")
                return self.compilation_cache[cache_key]
            
            # プロンプトをコンパイル
            compiled_content = template.content
            
            for var_name, var_value in variables.items():
                placeholder = f"{{{{{var_name}}}}}"
                if placeholder in compiled_content:
                    compiled_content = compiled_content.replace(placeholder, str(var_value))
            
            # 未使用の変数を警告
            unused_vars = [var for var in template.variables if f"{{{{{var}}}}}" in compiled_content]
            if unused_vars:
                self.logger.warning(f"未使用の変数: {unused_vars}")
            
            # キャッシュに保存
            self.compilation_cache[cache_key] = compiled_content
            
            self.logger.debug(f"プロンプトコンパイル完了: {template_name}")
            return compiled_content
            
        except Exception as e:
            self.logger.error(f"プロンプトコンパイルエラー: {e}")
            return f"プロンプトコンパイルエラー: {str(e)}"
    
    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """テンプレートを取得"""
        return self.templates.get(name)
    
    def list_templates(self) -> List[str]:
        """テンプレート一覧を取得"""
        return list(self.templates.keys())
    
    def remove_template(self, name: str) -> bool:
        """テンプレートを削除"""
        try:
            if name in self.templates:
                del self.templates[name]
                self.logger.info(f"テンプレート削除: {name}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"テンプレート削除エラー: {e}")
            return False
    
    def clear_cache(self):
        """コンパイルキャッシュをクリア"""
        self.compilation_cache.clear()
        self.logger.info("コンパイルキャッシュをクリアしました")
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return {
            'total_templates': len(self.templates),
            'cache_size': len(self.compilation_cache),
            'template_names': list(self.templates.keys())
        }
    
    def compile_system_prompt_dto(self, prompt_data: Any) -> str:
        """システムプロンプトDTOをコンパイル
        - dict/str いずれの入力にも対応
        """
        try:
            if isinstance(prompt_data, str):
                return prompt_data
            if not isinstance(prompt_data, dict):
                return str(prompt_data)

            # システムプロンプトの基本構造
            system_prompt = prompt_data.get('system_prompt', '')
            user_context = prompt_data.get('user_context', '')
            task_description = prompt_data.get('task_description', '')

            # プロンプトを構築
            compiled_prompt = f"""システムプロンプト:
{system_prompt}

ユーザーコンテキスト:
{user_context}

タスク説明:
{task_description}

上記の情報に基づいて、適切な応答を生成してください。"""

            self.logger.info("システムプロンプトDTOコンパイル完了")
            return compiled_prompt

        except Exception as e:
            self.logger.error(f"システムプロンプトDTOコンパイルエラー: {e}")
            return f"システムプロンプトコンパイルエラー: {str(e)}"
    
    def compile_with_context(self, template_name: str, context: Dict[str, Any]) -> str:
        """コンテキスト付きでプロンプトをコンパイル"""
        try:
            if template_name not in self.templates:
                raise ValueError(f"テンプレートが見つかりません: {template_name}")
            
            template = self.templates[template_name]
            
            # コンテキスト情報を追加
            context_variables = {
                **context,
                'timestamp': context.get('timestamp', ''),
                'session_id': context.get('session_id', ''),
                'user_id': context.get('user_id', '')
            }
            
            return self.compile_prompt(template_name, context_variables)
            
        except Exception as e:
            self.logger.error(f"コンテキスト付きコンパイルエラー: {e}")
            return f"コンパイルエラー: {str(e)}"
    
    def to_dict(self) -> Dict[str, Any]:
        """オブジェクトの状態を辞書形式で取得"""
        return {
            'templates': {name: template.to_dict() for name, template in self.templates.items()},
            'statistics': self.get_statistics()
        }


# グローバルインスタンス
prompt_compiler = PromptCompiler()


# 便利な関数
def add_template(name: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """テンプレートを追加"""
    return prompt_compiler.add_template(name, content, metadata)


def compile_prompt(template_name: str, variables: Dict[str, Any]) -> str:
    """プロンプトをコンパイル"""
    return prompt_compiler.compile_prompt(template_name, variables)


def get_template(name: str) -> Optional[PromptTemplate]:
    """テンプレートを取得"""
    return prompt_compiler.get_template(name)


def list_templates() -> List[str]:
    """テンプレート一覧を取得"""
    return prompt_compiler.list_templates()
