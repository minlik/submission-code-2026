from __future__ import annotations

import json
from typing import Any

from .specs import ToolCall, ToolResult


def decode_tool_call(raw_call: dict[str, Any]) -> ToolCall:
    function = raw_call.get("function") or {}
    tool_name = function.get("name")
    if not isinstance(tool_name, str) or not tool_name.strip():
        raise ValueError("tool name is required")
    arguments = _decode_arguments(function.get("arguments"))
    return ToolCall(
        call_id=str(raw_call.get("id") or ""),
        tool_name=tool_name,
        arguments=arguments,
        raw_call=raw_call,
    )


def encode_tool_result_message(result: ToolResult) -> str:
    if result.ok:
        payload = {
            "ok": True,
            "data": result.result,
        }
    else:
        payload = {
            "ok": False,
            "data": result.result,
            "error": {
                "code": result.error_code,
                "message": result.error_message,
            },
        }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _decode_arguments(raw_arguments: Any) -> dict[str, Any]:
    if raw_arguments is None:
        return {}
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if isinstance(raw_arguments, str):
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise ValueError(f"tool arguments are not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("tool arguments must decode to an object")
        return parsed
    raise ValueError(f"unsupported tool arguments type: {type(raw_arguments)}")
