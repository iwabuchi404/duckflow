from companion.state.agent_state import AgentState, AgentPhase

class ApprovalTool:
    """
    Manages user approval and 'Duck Call' (consultation).
    """
    def __init__(self, state: AgentState):
        self.state = state

    async def duck_call(self, message: str = "") -> str:
        """
        🦆 Duck Call: Explicitly ask the user for help or decision.
        Stops execution and waits for user input.
        Pacemaker介入時にも自動的に使用される（ループ上限到達・連続エラー等）。

        Args:
            message: ユーザーに表示する質問・相談内容

        Returns:
            実行確認文字列 "Paused for user input."
        """
        print(f"\n📞 DUCK CALL: {message}")
        print("   (The agent is pausing for your input...)\n")
        
        # Set phase to AWAITING_USER so the loop prompts for input next
        self.state.phase = AgentPhase.AWAITING_USER

        # Keep the question text in the tool result so the question and the
        # user's later answer stay connected in conversation history.
        # Without this, history shows only "Paused for user input" and the
        # model may re-ask or lose the original request after answering.
        if message and message.strip():
            return f"Paused for user input. Question was: {message.strip()}"
        return "Paused for user input."

