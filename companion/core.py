from .conversation import ConversationManager  

class DuckAgent:  
    def __init__(self, debug_context_mode=None):  
        # 既存コード...  
        self.conversation = ConversationManager(self.io_handler)  

    async def _handle_code_execution(self, command):  
        # 既存の実行処理...  
        continuation = await self.conversation.continue_conversation(  
            execution_result,  
            self.current_input  
        )  
        return continuation  