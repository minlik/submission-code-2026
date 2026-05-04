from __future__ import annotations

from typing import Any

from ...data.mha_adapter import MhaAdapter
from ..specs import ToolCall, ToolResult, ToolSpec
from .device_helpers import device_status_map, resolve_status_value


class QueryDeviceStatusToolRuntime:
    def __init__(self, adapter: MhaAdapter | None = None) -> None:
        self.adapter = adapter or MhaAdapter()

    def spec(self) -> ToolSpec:
        return ToolSpec(
            tool_id="query_device_status",
            model_name="query_device_status",
            description=(
                "Query live status for resolved device ids. When fields is omitted, returns a compact "
                "full status map for each device. When fields is provided, each field may be an exact "
                "path or a unique suffix such as fan.preset_mode; ambiguous fields are reported in "
                "unresolved_fields."
            ),
            strict=False,
            input_schema={
                "type": "object",
                "properties": {
                    "dids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "description": "Resolved device ids whose live status should be queried.",
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional status field paths to return, such as state, brightness, "
                            "fan.preset_mode, or bottom.remaining_running_time. Omit to return the "
                            "compact full status map."
                        ),
                    },
                },
                "required": ["dids"],
                "additionalProperties": False,
            },
        )

    def execute(self, call: ToolCall, ctx: Any) -> ToolResult:
        try:
            dids = self._normalize_dids(call.arguments.get("dids"))
            fields = self._normalize_fields(call.arguments.get("fields"))
        except Exception as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result={"received_arguments": dict(call.arguments)},
                error_code="INVALID_ARGUMENT",
                error_message=str(exc),
            )

        device_results: list[dict[str, Any]] = []
        unresolved_dids: list[str] = []
        unresolved_fields: list[dict[str, Any]] = []
        for did in dids:
            device = self.adapter.find_device(ctx.engine_data or {}, did)
            if device is None:
                unresolved_dids.append(did)
                continue
            if not fields:
                device_results.append({"did": did, "status": device_status_map(device)})
                continue
            resolved_status: dict[str, Any] = {}
            for field in fields:
                resolved, value, candidates = resolve_status_value(device, field)
                if resolved is None:
                    unresolved_fields.append({"did": did, "field": field, "candidates": candidates})
                    continue
                resolved_status[resolved] = value
            device_results.append({"did": did, "status": resolved_status})

        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            ok=True,
            result={
                "devices": device_results,
                "unresolved_dids": unresolved_dids,
                "unresolved_fields": unresolved_fields,
            },
        )

    @staticmethod
    def _normalize_dids(raw_dids: Any) -> list[str]:
        if not isinstance(raw_dids, list) or not raw_dids:
            raise ValueError("dids must be a non-empty list")
        result: list[str] = []
        for index, did in enumerate(raw_dids):
            if not isinstance(did, str) or not did.strip():
                raise ValueError(f"dids[{index}] must be a non-empty string")
            result.append(did.strip())
        return result

    @staticmethod
    def _normalize_fields(raw_fields: Any) -> list[str]:
        if raw_fields is None:
            return []
        if not isinstance(raw_fields, list):
            raise ValueError("fields must be a list when provided")
        result: list[str] = []
        for index, field in enumerate(raw_fields):
            if not isinstance(field, str) or not field.strip():
                raise ValueError(f"fields[{index}] must be a non-empty string")
            result.append(field.strip())
        return result
