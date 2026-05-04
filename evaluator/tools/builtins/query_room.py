from __future__ import annotations

import json
from typing import Any

from ..specs import ToolCall, ToolResult, ToolSpec


class QueryRoomToolRuntime:
    def spec(self) -> ToolSpec:
        return ToolSpec(
            tool_id="query_room",
            model_name="query_room",
            description="Query room list and room details",
            strict=False,
            input_schema={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        )

    def execute(self, call: ToolCall, ctx: Any) -> ToolResult:
        obs, *_ = ctx.env.step({"name": "query_room"})
        content = str(getattr(obs, "output", "") or "")
        error = getattr(obs, "error", None)
        if error is not None:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result={},
                error_code="EXECUTION_ERROR",
                error_message=str(error),
            )
        rooms = _parse_json_list(content)
        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            ok=True,
            result={
                "count": len(rooms),
                "rooms": rooms,
            },
        )


def _parse_json_list(content: str) -> list[dict[str, Any]]:
    stripped = content.strip()
    if not stripped:
        return []
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        items: list[dict[str, Any]] = []
        index = 0
        while index < len(stripped):
            while index < len(stripped) and stripped[index].isspace():
                index += 1
            if index >= len(stripped):
                break
            parsed, next_index = decoder.raw_decode(stripped, index)
            if isinstance(parsed, list):
                items.extend(item for item in parsed if isinstance(item, dict))
            elif isinstance(parsed, dict):
                items.append(parsed)
            index = next_index
        return items
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        return [parsed]
    return []
