"""編集フォーマット A/B ベンチマークランナー。

docs/edit_format_search_replace_design.md §5 の2次元計測（形式 × モデルtier）。

2つのモード:
- offline（デフォルト）: モデルを呼ばず、各タスクの編集を各フォーマットに
  決定的にレンダリングして edit_file に適用し、適用層の成否を測る。
  API鍵不要。マーカー形式の適用パイプラインと従来形式の差分（特に共通インデント
  領域での挙動差）を回帰的に検証できる。「現行 find:| のベースライン」もこれで取る。
- online（--online）: 実モデルに「このファイルをこう編集して」と各フォーマットで
  指示し、生成された編集を適用して成否を測る。API鍵とduckflow.yamlのモデル設定が必要。
  tier→形式マッピング（§7.2）と降格閾値（§7.3）の実証に使う。

使い方:
    uv run python -X utf8 -m benchmarks.edit_format_bench
    uv run python -X utf8 -m benchmarks.edit_format_bench --formats marker legacy
    uv run python -X utf8 -m benchmarks.edit_format_bench --online --model gpt-4o-mini --provider openai
"""

import argparse
import asyncio
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from companion.tools.file_ops import FileOps
from benchmarks.edit_tasks import TASKS, EditTask, render_marker, render_legacy


FORMATS = {
    "marker": render_marker,
    "legacy": render_legacy,
}


def _make_ops() -> FileOps:
    """一時ディレクトリをワークスペースにした FileOps を生成する。

    Returns:
        テスト用に隔離された FileOps インスタンス
    """
    ops = FileOps()
    ops.workspace_root = Path(tempfile.mkdtemp())
    return ops


async def _run_task_offline(task: EditTask, fmt: str) -> Dict[str, object]:
    """1タスクを1フォーマットでオフライン適用し、結果を判定する。

    Args:
        task: 対象の編集タスク
        fmt: フォーマット名（"marker" / "legacy"）

    Returns:
        {"id", "format", "applied", "routed", "passed", "detail"} の辞書
    """
    ops = _make_ops()
    path = "target.py"
    (ops.workspace_root / path).write_text(task.initial_content, encoding="utf-8")

    content = FORMATS[fmt](task.edits)
    result = await ops.edit_file(path=path, content=content)
    applied = result.startswith("Successfully edited")
    after = (ops.workspace_root / path).read_text(encoding="utf-8")

    # edit_file は _sanitize_content により末尾改行を正規化で落とすため、
    # 末尾改行差は無視して比較する（編集の正否のみを評価する）。
    def _norm(text: str) -> str:
        return text.rstrip("\n")

    if task.expect_routed_away:
        # ルーティングで拒否され、かつファイルが変更されていなければ正解
        routed = ("conflict_markers_in_target" in result) or ("marker_leak_in_replace" in result)
        passed = routed and (_norm(after) == _norm(task.initial_content))
        detail = "" if passed else f"expected routing/no-change, got: {result.splitlines()[0] if result else '?'}"
        return {"id": task.id, "format": fmt, "applied": applied, "routed": routed,
                "passed": passed, "detail": detail}

    # 通常タスク: 適用成功かつ内容一致が正解
    passed = applied and (_norm(after) == _norm(task.expected_content))
    detail = ""
    if not passed:
        if not applied:
            detail = f"not applied: {result.splitlines()[0] if result else '?'}"
        else:
            detail = "applied but content mismatch"
    return {"id": task.id, "format": fmt, "applied": applied, "routed": False,
            "passed": passed, "detail": detail}


async def _run_task_online(task: EditTask, fmt: str, client) -> Dict[str, object]:
    """1タスクを1フォーマットでオンライン（実モデル）適用する骨組み。

    モデルに各フォーマットで編集を生成させ、抽出して edit_file に適用する。
    本体プロンプト設計は実装途中のため、現時点では NotImplementedError を返す
    プレースホルダ。online 計測を行う際にここを埋める。

    Args:
        task: 対象の編集タスク
        fmt: フォーマット名
        client: LLMClient インスタンス

    Returns:
        オフラインと同形式の結果辞書
    """
    raise NotImplementedError(
        "online モードのモデル呼び出しは未実装です。"
        "duckflow.yaml のモデル設定とAPI鍵を用意し、ここに "
        "「ファイル内容＋編集指示→各フォーマットで編集生成→抽出→edit_file適用」の "
        "プロンプトを実装してください。"
    )


def _print_report(rows: List[Dict[str, object]], formats: List[str]) -> None:
    """計測結果を集計してコンソールに表示する。

    Args:
        rows: 各 (タスク × フォーマット) の結果辞書のリスト
        formats: 計測したフォーマット名のリスト
    """
    print("\n=== Edit Format Benchmark ===\n")
    # フォーマット別の合格率
    for fmt in formats:
        fmt_rows = [r for r in rows if r["format"] == fmt]
        passed = sum(1 for r in fmt_rows if r["passed"])
        total = len(fmt_rows)
        rate = (passed / total * 100) if total else 0.0
        print(f"[{fmt:6}] {passed}/{total} passed ({rate:.0f}%)")

    # 失敗の詳細
    failures = [r for r in rows if not r["passed"]]
    if failures:
        print("\n--- Failures ---")
        for r in failures:
            print(f"  {r['id']} [{r['format']}]: {r['detail']}")

    # カテゴリ別マトリクス（形式 × 合否）
    print("\n--- Per-task ---")
    ids = sorted({r["id"] for r in rows})
    header = "task".ljust(24) + "".join(f.ljust(8) for f in formats)
    print(header)
    for tid in ids:
        line = tid.ljust(24)
        for fmt in formats:
            r = next((x for x in rows if x["id"] == tid and x["format"] == fmt), None)
            mark = "?" if r is None else ("OK" if r["passed"] else "FAIL")
            line += mark.ljust(8)
        print(line)
    print()


async def main_async(formats: List[str], online: bool,
                     model: Optional[str], provider: Optional[str]) -> None:
    """ベンチマークを実行してレポートを出力する。

    Args:
        formats: 計測するフォーマット名のリスト
        online: True なら実モデルで計測（要API鍵）
        model: online 時のモデルID
        provider: online 時のプロバイダー名
    """
    client = None
    if online:
        from companion.base.llm_client import LLMClient
        client = LLMClient(model=model, provider=provider)
        if getattr(client, "use_mock", False):
            print("⚠️  API鍵が見つからず Mock LLM になっています。online 計測には実鍵が必要です。")
            return

    rows: List[Dict[str, object]] = []
    for task in TASKS:
        for fmt in formats:
            # コンフリクト・ルーティングはマーカー形式のみの安全機構。
            # 従来 find:/replace: 形式には適用されないため評価対象外。
            if task.expect_routed_away and fmt != "marker":
                continue
            if online:
                row = await _run_task_online(task, fmt, client)
            else:
                row = await _run_task_offline(task, fmt)
            rows.append(row)

    _print_report(rows, formats)


def main() -> None:
    """CLI エントリーポイント。引数をパースして計測を実行する。"""
    parser = argparse.ArgumentParser(description="Edit format A/B benchmark")
    parser.add_argument("--formats", nargs="+", default=["marker", "legacy"],
                        choices=list(FORMATS.keys()), help="計測するフォーマット")
    parser.add_argument("--online", action="store_true", help="実モデルで計測（要API鍵）")
    parser.add_argument("--model", type=str, default=None, help="online 時のモデルID")
    parser.add_argument("--provider", type=str, default=None, help="online 時のプロバイダー")
    args = parser.parse_args()
    asyncio.run(main_async(args.formats, args.online, args.model, args.provider))


if __name__ == "__main__":
    main()
