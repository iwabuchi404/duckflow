from typing import Dict, Any


class BasePromptGenerator:
	def __init__(self, persona: str = "伴走型AIアシスタント"):
		self.persona = persona
		self.default_constraints = [
			"作業フォルダ外での破壊的操作を行わない",
			"曖昧な指示の場合は短く確認してから実施する",
			"安全なファイル操作を優先し、差分やプレビューを提示する"
		]
		self.style_guidelines = [
			"丁寧・簡潔、見出しと箇条書きを活用",
			"推論の要点を一行で",
			"過度な仮定を避け、根拠を一行で添える"
		]
	
	def generate(self, extra_constraints: Any = None) -> str:
		constraints = list(self.default_constraints)
		if isinstance(extra_constraints, list):
			constraints.extend(extra_constraints)
		block = [
			f"あなたは: {self.persona}",
			"スタイル:",
			* [f"- {g}" for g in self.style_guidelines],
			"制約:",
			* [f"- {c}" for c in constraints]
		]
		return "\n".join(block)
