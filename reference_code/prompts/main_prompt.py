from typing import Dict, Any
from companion.state.agent_state import AgentState


class MainPromptGenerator:
	def generate(self, state: AgentState) -> str:
		fixed = [
			"--- 固定5項目 ---",
			f"目的: {state.goal}",
			f"理由(なぜ今): {state.why_now}",
			"制約:",
			* [f"- {c}" for c in (state.constraints or [])],
			"短期プラン(brief):",
			* [f"- {p}" for p in (state.plan_brief or [])],
			"未解決の問い:",
			* [f"- {q}" for q in (state.open_questions or [])],
		]
		conv = [
			"--- 会話状況 ---",
			f"メッセージ数: {len(state.conversation_history)}"
		]
		# 軽量ワークスペース文脈（あれば）
		ws = state.collected_context.get("workspace_info") if hasattr(state, 'collected_context') else None
		ws_block = []
		if isinstance(ws, dict):
			path = ws.get("current_path") or ws.get("path")
			files = ws.get("files", [])
			if path:
				ws_block.append("--- 作業フォルダ ---")
				ws_block.append(f"場所: {path}")
				if files:
					ws_block.append("最近のファイル:")
					ws_block.extend([f"- {f}" for f in files[:5]])
		# 直近読み取りファイル
		lr = state.collected_context.get("last_read_file") if hasattr(state, 'collected_context') else None
		lr_block = []
		if isinstance(lr, dict):
			lr_block.append("--- 直近の読込ファイル ---")
			if lr.get("path"):
				lr_block.append(f"パス: {lr['path']}")
			if lr.get("summary"):
				lr_block.append("要約:")
				lr_block.append(str(lr["summary"]))
		
		return "\n".join([*fixed, *conv, *ws_block, *lr_block])
