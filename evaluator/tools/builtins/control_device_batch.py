from __future__ import annotations

from typing import Any

from ...inference.action_simulator import ActionSimulator
from ..specs import ToolCall, ToolContext, ToolResult, ToolSpec
from .control_device import ControlDeviceToolRuntime


class ControlDeviceBatchToolRuntime:
    def __init__(self, action_simulator: ActionSimulator | None = None) -> None:
        self.action_simulator = action_simulator or ActionSimulator()
        self.single_runtime = ControlDeviceToolRuntime(action_simulator=self.action_simulator)

    def spec(self) -> ToolSpec:
        return ToolSpec(
            tool_id="control_device_batch",
            model_name="control_device_batch",
            description=(
                "Immediately control multiple resolved device ids with one exact service locator and "
                "one shared argument object. Each did is validated independently against the same "
                "locator and arguments. Devices that fail validation or execution are reported per did; "
                "other devices still run."
            ),
            strict=False,
            input_schema={
                "type": "object",
                "properties": {
                    "dids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "description": "Resolved target device ids. The tool validates each device independently.",
                    },
                    "locator": {
                        "type": "string",
                        "description": (
                            "Exact service locator string. Use service_name for device-level services "
                            "and component_name.service_name for component services."
                        ),
                    },
                    "arguments": {
                        "type": ["object", "null"],
                        "description": (
                            "Optional service argument object. Keys must match the target service's "
                            "declared argument names exactly. Pass null or {} for services without "
                            "arguments. For parameterized services, provide every required argument "
                            "and do not include undeclared keys."
                        ),
                        "additionalProperties": True,
                    },
                },
                "required": ["dids", "locator"],
                "additionalProperties": False,
            },
        )

    def execute(self, call: ToolCall, ctx: Any) -> ToolResult:
        try:
            dids = self._normalize_dids(call.arguments.get("dids"))
            locator = self._normalize_string(call.arguments.get("locator"), "locator")
            arguments = call.arguments.get("arguments")
            if arguments is None:
                arguments = {}
            if not isinstance(arguments, dict):
                raise ValueError("arguments must be an object when provided")
        except Exception as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result={"received_arguments": dict(call.arguments)},
                error_code="INVALID_ARGUMENT",
                error_message=str(exc),
            )

        results: list[dict[str, Any]] = []
        changed_count = 0
        noop_count = 0
        failed_count = 0
        first_error_code: str | None = None
        first_error_message: str | None = None
        for did in dids:
            single = self.single_runtime.execute(
                ToolCall(
                    call_id=f"{call.call_id}:{did}",
                    tool_name="control_device",
                    arguments={"did": did, "locator": locator, "arguments": dict(arguments)},
                ),
                ToolContext(
                    env=ctx.env,
                    engine_data=ctx.engine_data,
                    profile_name=ctx.profile_name,
                    step_index=ctx.step_index,
                    sample_meta=ctx.sample_meta,
                ),
            )
            if single.ok:
                status = single.result.get("execution", {}).get("status")
                if status == "noop":
                    noop_count += 1
                else:
                    changed_count += 1
                results.append(
                    {
                        "did": did,
                        "status": status,
                        "state_changes": single.result.get("diagnostics", {}).get("state_changes", []),
                    }
                )
                continue
            failed_count += 1
            first_error_code = first_error_code or single.error_code
            first_error_message = first_error_message or single.error_message
            results.append(
                {
                    "did": did,
                    "status": "failed",
                    "error_code": single.error_code,
                    "error_message": single.error_message,
                }
            )

        payload = {
            "requested_dids": dids,
            "locator": locator,
            "arguments": dict(arguments),
            "accepted": failed_count == 0,
            "summary": {
                "requested_count": len(dids),
                "changed_count": changed_count,
                "noop_count": noop_count,
                "failed_count": failed_count,
            },
            "results": results,
        }
        if failed_count:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result=payload,
                error_code=first_error_code or "BATCH_EXECUTION_FAILED",
                error_message=first_error_message or "batch control failed",
            )
        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            ok=True,
            result=payload,
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
    def _normalize_string(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return value.strip()
