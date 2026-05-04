from __future__ import annotations

from typing import Any

from mha.env import PyExec

from ..specs import ToolCall, ToolResult, ToolSpec


class PyExecToolRuntime:
    def spec(self) -> ToolSpec:
        return ToolSpec(
            tool_id="pyexec",
            model_name="pyexec",
            description=(
                "Run one Python block against the current home for immediate query or immediate control. "
                "For delayed, scheduled, or state-triggered tasks, use create_automation instead."
            ),
            strict=False,
            input_schema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": (
                            "A single Python block. Available symbols: home: Home; home.outdoor: Outdoor | None; "
                            "home.rooms: list[Room]; home.devices: list[Device]; home.get_room(id: str) -> Room; "
                            "home.get_device(did: str) -> Device; get_device(did: str) -> Device; "
                            "get_room(id: str) -> Room; get_devices() -> list[Device]; get_rooms() -> list[Room]; "
                            'render_device(device: Device, mode: Literal["brief", "spec", "status", "spec_status"]) -> str; '
                            "render_room(room: Room) -> str. Use print(...) for readable output; inspect capabilities "
                            'with print(render_device(device, "spec")) before calling services. Examples: '
                            'print(render_device(get_device("1234"), "spec")); '
                            'get_device("1234").light.turn_on(); '
                            'for dev in home.devices:\n    if dev.category == "light":\n        dev.turn_on()'
                        ),
                    },
                },
                "required": ["code"],
                "additionalProperties": False,
            },
        )

    def execute(self, call: ToolCall, ctx: Any) -> ToolResult:
        code = call.arguments.get("code")
        if not isinstance(code, str) or not code.strip():
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result={"received_arguments": dict(call.arguments)},
                error_code="INVALID_ARGUMENT",
                error_message="missing required string argument: code",
            )

        obs, *_ = ctx.env.step(PyExec(code))
        stdout = str(getattr(obs, "output", "") or "")
        error = getattr(obs, "error", None)
        if error is not None:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result={
                    "stdout": stdout,
                    "stderr": str(error),
                    "exit_state": "runtime_error",
                },
                error_code="EXECUTION_ERROR",
                error_message=str(error),
            )

        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            ok=True,
            result={
                "stdout": stdout,
                "stderr": "",
                "exit_state": "success",
            },
        )
