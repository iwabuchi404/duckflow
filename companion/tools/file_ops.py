def write_file(path: str, content: str) -> str:
    """
    ファイル書き込み（ディレクトリ自動作成付き）
    
    Raises:
        ValueError: 無効なパス指定
        OSError: ファイルシステムエラー
    """
    # パス検証（前回修正済み）
    if not path or path.isspace() or "generated_" in path:
        raise ValueError("明示的なパス指定が必要です。例: @src/main.py")
    
    # ディレクトリ自動作成
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        logger.info(f"自動作成: ディレクトリ {directory}")
    
    # ファイル書き込み
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return f"ファイル作成: {path}"