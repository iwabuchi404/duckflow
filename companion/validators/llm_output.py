"""
Phase 1 LLM Output Validator for Main LLM JSON (Corrected)
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ValidationError

# 統一されたEnum定義をインポート
from companion.state.enums import Step, Status


class MainLLMOutput(BaseModel):
    rationale: str = Field(...)
    goal_consistency: str = Field(...)
    constraint_check: str = Field(...)
    next_step: str = Field(...)
    # 型定義をstrからEnumに修正
    step: Step = Field(...)
    status: Status = Field(...)
    state_delta: Optional[str] = Field(default=None)


class LLMOutputFormatter:
    def __init__(self):
        pass

    def validate(self, data: Dict[str, Any]) -> MainLLMOutput:
        return MainLLMOutput(**data)

    def try_repair(self, data: Dict[str, Any]) -> Optional[MainLLMOutput]:
        # Best-effort repair
        keys = ["rationale", "goal_consistency", "constraint_check", "next_step", "step", "status", "state_delta"]
        patched = {
            "rationale": data.get("rationale", ""),
            "goal_consistency": data.get("goal_consistency", ""),
            "constraint_check": data.get("constraint_check", ""),
            "next_step": data.get("next_step", ""),
            "step": data.get("step", Step.IDLE),
            "status": data.get("status", Status.PENDING),
            "state_delta": data.get("state_delta", "")
        }
        try:
            return MainLLMOutput(**patched)
        except ValidationError:
            return None