from __future__ import annotations

from typing import Any

from ...inference.action_simulator import ActionSimulator
from ..specs import ToolCall, ToolResult, ToolSpec


class CreateAutomationActionsToolRuntime:
    def __init__(self, action_simulator: ActionSimulator | None = None) -> None:
        self.action_simulator = action_simulator or ActionSimulator()
        self.created_automations: list[dict[str, Any]] = []

    def spec(self) -> ToolSpec:
        return ToolSpec(
            tool_id="create_automation_actions",
            model_name="create_automation",
            description=(
                "Create an automation rule by recording trigger conditions and device actions. "
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
                                "description": "Quartz 7-field cron string, or null when there is no time condition.",
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
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "did": {"type": "string", "description": "Target device id for the action."},
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
                                        "Optional service argument object for this action. Keys must match "
                                        "the target service's declared argument names exactly. Omit this "
                                        "field, pass null, or pass {} for services without arguments. For "
                                        "parameterized services, provide every required argument and do not "
                                        "include undeclared keys."
                                    ),
                                    "additionalProperties": True,
                                },
                            },
                            "required": ["did", "locator"],
                            "additionalProperties": False,
                        },
                        "minItems": 1,
                    },
                },
                "required": ["conditions", "actions"],
                "additionalProperties": False,
            },
        )

    def execute(self, call: ToolCall, ctx: Any) -> ToolResult:
        try:
            conditions = self._normalize_conditions(call.arguments.get("conditions"))
            actions = self._normalize_actions(call.arguments.get("actions"))
        except Exception as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result={"received_arguments": dict(call.arguments)},
                error_code="INVALID_ARGUMENT",
                error_message=str(exc),
            )

        if ctx.engine_data:
            trial_env = self.action_simulator.adapter.build_env(ctx.engine_data)
            try:
                for action in actions:
                    normalized = self.action_simulator.normalize_action(ctx.engine_data, action)
                    self.action_simulator._apply_action(trial_env, normalized)
            except Exception as exc:
                return ToolResult(
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    ok=False,
                    result={
                        "representation": "actions",
                        "conditions": conditions,
                        "actions": actions,
                    },
                    error_code="AUTOMATION_ACTION_VALIDATION_FAILED",
                    error_message=str(exc),
                )

        created = {
            "representation": "actions",
            "created": True,
            "conditions": conditions,
            "actions": actions,
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
    def _normalize_actions(raw_actions: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_actions, list) or not raw_actions:
            raise ValueError("actions must be a non-empty list")
        normalized: list[dict[str, Any]] = []
        for index, action in enumerate(raw_actions):
            if not isinstance(action, dict):
                raise ValueError(f"actions[{index}] must be an object")
            did = action.get("did")
            locator = action.get("locator")
            if not isinstance(did, str) or not did.strip():
                raise ValueError(f"actions[{index}] missing required string: did")
            if not isinstance(locator, str) or not locator.strip():
                raise ValueError(f"actions[{index}] missing required string: locator")
            item = {"did": did.strip(), "locator": locator.strip()}
            if "arguments" in action:
                item["arguments"] = action.get("arguments")
            normalized.append(item)
        return normalized
