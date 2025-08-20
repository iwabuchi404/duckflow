#!/usr/bin/env python3
"""
プロンプトコンテキストビルダー - 構造化コンテキスト管理

codecrafterから分離し、companion内で完結するように調整
"""

import json
import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ContextSection:
    """コンテキストセクション"""
    name: str
    content: str
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'name': self.name,
            'content': self.content,
            'priority': self.priority,
            'metadata': self.metadata
        }


@dataclass
class PromptContext:
    """プロンプトコンテキスト"""
    title: str
    sections: List[ContextSection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'title': self.title,
            'sections': [section.to_dict() for section in self.sections],
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class PromptContextBuilder:
    """プロンプトコンテキストビルダー"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.contexts: Dict[str, PromptContext] = {}
        
        self.logger.info("PromptContextBuilder初期化完了")
    
    def create_context(self, title: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """新しいコンテキストを作成"""
        try:
            context_id = f"ctx_{len(self.contexts)}_{datetime.now().timestamp()}"
            
            context = PromptContext(
                title=title,
                metadata=metadata or {}
            )
            
            self.contexts[context_id] = context
            self.logger.info(f"コンテキスト作成: {title} (ID: {context_id})")
            return context_id
            
        except Exception as e:
            self.logger.error(f"コンテキスト作成エラー: {e}")
            return ""
    
    def add_section(self, context_id: str, name: str, content: str, 
                    priority: int = 0, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """セクションを追加"""
        try:
            if context_id not in self.contexts:
                raise ValueError(f"コンテキストが見つかりません: {context_id}")
            
            context = self.contexts[context_id]
            
            section = ContextSection(
                name=name,
                content=content,
                priority=priority,
                metadata=metadata or {}
            )
            
            context.sections.append(section)
            context.updated_at = datetime.now()
            
            # 優先度でソート
            context.sections.sort(key=lambda x: x.priority, reverse=True)
            
            self.logger.info(f"セクション追加: {name} (優先度: {priority})")
            return True
            
        except Exception as e:
            self.logger.error(f"セクション追加エラー: {e}")
            return False
    
    def get_context(self, context_id: str) -> Optional[PromptContext]:
        """コンテキストを取得"""
        return self.contexts.get(context_id)
    
    def from_agent_state(self, agent_state) -> str:
        """エージェント状態から一貫性のあるリッチなコンテキストを作成"""
        try:
            state_info = {
                'step': getattr(agent_state, 'step', 'unknown').value,
                'status': getattr(agent_state, 'status', 'unknown').value,
            }
            title = f"Agent State Context - {state_info['step']}.{state_info['status']}"
            context_id = self.create_context(title, state_info)

            # --- Main Context の構築 ---

            # 1. 基本状態
            self.add_section(context_id, "現在の状況", f"ステップ: {state_info['step']}, ステータス: {state_info['status']}", priority=10)

            # 2. 固定5項目
            fixed_five_items = {
                "目標": getattr(agent_state, 'goal', ''),
                "なぜ今やるのか": getattr(agent_state, 'why_now', ''),
                "制約": getattr(agent_state, 'constraints', []),
                "直近の計画": getattr(agent_state, 'plan_brief', []),
                "未解決の問い": getattr(agent_state, 'open_questions', [])
            }
            fixed_five_content = "\n".join([f"- {k}: {v if isinstance(v, str) else ', '.join(v)}" for k, v in fixed_five_items.items() if v])
            if fixed_five_content:
                self.add_section(context_id, "文脈の核（固定5項目）", fixed_five_content, priority=9)

            # 3. 最新のアクティビティ（永続短期記憶から）
            short_term_memory = getattr(agent_state, 'short_term_memory', {})
            last_read_file = short_term_memory.get('last_read_file')
            if last_read_file:
                activity_content = f"直前にファイル「{last_read_file.get('path')}」を読み込みました。\n要約: {last_read_file.get('summary', 'なし')}"
                self.add_section(context_id, "最新のアクティビティ", activity_content, priority=8)

            # 4. 直近の会話の流れ
            history = getattr(agent_state, 'conversation_history', [])
            if history:
                recent_messages = []
                # 最新のユーザーとアシスタントのペアを1つ取得
                user_msg, assistant_msg = None, None
                for msg in reversed(history):
                    if msg.role == 'assistant' and not assistant_msg:
                        assistant_msg = msg.content
                    if msg.role == 'user' and not user_msg:
                        user_msg = msg.content
                    if user_msg and assistant_msg:
                        break
                if user_msg:
                    conversation_flow = f"ユーザー: {user_msg[:150]}...\nアシスタント: {assistant_msg[:200] if assistant_msg else '(応答待ち)'}..."
                    self.add_section(context_id, "直近の会話の流れ", conversation_flow, priority=7)

            self.logger.info(f"エージェント状態からリッチコンテキスト作成: {context_id}")
            return context_id
            
        except Exception as e:
            self.logger.error(f"エージェント状態からのコンテキスト作成エラー: {e}", exc_info=True)
            return ""
    
    def build_prompt(self, context_id: str, format_type: str = "text") -> str:
        """プロンプトを構築"""
        try:
            if context_id not in self.contexts:
                raise ValueError(f"コンテキストが見つかりません: {context_id}")
            
            context = self.contexts[context_id]
            
            if format_type == "json":
                return self._build_json_prompt(context)
            elif format_type == "markdown":
                return self._build_markdown_prompt(context)
            else:
                return self._build_text_prompt(context)
                
        except Exception as e:
            self.logger.error(f"プロンプト構築エラー: {e}")
            return f"プロンプト構築エラー: {str(e)}"
    
    def _build_text_prompt(self, context: PromptContext) -> str:
        """テキスト形式のプロンプトを構築"""
        lines = [f"# {context.title}", ""]
        
        for section in context.sections:
            lines.append(f"## {section.name}")
            lines.append(section.content)
            lines.append("")
        
        return "\n".join(lines)
    
    def _build_markdown_prompt(self, context: PromptContext) -> str:
        """Markdown形式のプロンプトを構築"""
        lines = [f"# {context.title}", ""]
        
        for section in context.sections:
            lines.append(f"## {section.name}")
            lines.append(section.content)
            lines.append("")
        
        return "\n".join(lines)
    
    def _build_json_prompt(self, context: PromptContext) -> str:
        """JSON形式のプロンプトを構築"""
        data = {
            'title': context.title,
            'sections': [section.to_dict() for section in context.sections],
            'metadata': context.metadata
        }
        
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    def update_section(self, context_id: str, section_name: str, 
                       new_content: str, new_priority: Optional[int] = None) -> bool:
        """セクションを更新"""
        try:
            if context_id not in self.contexts:
                raise ValueError(f"コンテキストが見つかりません: {context_id}")
            
            context = self.contexts[context_id]
            
            for section in context.sections:
                if section.name == section_name:
                    section.content = new_content
                    if new_priority is not None:
                        section.priority = new_priority
                    
                    context.updated_at = datetime.now()
                    
                    # 優先度でソート
                    context.sections.sort(key=lambda x: x.priority, reverse=True)
                    
                    self.logger.info(f"セクション更新: {section_name}")
                    return True
            
            self.logger.warning(f"セクションが見つかりません: {section_name}")
            return False
            
        except Exception as e:
            self.logger.error(f"セクション更新エラー: {e}")
            return False
    
    def remove_section(self, context_id: str, section_name: str) -> bool:
        """セクションを削除"""
        try:
            if context_id not in self.contexts:
                raise ValueError(f"コンテキストが見つかりません: {context_id}")
            
            context = self.contexts[context_id]
            
            for i, section in enumerate(context.sections):
                if section.name == section_name:
                    del context.sections[i]
                    context.updated_at = datetime.now()
                    
                    self.logger.info(f"セクション削除: {section_name}")
                    return True
            
            self.logger.warning(f"セクションが見つかりません: {section_name}")
            return False
            
        except Exception as e:
            self.logger.error(f"セクション削除エラー: {e}")
            return False
    
    def list_contexts(self) -> List[str]:
        """コンテキスト一覧を取得"""
        return list(self.contexts.keys())
    
    def remove_context(self, context_id: str) -> bool:
        """コンテキストを削除"""
        try:
            if context_id in self.contexts:
                del self.contexts[context_id]
                self.logger.info(f"コンテキスト削除: {context_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"コンテキスト削除エラー: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        total_sections = sum(len(ctx.sections) for ctx in self.contexts.values())
        
        return {
            'total_contexts': len(self.contexts),
            'total_sections': total_sections,
            'context_names': [ctx.title for ctx in self.contexts.values()]
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """オブジェクトの状態を辞書形式で取得"""
        return {
            'contexts': {ctx_id: ctx.to_dict() for ctx_id, ctx in self.contexts.items()},
            'statistics': self.get_statistics()
        }


# グローバルインスタンス
prompt_context_builder = PromptContextBuilder()


# 便利な関数
def create_context(title: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """新しいコンテキストを作成"""
    return prompt_context_builder.create_context(title, metadata)


def add_section(context_id: str, name: str, content: str, 
                priority: int = 0, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """セクションを追加"""
    return prompt_context_builder.add_section(context_id, name, content, priority, metadata)


def build_prompt(context_id: str, format_type: str = "text") -> str:
    """プロンプトを構築"""
    return prompt_context_builder.build_prompt(context_id, format_type)


def get_context(context_id: str) -> Optional[PromptContext]:
    """コンテキストを取得"""
    return prompt_context_builder.get_context(context_id)
