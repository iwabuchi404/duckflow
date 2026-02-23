from .summary import summarize_result

class CodeRunner:
    async def run_python_file(self, file_path: str) -> str:
        # 既存コード...
        result = await self.run_command(f"python {file_path}")
        
        # 要約表示に変更
        return summarize_result(
            result["stdout"], 
            result["stderr"], 
            result["exit_code"]
        )