"""Decision Engine のデータモデル。

design: Decision Engine（Context Mixer）に基づく最小構成。
Agent の履歴はそのまま渡さず、判断に必要な情報だけを
Context Compiler が抽出する。
"""

from dataclasses import dataclass, field

# 判断要求の種別。v1 は needs_clarification のみ実装。
DECISION_NEEDS_CLARIFICATION = "needs_clarification"

# 判定アクション値
ACTION_CONTINUE = "continue"
ACTION_ASK_USER = "ask_user"


@dataclass
class DecisionRequest:
    """Decision Engine への判断要求。

    Attributes:
        type: 判断の種別（"needs_clarification" 等）。
        focus: 判断の焦点（任意。例 "target_file"）。
        task: 発火点となったユーザー要求本文。
    """

    type: str
    focus: str = ""
    task: str = ""


@dataclass
class DecisionContext:
    """Context Compiler が構築する判断用コンテキスト。

    Attributes:
        user_request: 現在のユーザー要求本文。
        mode: 現在の Agent モード（planning/task 等）。
        recent_actions: 直近に実行されたアクション名の列。
        known_facts: 既知の事実（将来拡張）。
        assumptions: 未解決の仮定（将来拡張）。
        workspace_files: workspace 直下のファイル一覧（探索後発火用）。
        file_excerpts: 直近に read_file で読んだファイルの抜粋。
        current_plan: 現在の plan の要約（goal + step 名）。
    """

    user_request: str
    mode: str = ""
    recent_actions: list[str] = field(default_factory=list)
    known_facts: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    # v2 (post-exploration gate): material gathered during exploration.
    workspace_files: list[str] = field(default_factory=list)
    file_excerpts: list[str] = field(default_factory=list)
    current_plan: str = ""


@dataclass
class DecisionResult:
    """Decision Provider の判定結果。

    Attributes:
        action: "continue" / "ask_user" / "replan" / "stop" / "review"。
        focus: 判定が特定した未解決点（ask_user 時）。
        reason: 判定理由（プロバイダ出力、あれば）。
        raw: プロバイダの生出力（検証用）。
    """

    action: str = ACTION_CONTINUE
    focus: str = ""
    reason: str = ""
    raw: str = ""
