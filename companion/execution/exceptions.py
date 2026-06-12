from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from companion.state.agent_state import Task

class ParameterValidationError(Exception):
    """
    Raised when the parameters provided in an Action object do not match 
    the actual signature of the target tool function.
    """
    def __init__(self, task: 'Task', expected_params: str, received_params: str, missing_required: list[str], extra_received: list[str]):
        self.task = task
        self.expected_params = expected_params
        self.received_params = received_received
        self.missing_required = missing_required
        self.extra_received = extra_received
        
        missing_str = f"Missing required: {', '.join(missing_required)}" if missing_required else "None"
        extra_str = f"Extra received: {', '.join(extra_received)}" if extra_received else "None"
        
        message = (
            f"Parameter validation failed for Task '{task.title}' (Tool: {task.action.name}).\n"
            f"Expected Signature: ({expected_params})\n"
            f"Received Arguments: ({received_params})\n"
            f"Issues: {missing_str}, {extra_str}"
        )
        super().__init__(message)

class ReplanRequiredError(Exception):
    """Exception raised when a task requires dynamic planning (Yield)."""
    def __init__(self, task: 'Task'):
        self.task = task
        super().__init__(f"Task '{task.title}' requires dynamic planning.")