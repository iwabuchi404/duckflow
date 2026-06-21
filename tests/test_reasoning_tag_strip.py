"""推論系モデルの <think> ブロック除去のテスト。

DeepSeek-R1 / Kimi K2 / Qwen3 / GLM / GPT-OSS 等の推論モデルが本文に埋め込む
<think>...</think> を SymOpsProcessor がパイプライン入口で除去し、response の
コンテンツブロックに </think> が生漏れしないことを検証する（表示崩れ回帰防止）。
"""
from companion.utils.preprocessor import strip_reasoning_tags
from companion.utils.sym_ops import SymOpsProcessor


def test_strip_removes_full_block():
    """完全な <think>...</think> ブロックを中身ごと除去する。"""
    text = "<think>推論過程</think>\n::response\n<<<\nこんにちは\n>>>"
    stripped, was = strip_reasoning_tags(text)
    assert was is True
    assert "<think>" not in stripped
    assert "</think>" not in stripped
    assert "推論過程" not in stripped  # 推論内容も漏れない
    assert "こんにちは" in stripped


def test_strip_removes_orphan_close_tag():
    """コンテンツブロック内に漏れた孤立 </think> を除去（表示崩れの直接原因）。"""
    text = "::response\n<<<\nこんにちは\n</think>\n>>>"
    stripped, was = strip_reasoning_tags(text)
    assert was is True
    assert "</think>" not in stripped
    assert "こんにちは" in stripped


def test_strip_removes_orphan_open_tag():
    """孤立 <think>（閉じ忘れ）も除去する。"""
    text = "<think>残り\n::response\n<<<\nこんにちは\n>>>"
    stripped, was = strip_reasoning_tags(text)
    assert was is True
    assert "<think>" not in stripped
    assert "こんにちは" in stripped


def test_strip_noop_when_absent():
    """<think> が含まれない場合は何もしない。"""
    text = "::response\n<<<\nこんにちは\n>>>"
    stripped, was = strip_reasoning_tags(text)
    assert was is False
    assert stripped == text


def test_strip_case_insensitive():
    """大文字小文字を区別しない（<THINK> 等も除去）。"""
    text = "<THINK>reasoning</THINK>\n::response\n<<<\nhi\n>>>"
    stripped, was = strip_reasoning_tags(text)
    assert was is True
    assert "reasoning" not in stripped
    assert "hi" in stripped


def test_processor_pipeline_strips_think_from_response():
    """SymOpsProcessor が <think> を除去し、response の content に
    </think> が漏れないことを検証する（表示崩れ回帰防止）。"""
    raw = (
        "<think>ユーザーがリファクタリングしたファイルを確認する必要がある。</think>\n"
        "::c1.0\n"
        ">> 応答します\n"
        "::response\n"
        "<<<\n"
        "リファクタリングの確認をします。\n"
        ">>>"
    )
    result = SymOpsProcessor().process(raw)

    # response action の content に <think>/</think> が混入しない
    response_contents = [a.content for a in result.actions if a.type == "response"]
    assert response_contents, "response action が存在すべき"
    for content in response_contents:
        assert "<think>" not in content
        assert "</think>" not in content
        assert "リファクタリングしたファイル" not in content  # 推論内容の漏洩がない

    # 除去警告が記録される（観測用）
    assert any("Reasoning tags stripped" in w for w in result.warnings)
