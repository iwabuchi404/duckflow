"""Context Compiler — 判断に必要な情報だけを AgentState から抽出する。

Agent 自身が作った要約を信用しない（判断対象の欠落が Decision Engine に
伝播するため）。履歴から機械的に抽出する。
"""

from pathlib import Path
from typing import Any

from companion.decision.models import DecisionContext

# file_excerpts の上限: 直近ファイル数 × 各最大行数
_MAX_EXCERPT_FILES = 3
_MAX_EXCERPT_LINES = 40
_MAX_WORKSPACE_FILES = 60


class ContextCompiler:
    """AgentState から DecisionContext を構築する。"""

    def build(
        self, state: Any, task: str, workspace_root: str | None = None
    ) -> DecisionContext:
        """現在の状態から判断用コンテキストを生成する。

        Args:
            state: 現在の AgentState。
            task: 発火点となったユーザー要求本文。
            workspace_root: workspace のルートパス。指定時は直下の
                ファイル一覧を context に含める（探索後発火用）。

        Returns:
            DecisionContext。
        """
        return DecisionContext(
            user_request=task,
            mode=getattr(getattr(state, "current_mode", None), "value", ""),
            recent_actions=self._recent_action_names(state),
            workspace_files=self._workspace_files(workspace_root),
            file_excerpts=self._file_excerpts(state),
            current_plan=self._plan_summary(state),
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

    @staticmethod
    def _workspace_files(workspace_root: str | None) -> list[str]:
        """workspace 直下のエントリ一覧を返す（ディレクトリは末尾 / 付き）。

        Args:
            workspace_root: workspace ルートパス。None なら空リスト。

        Returns:
            ソート済みエントリ名のリスト（最大 _MAX_WORKSPACE_FILES 件）。
        """
        if not workspace_root:
            return []
        try:
            root = Path(workspace_root)
            if not root.is_dir():
                return []
            entries = []
            for item in sorted(root.iterdir()):
                if item.name.startswith(".") or item.name == "__pycache__":
                    continue
                entries.append(item.name + ("/" if item.is_dir() else ""))
            return entries[:_MAX_WORKSPACE_FILES]
        except OSError:
            return []

    @staticmethod
    def _file_excerpts(state: Any) -> list[str]:
        """直近の read_file ツール結果からファイル抜粋を抽出する。

        TOOL_RESULT メッセージ内の `::read_file @path` と `content:` 行を
        機械的に拾う。各ファイルは _MAX_EXCERPT_LINES 行まで、
        合計 _MAX_EXCERPT_FILES 件まで。

        Args:
            state: 現在の AgentState。

        Returns:
            "path:\\n<excerpt>" 形式の文字列リスト（新しい順）。
        """
        excerpts: list[str] = []
        for msg in reversed(state.conversation_history):
            if len(excerpts) >= _MAX_EXCERPT_FILES:
                break
            content = msg.get("content", "")
            if "::read_file" not in content:
                continue
            path = ""
            body_lines: list[str] = []
            in_block = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("::read_file"):
                    path = stripped.split("@", 1)[-1].strip()
                elif stripped == "<<<":
                    in_block = True
                elif stripped == ">>>":
                    in_block = False
                elif in_block and stripped.startswith("content:"):
                    body_lines.append(stripped[len("content:") :].lstrip())
                elif in_block and body_lines:
                    body_lines.append(line)
            if body_lines:
                excerpt = "\n".join(body_lines[:_MAX_EXCERPT_LINES])
                excerpts.append(f"{path or '(unknown)'}:\n{excerpt}")
        return excerpts

    @staticmethod
    def _plan_summary(state: Any) -> str:
        """現在の plan を goal + step 名の1行要約にする。

        Args:
            state: 現在の AgentState。

        Returns:
            plan 要約文字列。plan がなければ空文字列。
        """
        plan = getattr(state, "current_plan", None)
        if plan is None:
            return ""
        steps = getattr(plan, "steps", [])
        step_titles = "; ".join(getattr(s, "title", "") for s in steps)
        goal = getattr(plan, "goal", "")
        return f"{goal} | steps: {step_titles}" if step_titles else goal
