"""Native tool-calling protocol helpers (Sym-Ops swap experiment).

Converts the registered tool surface into API-native JSON Schema tool
definitions, translates native tool_calls responses into the internal
ActionList container, and rebuilds native conversation messages from
the text history each turn. See docs/tool_protocol_swap_design.md.

Only the main-agent path (response_model None/ActionList) uses this;
auxiliary structured calls stay on JSON/Pydantic.
"""

import inspect
import logging
import os
import re
import typing
from typing import Any, Callable, Dict, List, Mapping, Optional

logger = logging.getLogger(__name__)

PROTOCOL_ENV_VAR = "DUCKFLOW_TOOL_PROTOCOL"

# Control-plane actions are terminal signals, not callable tools, and are
# therefore excluded from native tool definitions. Plain model text maps
# to a response action (§4.2). duck_call stays text-driven as well so the
# collaboration pause works identically in both protocols.
NATIVE_CONTROL_ACTIONS = {"response", "exit", "duck_call", "status", "result"}

# Internal metadata keys that must never reach the API wire.
_INTERNAL_KEY_PREFIX = "_"

_JSON_TYPES = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
}


def resolve_protocol() -> str:
    """Resolve the active tool protocol from the environment.

    Returns:
        "native" when DUCKFLOW_TOOL_PROTOCOL=native, otherwise "symops".
    """
    return (
        "native" if os.getenv(PROTOCOL_ENV_VAR, "symops").lower() == "native" else "symops"
    )


def _json_type_name(annotation: Any) -> str:
    """Map a Python annotation to a JSON Schema type name.

    Args:
        annotation: inspect.Parameter.annotation value.

    Returns:
        JSON Schema type (string/integer/number/boolean/array/object).
    """
    if annotation is inspect.Parameter.empty:
        return "string"
    origin = typing.get_origin(annotation)
    if origin in (list, tuple, set):
        return "array"
    if origin is dict:
        return "object"
    if origin is typing.Union or str(type(origin)) == "<class 'types.UnionType'>":
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        if args:
            return _json_type_name(args[0])
        return "string"
    name = getattr(annotation, "__name__", str(annotation))
    return _JSON_TYPES.get(name, "string")


def sanitize_tool_references(text: str) -> str:
    """Neutralize Sym-Ops call notation for native-protocol contexts.

    Tool results, correction hints, and block messages were written for
    the Sym-Ops surface and reference tools as ``::name @target``. In
    native mode a model imitating that notation emits plain text that
    becomes a terminal response instead of a tool call, so the markers
    are rewritten to bare function names. The ``::`` must be preceded by
    a non-word/non-colon character (or line start) so code tokens like
    ``std::vector`` are left untouched.

    Args:
        text: Guidance text possibly containing ``::name @target``.

    Returns:
        Text with ``::name @target`` rewritten to ``name``.
    """
    return re.sub(
        r"(?<![\w:]):{2}(\w+)(\s+@(?:<[^>]*>|\S+))?", r"\1", text
    )


def _param_descriptions(func: Callable[..., Any]) -> Dict[str, str]:
    """Extract per-parameter docs from the function's ``Args:`` section.

    Args:
        func: Tool implementation callable.

    Returns:
        Mapping of parameter name to its docstring description. Params
        without an entry are absent from the mapping.
    """
    doc = inspect.getdoc(func) or ""
    match = re.search(r"Args:\s*\n(.*?)(?:\n\s*(?:Returns|Raises)[:\s]|\Z)", doc, re.DOTALL)
    if not match:
        return {}
    descriptions: Dict[str, str] = {}
    for line in match.group(1).splitlines():
        param_match = re.match(r"^\s*(\w+):\s*(.+)$", line)
        if param_match:
            descriptions[param_match.group(1)] = sanitize_tool_references(
                param_match.group(2).strip()
            )
    return descriptions


def build_native_tools(
    tools: Mapping[str, Callable[..., Any]], mode: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Build API-native tool definitions from registered callables.

    Uses the same mode scoping as Sym-Ops descriptions (UNIVERSAL_TOOLS
    plus MODE_TOOL_MAPPING) minus control-plane actions. Descriptions
    are the first docstring paragraph, matching get_tool_descriptions().

    Args:
        tools: Registered tool name to callable mapping.
        mode: Agent mode name. Unknown modes expose universal tools only.

    Returns:
        List of {"type": "function", "function": {...}} definitions.
    """
    from companion.core_tools import MODE_TOOL_MAPPING, UNIVERSAL_TOOLS

    allowed = None
    if mode and mode in MODE_TOOL_MAPPING:
        allowed = UNIVERSAL_TOOLS | MODE_TOOL_MAPPING[mode]
    elif mode:
        allowed = UNIVERSAL_TOOLS

    definitions = []
    for name, func in tools.items():
        if name in NATIVE_CONTROL_ACTIONS:
            continue
        if allowed is not None and name not in allowed:
            continue
        try:
            sig = inspect.signature(func)
        except (ValueError, TypeError):
            continue
        param_docs = _param_descriptions(func)
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for p_name, param in sig.parameters.items():
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                continue
            properties[p_name] = {
                "type": _json_type_name(param.annotation),
                "description": param_docs.get(
                    p_name, f"{p_name} argument of {name}"
                ),
            }
            if param.default is inspect.Parameter.empty:
                required.append(p_name)
        full_doc = inspect.getdoc(func) or "No description."
        summary = full_doc.split("\n\n")[0].replace("\n", " ")
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": summary,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return definitions


def tool_calls_to_actions(message: Any) -> List[Dict[str, Any]]:
    """Convert a native response message's tool_calls to action dicts.

    Unknown tool names pass through untouched: execute_actions() applies
    the same unknown-tool filter and feedback as the Sym-Ops path.

    Args:
        message: Response message object with optional tool_calls.

    Returns:
        List of {name, parameters, thought, call_id} dicts.
    """
    import json as _json

    calls = getattr(message, "tool_calls", None) or []
    actions = []
    for call in calls:
        fn = getattr(call, "function", None)
        raw_args = getattr(fn, "arguments", "") if fn else ""
        try:
            parameters = _json.loads(raw_args) if raw_args else {}
        except (ValueError, TypeError):
            parameters = {}
        if not isinstance(parameters, dict):
            parameters = {}
        actions.append(
            {
                "name": getattr(fn, "name", None) if fn else None,
                "parameters": parameters,
                "thought": "",
                "call_id": getattr(call, "id", None),
            }
        )
    return [a for a in actions if a["name"]]


def native_text_to_action(content: str) -> Dict[str, Any]:
    """Map native plain text (no tool calls) to a terminal action dict.

    A trailing question mark becomes an internal duck_call consultation
    (never sent as an API tool); anything else becomes a response.
    Mirrors the harness question detection (duck_call phase or "?").

    Args:
        content: Stripped model text output.

    Returns:
        Action dict with name duck_call or response.
    """
    if content.rstrip().endswith(("?", "？")):
        return {
            "name": "duck_call",
            "parameters": {"message": content},
            "thought": "Native trailing question as consultation.",
            "call_id": None,
        }
    return {
        "name": "response",
        "parameters": {"message": content},
        "thought": "Native text response.",
        "call_id": None,
    }


def _extract_tool_result_blocks(content: str) -> List[Dict[str, str]]:
    """Extract ordered (tool_name, body) pairs from TOOL_RESULT envelopes.

    Args:
        content: History message text possibly containing envelopes.

    Returns:
        List of {tool_name, body} dicts in appearance order.
    """
    import re as _re

    blocks = []
    for match in _re.finditer(
        r"\[TOOL_RESULT\]\s*(.*?)\s*\[/TOOL_RESULT\]", content, _re.DOTALL
    ):
        envelope = match.group(1)
        name_match = _re.search(r"^::(\w+)\s+@.*$", envelope, _re.MULTILINE)
        body_match = _re.search(r"<<<\n(.*)\n>>>", envelope, _re.DOTALL)
        blocks.append(
            {
                "tool_name": name_match.group(1) if name_match else "",
                "body": body_match.group(1) if body_match else envelope.strip(),
            }
        )
    return blocks


def _is_summary_text(content: str) -> bool:
    """Detect action-summary or history-note lines (not model prose).

    Args:
        content: Assistant history message text.

    Returns:
        True for ":: action" summaries and history notes.
    """
    stripped = content.lstrip()
    return stripped.startswith("::") or stripped.startswith("履歴注記")


def _is_pure_envelope(content: str) -> bool:
    """Detect user messages holding only TOOL_RESULT envelopes.

    Args:
        content: History message text.

    Returns:
        True when the whole message is envelope blocks (machine data
        already represented via tool-role messages in native mode).
    """
    stripped = (content or "").strip()
    if not stripped.startswith("[TOOL_RESULT]"):
        return False
    without = stripped
    while without.startswith("[TOOL_RESULT]"):
        end = without.find("[/TOOL_RESULT]")
        if end < 0:
            return False
        without = without[end + len("[/TOOL_RESULT]"):].strip()
    return not without


def build_native_messages(
    text_messages: List[Dict[str, Any]],
    assistant_log: List[Dict[str, Any]],
    journal: Optional[Mapping[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Rebuild native conversation messages from the text history.

    Assistant turns that carried tool_calls are restored verbatim from
    assistant_log (recorded per native chat() call). Pairing is keyed by
    turn id, not position: the executor stamps each assistant summary
    with ``_native_turn`` (from ``Action.native_turn``) and log entries
    carry the same id in ``_turn``. A summary pairs only with the entry
    of the same turn id; summaries without a fresh match — legacy text
    history, forced executions (pacemaker/parse-failure duck_calls), or
    entries written before this scheme — are dropped without consuming
    an entry. This keeps pairing stable across task resets, pruning,
    and interleaved non-LLM action summaries.

    Results pair by tool_call_id via ``journal`` (tolerating fail-fast
    partial execution); without a journal, calls pair with the turn's
    result blocks in order of appearance. Calls with no recorded result
    still emit a placeholder ``tool`` message — an assistant message
    with tool_calls but missing tool results is rejected by
    OpenAI-compatible APIs. Text-only turns (user inputs, response
    prose, denial contexts, system notices) pass through unchanged.

    Args:
        text_messages: Current text-form message list.
        assistant_log: Verbatim assistant message dicts in turn order.
        journal: Optional tool_call_id to outcome mapping from the
            execution journal (turn/tool_name/status/executed/body).

    Returns:
        Native message list for the API call.
    """
    by_turn: Dict[str, Dict[str, Any]] = {}
    for entry in assistant_log:
        turn = entry.get("_turn")
        if turn:
            by_turn[turn] = entry
    consumed_turns: set = set()
    out: List[Dict[str, Any]] = []
    i = 0
    while i < len(text_messages):
        msg = text_messages[i]
        role = msg.get("role", "")
        content = msg.get("content", "") or ""
        if role == "assistant" and _is_summary_text(content):
            turn = msg.get("_native_turn")
            entry = None
            if turn is not None and turn not in consumed_turns:
                entry = by_turn.get(turn)
                if entry is not None:
                    consumed_turns.add(turn)
            if entry is not None:
                calls = [
                    c for c in (entry.get("tool_calls") or []) if c.get("id")
                ]
                # Collect the turn's following messages: pure TOOL_RESULT
                # envelopes are represented by tool messages; anything
                # else (denials, system notes, real user input) passes
                # through verbatim.
                j = i + 1
                leftovers: List[Dict[str, Any]] = []
                blocks: List[Dict[str, str]] = []
                while (
                    j < len(text_messages)
                    and text_messages[j].get("role") != "assistant"
                ):
                    nxt = text_messages[j]
                    nxt_content = nxt.get("content", "") or ""
                    if _is_pure_envelope(nxt_content):
                        blocks.extend(
                            _extract_tool_result_blocks(nxt_content)
                        )
                    else:
                        leftovers.append(nxt)
                    j += 1
                emit = {
                    k: v
                    for k, v in entry.items()
                    if not k.startswith(_INTERNAL_KEY_PREFIX)
                }
                if calls:
                    emit["tool_calls"] = calls
                    out.append(emit)
                    for call in calls:
                        cid = call.get("id")
                        record = (
                            journal.get(cid) if journal is not None else None
                        )
                        if record is not None and record.get("body") is not None:
                            body = record["body"]
                        elif journal is None and blocks:
                            body = blocks.pop(0)["body"]
                        else:
                            logger.warning(
                                "native rebuild: no journal result for %s; "
                                "emitting placeholder",
                                cid,
                            )
                            body = (
                                "[tool call produced no recorded result: "
                                "filtered, dropped by the per-turn limit, or "
                                "the turn was aborted before it ran]"
                            )
                        out.append(
                            {
                                "role": "tool",
                                "tool_call_id": cid,
                                "content": body,
                            }
                        )
                elif emit.get("content"):
                    # Text-only turn (response/duck_call): restore the
                    # assistant prose so the model sees its own replies.
                    out.append(emit)
                for kept in leftovers:
                    kept_msg = dict(kept)
                    kept_msg.pop("cache_control", None)
                    out.append(kept_msg)
                i = j
                continue
            # No matching log entry: drop the summary; envelopes pass
            # through as user text.
            i += 1
            continue
        clean = dict(msg)
        clean.pop("cache_control", None)
        clean.pop("_native_turn", None)
        out.append(clean)
        i += 1
    return out
