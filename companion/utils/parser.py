"""Backward-compatible facade for the canonical Sym-Ops parser.

The main-agent runtime uses :class:`companion.utils.sym_ops.SymOpsProcessor`.
This module remains only for callers that imported ``DuckflowParser`` before
that pipeline became the single source of truth. Keeping a facade here avoids
maintaining a second, behaviorally different grammar implementation.
"""

from dataclasses import dataclass, field

from companion.utils.sym_ops import SymOpsProcessor


@dataclass
class Action:
    """Represent a parsed action in the legacy compatibility shape.

    Args:
        type: Sym-Ops action name.
        params: Parsed inline or YAML parameters.
        content: Optional content-block body.
        target: Primary positional argument introduced by ``@``.
    """

    type: str
    params: dict[str, str] = field(default_factory=dict)
    content: str | None = None
    target: str = ""


@dataclass
class DuckflowResponse:
    """Represent a parsed Duckflow response for legacy callers.

    Args:
        reasoning: Combined ``>>`` thought text.
        vitals: Valid parsed vital values.
        actions: Parsed actions.
        raw_text: Original unmodified model response.
        parse_errors: Fatal compatibility-layer parsing failures.
        warnings: Non-fatal repairs or fuzzy-parse diagnostics.
        is_batch: Whether the response contains multiple or batched actions.
    """

    reasoning: str = ""
    vitals: dict[str, float] = field(default_factory=dict)
    actions: list[Action] = field(default_factory=list)
    raw_text: str = ""
    parse_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    is_batch: bool = False


class DuckflowParser:
    """Delegate the legacy parser API to the canonical Sym-Ops pipeline.

    Args:
        processor: Optional processor dependency for tests or customization.
    """

    def __init__(self, processor: SymOpsProcessor | None = None) -> None:
        """Initialize the compatibility parser.

        Args:
            processor: Optional canonical processor instance.

        Returns:
            None.
        """
        self._processor = processor or SymOpsProcessor()

    def parse(self, response: str) -> DuckflowResponse:
        """Parse a response through the canonical Sym-Ops implementation.

        Args:
            response: Raw LLM response string.

        Returns:
            Compatibility response containing canonical parse results.
        """
        try:
            parsed = self._processor.process(response)
        except Exception as exc:  # Preserve the legacy non-raising contract.
            return DuckflowResponse(
                raw_text=response,
                parse_errors=[f"Parse failed: {exc}"],
            )

        actions = [
            Action(
                type=action.type,
                params=dict(action.params),
                content=action.content or None,
                target=action.path,
            )
            for action in parsed.actions
        ]
        explicit_batch = any(
            line.strip() == "::execute_batch" for line in response.splitlines()
        )
        return DuckflowResponse(
            reasoning="\n".join(parsed.thoughts).strip(),
            vitals=dict(parsed.vitals),
            actions=actions,
            raw_text=response,
            warnings=list(parsed.warnings),
            is_batch=explicit_batch or len(actions) > 1,
        )
