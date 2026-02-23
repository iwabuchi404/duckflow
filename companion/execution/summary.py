def summarize_result(stdout: str, stderr: str, exit_code: int) -> str:
    """実行結果を要約する最小実装"""
    if exit_code == 0:
        lines = stdout.splitlines()
        if not lines:
            return "✅ 実行完了（出力なし）"
        if len(lines) > 3:
            return f"✅ 実行結果: {lines[0]}\n{lines[1]}\n{lines[2]}\n...他{len(lines)-3}行"
        return "✅ 実行結果: " + "\n".join(lines)
    
    # エラー要約
    error_lines = [line for line in stderr.splitlines() if line.strip()]
    if error_lines:
        last_line = error_lines[-1]
        error_type = last_line.split(":")[0] if ":" in last_line else "実行時エラー"
        return f"❌ {error_type}: {last_line}"
    return f"❌ エラー (終了コード: {exit_code})"