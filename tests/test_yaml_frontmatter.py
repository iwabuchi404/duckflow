"""
YAML Frontmatter argument extraction のテスト。

検証観点:
1. --- ブロックがある場合、引数として正しく抽出されること
2. --- ブロックがない場合、元のコンテンツがそのまま使われること（後方互換）
3. 引数と残余コンテンツが正しく分離されること
4. FuzzyParser 経由で edit_file が正しくパースされること（統合）
"""

import pytest
from companion.utils.sym_ops import FuzzyParser


class TestExtractYamlFrontmatter:
    """_extract_yaml_frontmatter のユニットテスト"""

    def setup_method(self):
        self.parser = FuzzyParser()

    def test_basic_frontmatter(self):
        """基本的なフロントマター抽出"""
        content = '---\nanchors: "1:abc 3:def"\n---\ndef foo():\n    pass'
        params, body = self.parser._extract_yaml_frontmatter(content)
        assert params == {"anchors": "1:abc 3:def"}
        assert body == "def foo():\n    pass"

    def test_multiple_params(self):
        """複数引数の抽出"""
        content = '---\nanchors: "42:a3f 43:f10"\nmode: strict\n---\ndef bar():\n    return 1'
        params, body = self.parser._extract_yaml_frontmatter(content)
        assert params["anchors"] == "42:a3f 43:f10"
        assert params["mode"] == "strict"
        assert "def bar():" in body

    def test_no_frontmatter(self):
        """フロントマターがない場合は元のコンテンツをそのまま返す（後方互換）"""
        content = 'def foo():\n    pass'
        params, body = self.parser._extract_yaml_frontmatter(content)
        assert params == {}
        assert body == content

    def test_leading_blank_lines(self):
        """先頭の空行をスキップしてフロントマターを検出"""
        content = '\n\n---\nanchors: "1:abc 1:abc"\n---\nsome code'
        params, body = self.parser._extract_yaml_frontmatter(content)
        assert params["anchors"] == "1:abc 1:abc"
        assert body == "some code"

    def test_unclosed_frontmatter(self):
        """終端 --- がない場合はフロントマターなしとして扱う"""
        content = '---\nanchors: "1:abc 1:abc"\ndef foo():'
        params, body = self.parser._extract_yaml_frontmatter(content)
        assert params == {}
        assert body == content

    def test_invalid_yaml(self):
        """不正なYAMLはフロントマターなし扱い（エラーを出さない）"""
        content = '---\n: invalid: yaml: here\n---\ncode here'
        params, body = self.parser._extract_yaml_frontmatter(content)
        # エラーを発生させずに空のparamsと元のcontentを返す
        assert params == {}

    def test_empty_content_after_frontmatter(self):
        """フロントマターのみで本文なし"""
        content = '---\nanchors: "1:abc 1:abc"\n---'
        params, body = self.parser._extract_yaml_frontmatter(content)
        assert params["anchors"] == "1:abc 1:abc"
        assert body == ""


class TestSymOpsFrontmatterIntegration:
    """FuzzyParser 経由でのフロントマターの統合テスト"""

    def setup_method(self):
        self.parser = FuzzyParser()

    def test_edit_file_with_frontmatter_strict(self):
        """strict_parse で edit_file の YAML フロントマターが正しく解析される"""
        llm_output = """\
>> ハッシュを確認。替対象は 1:abc 1:abc の行。

::c0.95 ::s1.0 ::m0.2 ::f0.95

::edit_file @hello.py
<<<
---
anchors: "1:abc 1:abc"
---
# comment
def main():
>>>"""
        result = self.parser.strict_parse(llm_output)
        assert len(result.actions) == 1
        a = result.actions[0]
        assert a.type == "edit_file"
        assert a.path == "hello.py"
        assert a.params.get("anchors") == "1:abc 1:abc"
        # content は --- ブロックの後の本文のみ
        assert "# comment" in a.content
        assert "def main():" in a.content
        # anchors の行は content に含まれないこと
        assert "anchors" not in a.content

    def test_edit_file_without_frontmatter_strict(self):
        """strict_parse でフロントマターなし（後方互換）"""
        llm_output = """\
::c0.95 ::s1.0 ::m0.2 ::f0.95

::edit_file @hello.py
<<<
def main():
    pass
>>>"""
        result = self.parser.strict_parse(llm_output)
        a = result.actions[0]
        assert a.path == "hello.py"
        # anchors はない
        assert "anchors" not in a.params
        assert "def main():" in a.content

    def test_edit_file_with_frontmatter_fuzzy(self):
        """fuzzy_parse で edit_file の YAML フロントマターが正しく解析される"""
        llm_output = """\
::edit_file @hello.py
<<<
---
anchors: "2:bbb 4:ddd"
---
def calculate():
    return 42
>>>"""
        result = self.parser.fuzzy_parse(llm_output)
        assert len(result.actions) >= 1
        a = result.actions[0]
        assert a.params.get("anchors") == "2:bbb 4:ddd"
        assert "def calculate():" in a.content
        assert "anchors" not in a.content
