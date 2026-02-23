class ConversationManager:  
    def __init__(self, io_handler):  
        self.io_handler = io_handler  

    async def continue_conversation(self, execution_result: dict, user_input: str) -> bool:  
        """実行結果に基づき対話続行を判断"""  
        if execution_result["exit_code"] != 0:  
            await self.io_handler.send_response(  
                f"⚠️ エラーが発生しました: {execution_result['error_type']}"  
            )  
            return False  

        if "test" in user_input.lower():  
            await self.io_handler.send_response("🧪 テスト結果を確認しています...")  
            return True  

        await self.io_handler.send_response(  
            "✅ 処理が完了しました。続きますか？(yes/no)"  
        )  
        return (await self.io_handler.get_user_input()).strip().lower() == "yes"  