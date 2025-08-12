"""
コンテンツ計画用のPydanticスキーマ定義

LangChainのPydanticOutputParserで使用する構造化出力モデル
JSON解析エラーを根本的に解決するため、厳密な型定義を提供
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from enum import Enum


class ComplexityLevel(str, Enum):
    """タスク複雑度レベル"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PresentationStyle(str, Enum):
    """プレゼンテーションスタイル"""
    TECHNICAL = "technical"
    USER_FRIENDLY = "user_friendly"
    DETAILED = "detailed"


class ContentStructure(BaseModel):
    """コンテンツ構造定義"""
    primary_sections: List[str] = Field(
        description="主要セクションの一覧",
        min_items=1,
        example=["概要", "詳細分析", "結論"]
    )
    data_priorities: List[str] = Field(
        description="データの重要度順位",
        min_items=1,
        example=["主要データ", "補助データ", "参考情報"]
    )
    presentation_style: PresentationStyle = Field(
        description="プレゼンテーションスタイル",
        default=PresentationStyle.USER_FRIENDLY
    )


class ContentPlan(BaseModel):
    """コンテンツ計画の完全なスキーマ"""
    
    requirement_analysis: str = Field(
        description="ユーザー要求の詳細分析結果",
        min_length=10,
        example="ユーザーはtest_step2d_graph.pyファイルの場所特定と処理内容の説明を求めています"
    )
    
    summary: str = Field(
        description="実行計画の概要",
        min_length=10,
        example="対象ファイルの読み取りと詳細な内容分析を実行"
    )
    
    steps: List[str] = Field(
        description="実行ステップの詳細リスト",
        min_items=2,
        example=["ファイル読み取り", "内容分析", "説明生成"]
    )
    
    required_tools: List[str] = Field(
        description="必要なツールのリスト",
        min_items=1,
        example=["read_file", "llm_analysis"]
    )
    
    expected_files: List[str] = Field(
        description="処理対象ファイルのリスト",
        default_factory=list,
        example=["test_step2d_graph.py", "requirements.txt"]
    )
    
    complexity: ComplexityLevel = Field(
        description="タスクの複雑度レベル",
        default=ComplexityLevel.MEDIUM
    )
    
    success_criteria: str = Field(
        description="成功基準の定義",
        min_length=10,
        example="対象ファイルの機能と使用方法が明確に説明されている"
    )
    
    risks: List[str] = Field(
        description="予想されるリスクのリスト",
        default_factory=list,
        example=["ファイル読み取りエラー", "依存関係不明"]
    )
    
    information_needs: List[str] = Field(
        description="必要な情報のリスト",
        default_factory=list,
        example=["ファイル内容", "依存関係", "実行環境"]
    )
    
    content_structure: ContentStructure = Field(
        description="コンテンツ構造の定義",
        default_factory=lambda: ContentStructure(
            primary_sections=["概要", "詳細"],
            data_priorities=["主要情報"],
            presentation_style=PresentationStyle.USER_FRIENDLY
        )
    )
    
    confidence: float = Field(
        description="計画の信頼度（0.0-1.0）",
        ge=0.0,
        le=1.0,
        default=0.8,
        example=0.85
    )
    
    @validator('steps')
    def steps_must_not_be_empty(cls, v):
        """ステップが空でないことを検証"""
        if not v or any(not step.strip() for step in v):
            raise ValueError('steps must not be empty and each step must contain content')
        return v
    
    @validator('required_tools')
    def validate_required_tools(cls, v):
        """必要ツールの妥当性を検証"""
        valid_tools = {
            'read_file', 'write_file', 'list_files', 'get_file_info',
            'llm_analysis', 'search_code', 'create_directory'
        }
        for tool in v:
            if tool not in valid_tools:
                # 警告のみ、エラーにはしない（柔軟性を保つ）
                pass
        return v
    
    @validator('expected_files')
    def validate_expected_files(cls, v):
        """期待ファイルの妥当性を検証"""
        valid_files = []
        for file_path in v:
            # 基本的なファイルパス検証（過度な除外を修正）
            if (isinstance(file_path, str) and 
                file_path.strip() and
                # ファイルパスの基本的な妥当性チェックのみ（過度な除外は無効ファイルを生む）
                ('.' in file_path or '/' in file_path or '\\' in file_path)):
                valid_files.append(file_path.strip())
                print(f"[PYDANTIC_VALIDATOR] ファイル承認: '{file_path.strip()}'")
            else:
                print(f"[PYDANTIC_VALIDATOR] ファイル除外: '{file_path}' (理由: 妥当性チェック失敗)")
        print(f"[PYDANTIC_VALIDATOR] 最終有効ファイル: {valid_files}")
        return valid_files
    
    class Config:
        """Pydantic設定"""
        use_enum_values = True
        validate_assignment = True
        extra = "forbid"  # 余分なフィールドを禁止