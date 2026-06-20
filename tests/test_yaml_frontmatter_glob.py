"""
grep_files / find_files の include パラメータに include: *.py のような
未クォートの glob パターンを渡すと、YAML が先頭の '*' をエイリアス参照
（&anchor の再利用）構文と誤解釈し、yaml.safe_load が YAMLError を送出していた。

修正前の _extract_yaml_frontmatter はこのエラー時にフロントマター全体を
({}, content) として握りつぶしていたため、include だけでなく pattern や
path まで含めて全パラメータが消失していた（ユーザー報告の「パラメータエラー」）。
さらに include がデフォルト '*' にフォールバックすることで __pycache__ 内の
.pyc がノイズとして検索結果に混入していた（ユーザー報告の「.pycノイズ」）。
"""

from companion.utils.sym_ops import FuzzyParser


def _extract(yaml_block_content: str) -> tuple:
    """FuzzyParser._extract_yaml_frontmatter を直接呼び出すヘルパー。"""
    parser = FuzzyParser()
    return parser._extract_yaml_frontmatter(yaml_block_content)


class TestUnquotedGlobValue:
    """値が '*' から始まる未クォートのフロントマターのテスト"""

    def test_unquoted_star_py_glob_is_parsed(self) -> None:
        """include: *.py のような未クォート値でも全パラメータが救済されることを確認する。"""
        content = (
            "---\n"
            "pattern: \"TODO\"\n"
            "include: *.py\n"
            "path: \"companion\"\n"
            "---\n"
            "body"
        )
        params, remaining = _extract(content)
        assert params == {"pattern": "TODO", "include": "*.py", "path": "companion"}
        assert remaining == "body"

    def test_quoted_glob_still_works(self) -> None:
        """既存の正しい書き方（クォートあり）が引き続き動作することを確認する（リグレッション防止）。"""
        content = '---\ninclude: "*.py"\n---\nbody'
        params, remaining = _extract(content)
        assert params == {"include": "*.py"}

    def test_unquoted_glob_with_other_extension(self) -> None:
        """*.ts のような他の拡張子でも同様に救済されることを確認する。"""
        content = "---\ninclude: *.ts\n---\nbody"
        params, _ = _extract(content)
        assert params == {"include": "*.ts"}


class TestFallbackKeyValueParsing:
    """完全なYAML解析が依然として失敗するケースのフォールバックのテスト"""

    def test_unrelated_yaml_error_still_recovers_some_params(self) -> None:
        """
        glob修正でも解決しない未知のYAML構文エラーが起きた場合でも、
        行単位の "key: value" 抽出で部分的にパラメータを救済できることを確認する。
        """
        # ':' を含む不正な値で YAMLError を誘発しつつ、他の行は正常な key: value
        content = (
            "---\n"
            "pattern: \"a: b: c [unbalanced\n"
            "path: \"companion\"\n"
            "---\n"
            "body"
        )
        params, _ = _extract(content)
        # 少なくとも path は救済されている（全損していない）
        assert params.get("path") == "companion"

    def test_no_frontmatter_returns_empty(self) -> None:
        """フロントマターが存在しない場合は空辞書と元のコンテンツを返すことを確認する（リグレッション防止）。"""
        content = "no frontmatter here"
        params, remaining = _extract(content)
        assert params == {}
        assert remaining == content
