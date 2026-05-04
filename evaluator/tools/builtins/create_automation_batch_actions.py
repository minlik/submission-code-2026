from __future__ import annotations

from typing import Any

from ...inference.action_simulator import ActionSimulator
from ..specs import ToolCall, ToolResult, ToolSpec
from .control_device_batch import ControlDeviceBatchToolRuntime


class CreateAutomationBatchActionsToolRuntime:
    def __init__(self, action_simulator: ActionSimulator | None = None) -> None:
        self.action_simulator = action_simulator or ActionSimulator()
        self.created_automations: list[dict[str, Any]] = []
        self.batch_runtime = ControlDeviceBatchToolRuntime(action_simulator=self.action_simulator)

    def spec(self) -> ToolSpec:
        return ToolSpec(
            tool_id="create_automation_batch_actions",
            model_name="create_automation",
            description=(
                "Create an automation rule by recording trigger conditions and batch-capable device "
                "actions. Each batch action uses the same locator and argument object for multiple "
                "device ids. Every did in an action must independently support that locator and those "
                "arguments; otherwise the action is rejected. This tool validates the actions, stores "
                "the automation for inference output, and does not execute it immediately."
            ),
            strict=False,
            input_schema={
                "type": "object",
                "properties": {
                    "conditions": {
                        "type": "object",
                        "description": "Automation trigger conditions. Provide both keys. Use null for an unused condition.",
                        "properties": {
                            "time_cron": {
                                "type": ["string", "null"],
                                "description": "Quartz 7-field cron string, or null when there is no time-based trigger.",
                            },
                            "state_expr": {
                                "type": ["string", "null"],
                                "description": (
                                    "State expression such as device('1001').state == \"off\" or "
                                    "device('1002').fan.state == \"on\", or null when there is no "
                                    "state-based trigger. Use component.attribute for component attributes."
                                ),
                            },
                        },
                        "required": ["time_cron", "state_expr"],
                        "additionalProperties": False,
                    },
                    "actions": {
                        "type": "array",
                        "description": "Batch-capable device actions to run when the automation triggers.",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "dids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "minItems": 1,
                                    "description": (
                                        "Resolved device ids for one batch action. Every did in the "
                                        "action must support the same locator and arguments."
                                    ),
                                },
                                "locator": {
                                    "type": "string",
                                    "description": (
                                        "Exact service locator string. Use service_name for device-level "
                                        "services and component_name.service_name for component services."
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
                            "required": ["dids", "locator"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["conditions", "actions"],
                "additionalProperties": False,
            },
        )

    def execute(self, call: ToolCall, ctx: Any) -> ToolResult:
        try:
            conditions = self._normalize_conditions(call.arguments.get("conditions"))
            batch_actions = self._normalize_actions(call.arguments.get("actions"))
        except Exception as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result={"received_arguments": dict(call.arguments)},
                error_code="INVALID_ARGUMENT",
                error_message=str(exc),
            )

        flat_actions: list[dict[str, Any]] = [
            {
                "did": did,
                "locator": action["locator"],
                "arguments": dict(action["arguments"]),
            }
            for action in batch_actions
            for did in action["dids"]
        ]
        if ctx.engine_data:
            trial_env = self.action_simulator.adapter.build_env(ctx.engine_data)
            for index, action in enumerate(batch_actions):
                validation = self.batch_runtime.execute(
                    ToolCall(
                        call_id=f"{call.call_id}:{index}",
                        tool_name="control_device_batch",
                        arguments=action,
                    ),
                    ctx.__class__(
                        env=trial_env,
                        engine_data=ctx.engine_data,
                        profile_name=ctx.profile_name,
                        step_index=ctx.step_index,
                        sample_meta=ctx.sample_meta,
                    ),
                )
                if not validation.ok:
                    return ToolResult(
                        call_id=call.call_id,
                        tool_name=call.tool_name,
                        ok=False,
                        result={
                            "representation": "actions",
                            "conditions": conditions,
                            "batch_actions": batch_actions,
                        },
                        error_code="AUTOMATION_ACTION_VALIDATION_FAILED",
                        error_message=validation.error_message or validation.error_code or "batch automation validation failed",
                    )

        created = {
            "representation": "actions",
            "created": True,
            "conditions": conditions,
            "batch_actions": batch_actions,
            "actions": flat_actions,
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
            dids = action.get("dids")
            locator = action.get("locator")
            if not isinstance(dids, list) or not dids:
                raise ValueError(f"actions[{index}].dids must be a non-empty list")
            normalized_dids: list[str] = []
            for did_index, did in enumerate(dids):
                if not isinstance(did, str) or not did.strip():
                    raise ValueError(f"actions[{index}].dids[{did_index}] must be a non-empty string")
                normalized_dids.append(did.strip())
            if not isinstance(locator, str) or not locator.strip():
                raise ValueError(f"actions[{index}] missing required string: locator")
            arguments = action.get("arguments")
            if arguments is None:
                arguments = {}
            if not isinstance(arguments, dict):
                raise ValueError(f"actions[{index}].arguments must be an object or null")
            normalized.append(
                {
                    "dids": normalized_dids,
                    "locator": locator.strip(),
                    "arguments": dict(arguments),
                }
            )
        return normalized
