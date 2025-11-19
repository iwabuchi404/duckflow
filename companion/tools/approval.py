from companion.state.agent_state import AgentState, AgentPhase

class ApprovalTool:
    """
    Manages user approval and 'Duck Call' (consultation).
    """
    def __init__(self, state: AgentState):
        self.state = state

    async def duck_call(self, message: str) -> str:
        """
        🦆 Duck Call: Explicitly ask the user for help or decision.
        Stops execution and waits for user input.
        """
        print(f"\n📞 DUCK CALL: {message}")
        print("   (The agent is pausing for your input...)\n")
        
        # Set phase to AWAITING_USER so the loop prompts for input next
        self.state.phase = AgentPhase.AWAITING_USER
        
        return "Paused for user input."

