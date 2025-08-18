from typing import Dict, Any
from .base_prompt import BasePromptGenerator
from .main_prompt import MainPromptGenerator
from companion.state.agent_state import AgentState


class ContextAssembler:
	def __init__(self):
		self.base = BasePromptGenerator()
		self.main = MainPromptGenerator()
	
	def build_system_prompt(self, state: AgentState) -> str:
		base_block = self.base.generate(state.constraints)
		main_block = self.main.generate(state)
		return "\n\n".join([base_block, main_block])
