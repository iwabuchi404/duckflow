"""
複数行入力 (S3-7) の回帰テスト。

実際のキー入力シミュレーションは Windows ターミナル等で環境依存になるため、
get_user_input が期待するキーバインディング（Enter / c-j / escape,enter）を
PromptSession に登録していることを構造的に検証する。
"""

import pytest

from companion.ui.console import DuckUI


@pytest.mark.asyncio
async def test_get_user_input_registers_multiline_bindings(monkeypatch):
    """
    get_user_input が multiline 関連のキーバインディングを登録した
    PromptSession を組み立てることを検証する。

    PromptSession.prompt_async を差し替え、session 生成時に渡された
    KeyBindings の bindings 名前一覧をキャプチャする。
    """
    captured: dict = {}

    class FakeBuffer:
        def __init__(self):
            self.text = ""

    class FakeSession:
        def __init__(self, completer=None, key_bindings=None, multiline=False,
                     prompt_continuation=""):
            # 登録されたキーバインディングの keys を記録
            keys = []
            for b in key_bindings.bindings:
                # prompt_toolkit の KeyBinding は .keys 属性にキーシーケンスを持つ
                seq = getattr(b, "keys", None)
                if seq:
                    keys.append(tuple(seq))
            captured["keys"] = keys
            captured["multiline"] = multiline
            captured["has_completer"] = completer is not None

        async def prompt_async(self, prompt):
            return "stub"

    import companion.ui.console as console_mod

    # PromptSession を FakeSession へ差し替え
    monkeypatch.setattr(
        "prompt_toolkit.PromptSession", lambda **kw: FakeSession(**kw)
    )

    ui = DuckUI()
    await ui.get_user_input()

    keys = captured.get("keys", [])
    # prompt_toolkit は "enter" を c-m (Keys.ControlM) として登録する。
    # c-j (Keys.ControlJ) は Shift+Enter 相当、escape は Esc→Enter 用。
    # 3つすべてのキーシーケンスが登録されていることを検証する。
    ENTER_REPR = {"enter", "c-m", "<Keys.ControlM: 'c-m'>", "ControlM"}
    CJ_REPR = {"c-j", "<Keys.ControlJ: 'c-j'>", "ControlJ"}
    ESC_REPR = {"escape", "<Keys.Escape: 'escape'>", "Escape"}

    def _has(repr_set: set) -> bool:
        for seq in keys:
            for k in seq:
                val = getattr(k, "value", None) or str(k)
                if val in repr_set or k in repr_set:
                    return True
        return False

    assert _has(ENTER_REPR), f"enter (c-m) binding missing; got {keys}"
    assert _has(CJ_REPR), f"c-j (Shift+Enter) binding missing; got {keys}"
    assert _has(ESC_REPR), f"escape binding missing; got {keys}"


@pytest.mark.asyncio
async def test_get_user_input_returns_string(monkeypatch):
    """get_user_input が str を返す（最低限の契約）。"""

    class FakeSession:
        def __init__(self, **kwargs):
            pass

        async def prompt_async(self, prompt):
            return "hello"

    monkeypatch.setattr(
        "prompt_toolkit.PromptSession", lambda **kw: FakeSession(**kw)
    )

    ui = DuckUI()
    result = await ui.get_user_input()
    assert isinstance(result, str)
    assert result == "hello"


@pytest.mark.asyncio
async def test_get_user_input_eof_returns_exit(monkeypatch):
    """EOFError / KeyboardInterrupt 時は /exit を返す（既存契約の維持）。"""

    class FakeSession:
        def __init__(self, **kwargs):
            pass

        async def prompt_async(self, prompt):
            raise EOFError

    monkeypatch.setattr(
        "prompt_toolkit.PromptSession", lambda **kw: FakeSession(**kw)
    )

    ui = DuckUI()
    result = await ui.get_user_input()
    assert result == "/exit"
