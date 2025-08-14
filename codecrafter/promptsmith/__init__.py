"""
PromptSmith - AIプロンプト自動改善システム

鍛冶職人が金属を鍛えるように、AIプロンプトを磨き上げるシステムです。
3つのAI（Tester、Target、Optimizer）が協調してプロンプトを継続的に改善します。
"""

from .orchestrator import PromptSmithOrchestrator
from .prompt_manager import PromptManager
from .ai_roles.tester_ai import TesterAI
from .ai_roles.optimizer_ai import OptimizerAI
from .improvement_engine import ImprovementEngine

__version__ = "0.1.0"
__all__ = [
    "PromptSmithOrchestrator",
    "PromptManager", 
    "TesterAI",
    "OptimizerAI",
    "ImprovementEngine"
]