'''Hashline ファイル編集システムのユーティリティモジュール。

このモジュールは、Hashline 形式のファイル編集を支援する関数を提供します。
Hashline は、行番号とハッシュの組み合わせで行を識別し、LLMによるファイル編集の精度を向上させます。

ハッシュ仕様:
- アルゴリズム: CRC32 mod 4096
- 表現: 3文字の16進数 (例: a3f)
- 衝突軽減: 4096 通りのハッシュ値（2文字の256通りより十分大きい）
- 空白処理: leading/trailing whitespace を strip してからハッシュ計算

使用例:
    # read_file の出力形式
    42:a3f| def calculate_total(items):
    43:f10|     return sum(items)

    # edit_file の Sym-Ops 形式
    ::edit_file @utils.py
    <<<
    42:a3f 43:f10
    def calculate_total(items: list[int]) -> int:
        """Calculate the total sum."""
        return sum(items)
    >>>
'''

import zlib
from typing import List, Tuple


class HashlineHelper:
    """Hashline 形式のファイル編集支援ユーティリティクラス。"""

    HASH_MODULUS = 4096  # 2^12
    HASH_LENGTH = 3  # 3文字の16進数

    @staticmethod
    def _compute_crc32_hash(line: str) -> str:
        """
        行のハッシュを生成 (CRC32 mod 4096, 3文字hex)。

        Args:
            line: ハッシュ対象の行文字列（leading/trailing whitespace を strip した後）

        Returns:
            3文字の16進数ハッシュ文字列（例: a3f）
        """
        stripped = line.strip()
        if not stripped:
            # 空行の場合は特殊なハッシュ値（000）
            return "000"

        crc32 = zlib.crc32(stripped.encode('utf-8')) & 0xFFFFFFFF
        hash_value = crc32 % HashlineHelper.HASH_MODULUS
        return f"{hash_value:03x}"

    @staticmethod
    def format_with_hashlines(content: str, start_line: int = 1, include_hash: bool = True) -> str:
        """
        コンテンツを行番号付き形式に変換する。

        Args:
            content: 変換対象のコンテンツ文字列
            start_line: 最初の行に割り当てる行番号
            include_hash: ハッシュ(3桁hex)を含めるかどうか。False の場合は "行番号|内容" 形式。

        Returns:
            変換された文字列
        """
        lines = content.split('\n')
        hashline_lines = []

        for i, line in enumerate(lines, start=start_line):
            if include_hash:
                hash_value = HashlineHelper._compute_crc32_hash(line)
                hashline_lines.append(f"{i}:{hash_value}|{line}")
            else:
                hashline_lines.append(f"{i}|{line}")

        return '\n'.join(hashline_lines)

    @staticmethod
    def parse_anchor(anchor: str) -> Tuple[int, str]:
        """
        アンカー文字列から (行番号, ハッシュ) を抽出する。

        Args:
            anchor: アンカー文字列（例: "42:a3f"）

        Returns:
            (行番号, ハッシュ) のタプル

        Raises:
            ValueError: アンカー形式が不正な場合
        """
        if ':' not in anchor:
            raise ValueError(f"Invalid anchor format: '{anchor}'. Expected format: 'line:hash'")

        line_str, hash_value = anchor.split(':', 1)

        try:
            line_num = int(line_str)
        except ValueError:
            raise ValueError(f"Invalid line number in anchor: '{line_str}'")

        if len(hash_value) != HashlineHelper.HASH_LENGTH:
            raise ValueError(
                f"Invalid hash length in anchor: '{hash_value}'. "
                f"Expected {HashlineHelper.HASH_LENGTH} characters."
            )

        try:
            int(hash_value, 16)  # 有効な16進数かチェック
        except ValueError:
            raise ValueError(f"Invalid hex hash in anchor: '{hash_value}'")

        return line_num, hash_value

    @staticmethod
    def extract_content_block(
        file_lines: List[str],
        start_anchor: str,
        end_anchor: str
    ) -> Tuple[int, int, List[str]]:
        """
        ファイル内容からアンカーで指定された範囲を抽出・検証する。

        Args:
            file_lines: ファイルの行リスト（先頭行がインデックス0）
            start_anchor: 開始アンカー（例: "42:a3f"）
            end_anchor: 終了アンカー（例: "43:f10"）

        Returns:
            (開始行インデックス, 終了行インデックス, 範囲内の行) のタプル

        Raises:
            ValueError: アンカーが見つからない、またはハッシュが不一致の場合
        """
        start_line_num, start_hash = HashlineHelper.parse_anchor(start_anchor)
        end_line_num, end_hash = HashlineHelper.parse_anchor(end_anchor)

        # 行番号を0ベースインデックスに変換
        start_idx = start_line_num - 1
        end_idx = end_line_num - 1

        # インデックス範囲チェック
        if start_idx < 0 or start_idx >= len(file_lines):
            raise ValueError(
                f"Start line number {start_line_num} is out of range "
                f"(file has {len(file_lines)} lines)."
            )
        if end_idx < 0 or end_idx >= len(file_lines):
            raise ValueError(
                f"End line number {end_line_num} is out of range "
                f"(file has {len(file_lines)} lines)."
            )
        if start_idx > end_idx:
            raise ValueError(
                f"Start line {start_line_num} cannot be after end line {end_line_num}."
            )

        # ハッシュ検証
        actual_start_hash = HashlineHelper._compute_crc32_hash(file_lines[start_idx])
        if actual_start_hash != start_hash:
            actual_line = file_lines[start_idx]
            raise ValueError(
                f"Hash mismatch at line {start_line_num}: "
                f"expected hash '{start_hash}', got '{actual_start_hash}'.\n"
                f"  Actual line content: {repr(actual_line)}\n"
                f"The file has changed since read_file was called. "
                f"Call read_file again to get fresh anchors, then retry edit_file with the NEW anchors. "
                f"Do NOT reuse the old anchor '{start_anchor}'."
            )

        actual_end_hash = HashlineHelper._compute_crc32_hash(file_lines[end_idx])
        if actual_end_hash != end_hash:
            actual_line = file_lines[end_idx]
            raise ValueError(
                f"Hash mismatch at line {end_line_num}: "
                f"expected hash '{end_hash}', got '{actual_end_hash}'.\n"
                f"  Actual line content: {repr(actual_line)}\n"
                f"The file has changed since read_file was called. "
                f"Call read_file again to get fresh anchors, then retry edit_file with the NEW anchors. "
                f"Do NOT reuse the old anchor '{end_anchor}'."
            )

        # 範囲を抽出（終了行を含む）
        extracted = file_lines[start_idx:end_idx + 1]

        return start_idx, end_idx, extracted

    @staticmethod
    def format_context_after_edit(
        file_lines: List[str],
        edit_start_idx: int,
        edit_end_idx: int,
        context_lines: int = 5,
        include_hash: bool = False
    ) -> str:
        """
        編集後のコンテキストを行番号付き形式で返す。

        Args:
            file_lines: 編集後のファイルの行リスト
            edit_start_idx: 編集開始インデックス
            edit_end_idx: 編集終了インデックス
            context_lines: 変更箇所の前後に含める行数
            include_hash: ハッシュを含めるかどうか。デフォルト False。

        Returns:
            フォーマットされたコンテキスト文字列
        """
        # コンテキスト範囲を計算
        context_start = max(0, edit_start_idx - context_lines)
        context_end = min(len(file_lines), edit_end_idx + context_lines + 1)

        # コンテキスト範囲を抽出
        context_lines_list = file_lines[context_start:context_end]

        return HashlineHelper.format_with_hashlines(
            '\n'.join(context_lines_list), 
            start_line=context_start + 1, 
            include_hash=include_hash
        )
