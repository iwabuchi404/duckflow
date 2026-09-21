"""Context Compiler — 判断に必要な情報だけを AgentState から抽出する。

Agent 自身が作った要約を信用しない（判断対象の欠落が Decision Engine に
伝播するため）。履歴から機械的に抽出する。
"""

from typing import Any

from companion.decision.models import DecisionContext


class ContextCompiler:
    """AgentState から DecisionContext を構築する。"""

    def build(self, state: Any, task: str) -> DecisionContext:
        """現在の状態から判断用コンテキストを生成する。

        Args:
            state: 現在の AgentState。
            task: 発火点となったユーザー要求本文。

        Returns:
            DecisionContext。
        """
        return DecisionContext(
            user_request=task,
            mode=getattr(getattr(state, "current_mode", None), "value", ""),
            recent_actions=self._recent_action_names(state),
        )

    @staticmethod
    def _recent_action_names(state: Any, limit: int = 8) -> list[str]:
        """履歴末尾から直近のアクション名を抽出する（最大 limit 件）。

        Args:
            state: 現在の AgentState。
            limit: 返すアクション名の最大数。

        Returns:
            アクション名のリスト（古い順）。
        """
        # Walk messages newest-first but keep within-message order intact.
        per_message: list[list[str]] = []
        for msg in reversed(state.conversation_history):
            if msg.get("role") != "assistant":
                continue
            names: list[str] = []
            for line in msg.get("content", "").splitlines():
                line = line.strip()
                if line.startswith("::"):
                    names.append(line.split()[0].lstrip(":").split("@")[0])
                elif line.startswith("- Action:") or line.startswith("Action:"):
                    names.append(line.split(":", 1)[1].strip())
            if names:
                per_message.append(names)
            if sum(len(n) for n in per_message) >= limit:
                break
        flat = [name for names in reversed(per_message) for name in names]
        return flat[:limit]
