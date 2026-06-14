"""編集フォーマット A/B ベンチマークのタスクデータセット。

各タスクは「初期ファイル内容」「意味的な編集（find→replace のペア列）」「期待結果」を持つ。
ベンチランナーはこの抽象的な編集を各フォーマット（マーカー / 従来 find:）の
具体的なコンテンツ文字列にレンダリングし、edit_file に適用して成否を測る。

カテゴリ（docs/edit_format_search_replace_design.md §5）:
- normal:        通常の単一/複数行編集
- common_indent: 共通インデント領域（メソッド内部）— 従来形式の欠陥が発火
- long_local:    長いファイルの局所編集
- conflict:      git コンフリクトファイルの編集 — ルーティング検証
- format_echo:   フォーマット記号を含むファイルの編集 — 自己参照衝突
"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class EditTask:
    """単一の編集ベンチマークタスク。

    Attributes:
        id: タスク識別子
        category: タスクカテゴリ（normal / common_indent / long_local / conflict / format_echo）
        initial_content: 編集前のファイル内容
        edits: (find, replace) のペア列。意味的な編集内容
        expected_content: 編集成功時に期待されるファイル内容
        expect_routed_away: True の場合、マーカー形式では適用を拒否（ルーティング）されるのが正解
        note: 補足説明
    """
    id: str
    category: str
    initial_content: str
    edits: List[Tuple[str, str]]
    expected_content: str
    expect_routed_away: bool = False
    note: str = ""


# データセット本体。実運用前に 20〜30 件まで拡充する想定（現状は各カテゴリの代表）。
TASKS: List[EditTask] = [
    EditTask(
        id="normal_single_line",
        category="normal",
        initial_content="x = 1\ny = 2\nz = 3\n",
        edits=[("y = 2", "y = 20")],
        expected_content="x = 1\ny = 20\nz = 3\n",
        note="単一行の置換",
    ),
    EditTask(
        id="common_indent_method",
        category="common_indent",
        initial_content=(
            "class Calc:\n"
            "    def add(self, a, b):\n"
            "        return a + b\n"
        ),
        edits=[(
            "    def add(self, a, b):\n        return a + b",
            "    def add(self, a: int, b: int) -> int:\n        return a + b",
        )],
        expected_content=(
            "class Calc:\n"
            "    def add(self, a: int, b: int) -> int:\n"
            "        return a + b\n"
        ),
        note="共通インデント領域。従来の find:| 形式が壊れやすいケース",
    ),
    EditTask(
        id="long_local_edit",
        category="long_local",
        initial_content="".join(f"line_{i} = {i}\n" for i in range(1, 41)),
        edits=[("line_25 = 25", "line_25 = 2500")],
        expected_content="".join(
            (f"line_{i} = 2500\n" if i == 25 else f"line_{i} = {i}\n")
            for i in range(1, 41)
        ),
        note="40行ファイルの中央付近を1箇所編集",
    ),
    EditTask(
        id="multi_edit",
        category="normal",
        initial_content="a = 1\nb = 2\nc = 3\n",
        edits=[("a = 1", "a = 100"), ("c = 3", "c = 300")],
        expected_content="a = 100\nb = 2\nc = 300\n",
        note="同一ファイルへの複数編集",
    ),
    EditTask(
        id="conflict_file_edit",
        category="conflict",
        initial_content=(
            "def f():\n"
            "<<<<<<< HEAD\n"
            "    return 1\n"
            "=======\n"
            "    return 2\n"
            ">>>>>>> branch\n"
        ),
        edits=[("    return 1", "    return 3")],
        expected_content="",  # マーカー形式では適用されない（ルーティングで拒否が正解）
        expect_routed_away=True,
        note="git コンフリクト中のファイル。マーカー形式は拒否されるべき",
    ),
    EditTask(
        id="format_echo_file",
        category="format_echo",
        initial_content=(
            "DELIMITER = '>>>'\n"
            "def parse():\n"
            "    return DELIMITER\n"
        ),
        edits=[("    return DELIMITER", "    return DELIMITER  # parsed")],
        expected_content=(
            "DELIMITER = '>>>'\n"
            "def parse():\n"
            "    return DELIMITER  # parsed\n"
        ),
        note="本文にフォーマット記号(>>>)を含むファイルの編集",
    ),
]


def render_marker(edits: List[Tuple[str, str]]) -> str:
    """編集ペア列を SEARCH/REPLACE マーカー形式のコンテンツ文字列にレンダリングする。

    Args:
        edits: (find, replace) のペア列

    Returns:
        ::edit_file のコンテンツブロックに入れる文字列
    """
    blocks = []
    for find, replace in edits:
        blocks.append(
            f"<<<<<<< SEARCH\n{find}\n=======\n{replace}\n>>>>>>> REPLACE"
        )
    return "\n".join(blocks)


def render_legacy(edits: List[Tuple[str, str]]) -> str:
    """編集ペア列を従来の find:/replace:（%%% 区切り）形式にレンダリングする。

    Args:
        edits: (find, replace) のペア列

    Returns:
        ::edit_file のコンテンツブロックに入れる文字列
    """
    def _indent(text: str) -> str:
        return "\n".join("    " + line for line in text.split("\n"))

    segs = []
    for find, replace in edits:
        segs.append(f"find: |\n{_indent(find)}\nreplace: |\n{_indent(replace)}")
    return "\n%%%\n".join(segs)
