"""
Phase 1 LLM Output Validator for Main LLM JSON

Expected fields:
- rationale: str
- goal_consistency: str
- constraint_check: str
- next_step: str
- step: str
- state_delta: str | None

Behavior:
- validate JSON shape; if invalid, allow one repair attempt via simple heuristics
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ValidationError


class MainLLMOutput(BaseModel):
    rationale: str = Field(...)
    goal_consistency: str = Field(...)
    constraint_check: str = Field(...)
    next_step: str = Field(...)
    step: str = Field(...)
    state_delta: Optional[str] = Field(default=None)


class LLMOutputFormatter:
    def __init__(self):
        pass

    def validate(self, data: Dict[str, Any]) -> MainLLMOutput:
        return MainLLMOutput(**data)

    def try_repair(self, data: Dict[str, Any]) -> Optional[MainLLMOutput]:
        # Best-effort repair: coerce missing keys to empty strings
        keys = ["rationale", "goal_consistency", "constraint_check", "next_step", "step", "state_delta"]
        patched = {k: data.get(k, "") for k in keys}
        try:
            return MainLLMOutput(**patched)
        except ValidationError:
            return None


