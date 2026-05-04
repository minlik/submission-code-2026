from __future__ import annotations

from typing import Any

from ..specs import ToolCall, ToolResult, ToolSpec


class CreateAutomationCodeToolRuntime:
    def __init__(self) -> None:
        self.created_automations: list[dict[str, Any]] = []

    def spec(self) -> ToolSpec:
        return ToolSpec(
            tool_id="create_automation_code",
            model_name="create_automation",
            description=(
                "Create an automation rule by recording trigger conditions and Python control code. "
                "This stores the automation for inference output and does not execute it immediately."
            ),
            strict=False,
            input_schema={
                "type": "object",
                "properties": {
                    "conditions": {
                        "type": "object",
                        "properties": {
                            "time_cron": {
                                "type": ["string", "null"],
                                "description": (
                                    "Quartz 7-field cron string, or null when there is no time condition. "
                                    "Used for fixed time, recurring time, and delay requests,"
                                ),
                            },
                            "state_expr": {
                                "type": ["string", "null"],
                                "description": (
                                    "State expression such as device('1001').state == \"off\", device('1002').fan.state == \"on\", "
                                    "or null when unused. Using component.attribute for component attributes."
                                ),
                            },
                        },
                        "required": ["time_cron", "state_expr"],
                        "additionalProperties": False,
                    },
                    "code": {
                        "type": "string",
                        "description": (
                            "Python control statements to run when the automation triggers. Only include "
                            "control logic. Do not print(...), do not describe the rule in prose, and do "
                            "not include device or room queries."
                        ),
                    },
                },
                "required": ["conditions", "code"],
                "additionalProperties": False,
            },
        )

    def execute(self, call: ToolCall, ctx: Any) -> ToolResult:
        try:
            conditions = self._normalize_conditions(call.arguments.get("conditions"))
            code = self._normalize_code(call.arguments.get("code"))
        except Exception as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result={"received_arguments": dict(call.arguments)},
                error_code="INVALID_ARGUMENT",
                error_message=str(exc),
            )

        created = {
            "representation": "code",
            "created": True,
            "conditions": conditions,
            "code": code,
        }
        self.created_automations.append(created)
        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            ok=True,
            result=created,
        )

    def reset_created_automations(self) -> None:
        self.created_automations = []

    def drain_created_automations(self) -> list[dict[str, Any]]:
        drained = list(self.created_automations)
        self.created_automations = []
        return drained

    @staticmethod
    def _normalize_conditions(raw_conditions: Any) -> dict[str, Any]:
        if not isinstance(raw_conditions, dict):
            raise ValueError("conditions must be an object")
        if set(raw_conditions.keys()) != {"time_cron", "state_expr"}:
            raise ValueError("conditions must contain exactly time_cron and state_expr")
        time_cron = raw_conditions.get("time_cron")
        state_expr = raw_conditions.get("state_expr")
        if time_cron is not None and not isinstance(time_cron, str):
            raise ValueError("conditions.time_cron must be string or null")
        if state_expr is not None and not isinstance(state_expr, str):
            raise ValueError("conditions.state_expr must be string or null")
        return {"time_cron": time_cron, "state_expr": state_expr}

    @staticmethod
    def _normalize_code(raw_code: Any) -> str:
        if not isinstance(raw_code, str) or not raw_code.strip():
            raise ValueError("missing required string argument: code")
        return raw_code.strip()
