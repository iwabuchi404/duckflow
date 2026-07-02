"""
Tier運転プロファイル: モデルの強さに応じてプロンプト量・自律性・エスカレーション
閾値などを配給するための単一オブジェクト。

設計: docs/agent_surface_redesign_design.md §5
原則: tier を知るのはこのモジュールの resolve_tier_profile() だけ。
他のコンポーネントは TierProfile の具体値のみを参照し、tier 文字列や
if-tier 分岐を自前で持たない。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from companion.config.config_loader import config as _default_config

TIER_LOW = "low"
TIER_MID = "mid"
TIER_HIGH = "high"
VALID_TIERS = {TIER_LOW, TIER_MID, TIER_HIGH}

# TierProfile のうち、available_models の各エントリで個別上書きできるフィールド名。
_OVERRIDABLE_FIELDS = {
    "max_loops",
    "checkin_interval",
    "repo_map_token_budget",
    "escalation_threshold",
    "unknown_model_context_length",
}


class TierProfile(BaseModel):
    """モデル tier ごとの運転プロファイル。

    各フィールドの意味は docs/agent_surface_redesign_design.md §5.2 の表を参照。
    数値は設計時点の初期値であり、Phase 5 でベンチにより較正する。
    """

    model_config = {"frozen": True}

    tier: str = Field(description="解決された tier ('low' / 'mid' / 'high')")
    max_loops: int = Field(description="自律ループの最大反復回数の目安")
    checkin_interval: Optional[int] = Field(
        default=None,
        description="この回数ごとにチェックインを促す。None は強制チェックインなし（high tier）",
    )
    repo_map_token_budget: int = Field(description="repo map 注入のトークン予算")
    escalation_threshold: Optional[int] = Field(
        default=None,
        description="編集が何回失敗したら中モデルへ自動委譲するか。None はエスカレーションなし",
    )
    unknown_model_context_length: int = Field(
        description="フォールバックテーブルにもないモデルのコンテキスト長既定値"
    )
    history_compression: str = Field(
        description="履歴圧縮の強度 ('strong' / 'standard')"
    )
    few_shot_variant: str = Field(
        description="few-shot の分量 ('short' / 'standard' / 'minimal')"
    )
    tool_description_variant: str = Field(
        description="ツール説明の詳細度 ('concise' / 'standard')"
    )
    edit_format_hint: str = Field(
        description="推奨編集フォーマット ('replace_function_first' / 'search_replace')"
    )


# tier 別デフォルト値（docs/agent_surface_redesign_design.md §5.2 準拠）
_TIER_DEFAULTS: Dict[str, TierProfile] = {
    TIER_LOW: TierProfile(
        tier=TIER_LOW,
        max_loops=10,
        checkin_interval=5,
        repo_map_token_budget=500,
        escalation_threshold=1,
        unknown_model_context_length=16_000,
        history_compression="strong",
        few_shot_variant="short",
        tool_description_variant="concise",
        edit_format_hint="replace_function_first",
    ),
    TIER_MID: TierProfile(
        tier=TIER_MID,
        max_loops=18,
        checkin_interval=10,
        repo_map_token_budget=1500,
        escalation_threshold=2,
        unknown_model_context_length=32_000,
        history_compression="standard",
        few_shot_variant="standard",
        tool_description_variant="standard",
        edit_format_hint="search_replace",
    ),
    TIER_HIGH: TierProfile(
        tier=TIER_HIGH,
        max_loops=35,
        checkin_interval=None,
        repo_map_token_budget=1500,
        escalation_threshold=None,
        unknown_model_context_length=32_000,
        history_compression="standard",
        few_shot_variant="minimal",
        tool_description_variant="standard",
        edit_format_hint="search_replace",
    ),
}


def _find_model_entry(
    available_models: List[Dict[str, Any]], model_name: str
) -> Optional[Dict[str, Any]]:
    """model 名が一致する available_models エントリを探す。

    Args:
        available_models: duckflow.yaml の llm.available_models リスト。
        model_name: 現在使用中のモデル識別子。

    Returns:
        一致したエントリの辞書。見つからなければ None。
    """
    for entry in available_models:
        if entry.get("model") == model_name:
            return entry
    return None


def resolve_tier_profile(
    model_name: str,
    provider: Optional[str] = None,
    cfg: Any = None,
) -> TierProfile:
    """指定モデルの TierProfile を解決する。

    解決優先順位:
        1. available_models 内で model 名が一致するエントリの `tier` フィールド
        2. 一致するエントリが `tier` を持たない、またはエントリ自体が
           見つからない場合は "low"（保守的既定。DEFAULT_CONTEXT_LENGTH の
           過大既定と同じ轍を踏まないため — 未知のモデルは弱いモデルとして
           扱う）

    さらに、一致したエントリに `_OVERRIDABLE_FIELDS` のフィールドが
    直接指定されていれば、tier デフォルト値をそのモデル個別の値で上書きする。

    Args:
        model_name: 現在使用中のモデル識別子（例: "qwen/qwen3.6-35b-a3b"）。
        provider: プロバイダー名（現時点では未使用。将来の絞り込み用に予約）。
        cfg: ConfigLoader 互換オブジェクト。省略時はグローバル設定を使用。

    Returns:
        解決済みの TierProfile。
    """
    cfg = cfg if cfg is not None else _default_config
    available_models = cfg.get("llm.available_models", []) or []
    entry = _find_model_entry(available_models, model_name)

    tier = TIER_LOW
    if entry is not None:
        candidate = entry.get("tier")
        if candidate in VALID_TIERS:
            tier = candidate

    base = _TIER_DEFAULTS[tier]

    if entry is not None:
        overrides = {
            field: entry[field] for field in _OVERRIDABLE_FIELDS if field in entry
        }
        if overrides:
            base = base.model_copy(update=overrides)

    return base
