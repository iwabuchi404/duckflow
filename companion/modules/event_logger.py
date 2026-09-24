"""
EventLogger — JSONL event logging for observability (S3-11).

Writes structured events to logs/events.jsonl for offline analysis.
Each line is a self-contained JSON object.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EventLogger:
    """
    Append-only JSONL event logger.

    Events are written to ``logs/events.jsonl`` (configurable via
    ``event.log_path`` in duckflow.yaml). Each event is a single JSON
    line with a timestamp, event type, and arbitrary payload.
    """

    _instance: Optional["EventLogger"] = None

    def __new__(cls) -> "EventLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._enabled = True
            self._log_path = self._resolve_log_path()

    def _resolve_log_path(self) -> Path:
        from companion.config.config_loader import config

        path_str = config.get("event.log_path", "logs/events.jsonl")
        p = Path(path_str)
        if not p.is_absolute():
            root = Path(__file__).parent.parent.parent
            p = root / p
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def log(self, event_type: str, payload: dict[str, Any]) -> None:
        """Write a single event line to the JSONL log."""
        if not self._enabled:
            return
        try:
            event = {
                "ts": datetime.now().isoformat(timespec="milliseconds"),
                "type": event_type,
                **payload,
            }
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        except Exception as e:
            logger.debug(f"EventLogger write failed: {e}")

    def log_action_start(self, action_name: str, parameters: dict[str, Any]) -> None:
        """Write an action-start event.

        Args:
            action_name: Name of the action being started.
            parameters: Action parameters whose keys are recorded.

        Returns:
            None.
        """
        self.log(
            "action_start",
            {
                "action": action_name,
                "params_keys": list(parameters.keys()),
            },
        )

    def log_action_end(
        self,
        action_name: str,
        duration_ms: float,
        is_error: bool,
        result_len: int,
    ) -> None:
        """Write an action-end event.

        Args:
            action_name: Name of the completed action.
            duration_ms: Action duration in milliseconds.
            is_error: Whether the action failed.
            result_len: Length of the action result.

        Returns:
            None.
        """
        self.log(
            "action_end",
            {
                "action": action_name,
                "duration_ms": round(duration_ms, 1),
                "is_error": is_error,
                "result_len": result_len,
            },
        )

    def log_llm_call(self, model: str, message_count: int) -> None:
        """Write an LLM request event.

        Args:
            model: Model identifier used for the request.
            message_count: Number of input messages.

        Returns:
            None.
        """
        self.log(
            "llm_call",
            {
                "model": model,
                "message_count": message_count,
            },
        )

    def log_llm_response(
        self,
        model: str,
        duration_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        retry_count: int = 0,
    ) -> None:
        """Write an LLM response event.

        Args:
            model: Model identifier used for the request.
            duration_ms: Request duration in milliseconds.
            input_tokens: Input token count.
            output_tokens: Output token count.
            retry_count: Number of retries performed.

        Returns:
            None.
        """
        self.log(
            "llm_response",
            {
                "model": model,
                "duration_ms": round(duration_ms, 1),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "retry_count": retry_count,
            },
        )

    @property
    def log_path(self) -> Path:
        return self._log_path

    def disable(self) -> None:
        self._enabled = False

    def enable(self) -> None:
        self._enabled = True


event_logger = EventLogger()
