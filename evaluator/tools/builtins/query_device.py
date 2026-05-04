from __future__ import annotations

import json
from typing import Any

from ...data.mha_adapter import MhaAdapter
from ..specs import ToolCall, ToolResult, ToolSpec


class QueryDeviceToolRuntime:
    def __init__(self, adapter: MhaAdapter | None = None) -> None:
        self.adapter = adapter or MhaAdapter()

    def spec(self) -> ToolSpec:
        return ToolSpec(
            tool_id="query_device",
            model_name="query_device",
            description=(
                "Find candidate devices or inspect capability specs and current status for resolved devices. "
            ),
            strict=False,
            input_schema={
                "type": "object",
                "properties": {
                    "what": {
                        "type": "string",
                        "enum": ["brief", "spec", "status", "spec_status"],
                        "description": (
                            "Query mode: brief finds candidates, spec returns capabilities and arguments, "
                            "status returns live values, and spec_status returns both for a resolved device."
                        ),
                    },
                    "did": {
                        "type": ["string", "null"],
                        "description": "Resolved device id when known; otherwise pass null.",
                    },
                    "category": {
                        "type": ["string", "null"],
                        "description": "High-level device category filter, or null when unused.",
                    },
                    "subcategory": {
                        "type": ["string", "null"],
                        "description": "Fine-grained device type filter, or null when unused.",
                    },
                    "spid": {
                        "type": ["string", "null"],
                        "description": "Product model identifier filter, or null when unused.",
                    },
                    "room": {
                        "type": ["string", "null"],
                        "description": "Room name or room id filter, or null when unused.",
                    },
                    "tags": {
                        "type": ["string", "null"],
                        "description": "Tag filter, or null when unused.",
                    },
                },
                "required": ["what"],
                "additionalProperties": False,
            },
        )

    def execute(self, call: ToolCall, ctx: Any) -> ToolResult:
        try:
            payload = self._build_payload(call.arguments, ctx.engine_data or {})
        except Exception as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result={"received_arguments": dict(call.arguments)},
                error_code="INVALID_ARGUMENT",
                error_message=str(exc),
            )

        obs, *_ = ctx.env.step(payload)
        content = str(getattr(obs, "output", "") or "")
        error = getattr(obs, "error", None)
        if error is not None:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result={"filters": self._result_filters(payload)},
                error_code="EXECUTION_ERROR",
                error_message=str(error),
            )

        devices = _parse_json_list(content)
        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            ok=True,
            result={
                "what": payload["what"],
                "filters": self._result_filters(payload),
                "count": len(devices),
                "devices": devices,
            },
        )

    def _build_payload(self, arguments: dict[str, Any], engine_data: dict[str, Any]) -> dict[str, Any]:
        what = arguments.get("what")
        if not isinstance(what, str) or not what.strip():
            raise ValueError("missing required string argument: what")
        payload: dict[str, Any] = {"name": "query_device", "what": what.strip()}
        for key in ("did", "category", "subcategory", "spid", "room", "tags"):
            value = arguments.get(key)
            if value is None:
                continue
            if key == "room" and isinstance(value, str):
                payload[key] = self.adapter.room_id(engine_data, value) or value
            else:
                payload[key] = value
        return payload

    @staticmethod
    def _result_filters(payload: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in payload.items() if key != "name"}


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
