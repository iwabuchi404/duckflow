"""
文字コード設定の一元管理モジュール
システム起動時に一度だけ実行され、すべてのコンポーネントで共有される
"""

import logging
import os
import sys


class EncodingConfig:
    """文字コード設定の一元管理クラス"""

    _instance: "EncodingConfig | None" = None
    _initialized = False

    def __new__(cls) -> "EncodingConfig":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not self._initialized:
            self._setup_encoding_environment()
            self._initialized = True

    def _setup_encoding_environment(self) -> None:
        """文字コード関連の環境変数を設定"""
        try:
            # Python標準出力のエンコーディング設定
            os.environ["PYTHONIOENCODING"] = "utf-8"
            os.environ["PYTHONLEGACYWINDOWSSTDIO"] = "utf-8"

            # Windows固有の設定
            os.environ["PYTHONUTF8"] = "1"

            # ロケール設定
            os.environ["LC_ALL"] = "C.UTF-8"
            os.environ["LANG"] = "C.UTF-8"

            # 標準出力のエンコーディングを強制設定
            stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
            stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
            if callable(stdout_reconfigure):
                stdout_reconfigure(encoding="utf-8", errors="replace")
            if callable(stderr_reconfigure):
                stderr_reconfigure(encoding="utf-8", errors="replace")

            # Windows環境でのコンソールコードページ設定
            if os.name == "nt":
                try:
                    os.system("chcp 65001 > nul 2>&1")
                except Exception:
                    pass

            # ログ出力
            logger = logging.getLogger(__name__)
            logger.info("✅ システム文字コード環境設定完了")
            logger.info(
                f"PYTHONIOENCODING: {os.environ.get('PYTHONIOENCODING', '未設定')}"
            )
            logger.info(
                f"PYTHONLEGACYWINDOWSSTDIO: {os.environ.get('PYTHONLEGACYWINDOWSSTDIO', '未設定')}"
            )
            logger.info(f"PYTHONUTF8: {os.environ.get('PYTHONUTF8', '未設定')}")

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"⚠️ システム文字コード環境設定でエラー: {e}")

    def get_environment_vars(self) -> dict[str, str]:
        """設定された環境変数を取得"""
        return {
            "PYTHONIOENCODING": os.environ.get("PYTHONIOENCODING", ""),
            "PYTHONLEGACYWINDOWSSTDIO": os.environ.get("PYTHONLEGACYWINDOWSSTDIO", ""),
            "PYTHONUTF8": os.environ.get("PYTHONUTF8", ""),
            "LC_ALL": os.environ.get("LC_ALL", ""),
            "LANG": os.environ.get("LANG", ""),
        }

    def verify_encoding_setup(self) -> bool:
        """エンコーディング設定が正しく行われているか検証"""
        try:
            env_vars = self.get_environment_vars()
            required_vars = [
                "PYTHONIOENCODING",
                "PYTHONLEGACYWINDOWSSTDIO",
                "PYTHONUTF8",
            ]

            for var in required_vars:
                if env_vars.get(var) != "utf-8" and env_vars.get(var) != "1":
                    return False

            # 標準出力のエンコーディング確認
            if hasattr(sys.stdout, "encoding") and sys.stdout.encoding != "utf-8":
                return False

            return True

        except Exception:
            return False


# グローバルインスタンス
encoding_config = EncodingConfig()


def setup_encoding_once() -> EncodingConfig:
    """文字コード設定を一度だけ実行（既存コードとの互換性のため）

    Returns:
        初期化済みの文字コード設定インスタンス。
    """
    return encoding_config


def get_encoding_config() -> EncodingConfig:
    """文字コード設定インスタンスを取得

    Returns:
        共有されている文字コード設定インスタンス。
    """
    return encoding_config
