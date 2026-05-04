from __future__ import annotations

from typing import Any

from ...inference.action_simulator import ActionSimulator
from ..specs import ToolCall, ToolResult, ToolSpec


class _ControlValidationError(ValueError):
    def __init__(self, failure_kind: str, message: str) -> None:
        super().__init__(message)
        self.failure_kind = failure_kind
        self.message = message


class ControlDeviceToolRuntime:
    def __init__(self, action_simulator: ActionSimulator | None = None) -> None:
        self.action_simulator = action_simulator or ActionSimulator()

    def spec(self) -> ToolSpec:
        return ToolSpec(
            tool_id="control_device",
            model_name="control_device",
            description=(
                "Immediately control a resolved device by calling an exact service locator. "
                "Use create_automation instead for delayed, scheduled, or state-triggered tasks."
            ),
            strict=False,
            input_schema={
                "type": "object",
                "properties": {
                    "did": {"type": "string", "description": "Resolved target device id."},
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
                "required": ["did", "locator"],
                "additionalProperties": False,
            },
        )

    def execute(self, call: ToolCall, ctx: Any) -> ToolResult:
        request = self._best_effort_request(call.arguments)
        target = self._best_effort_target(ctx.engine_data or {}, request)
        try:
            request = self._build_request(call.arguments)
            target = self._resolve_target(ctx.engine_data or {}, request["did"], request["locator"])
        except ValueError as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result=self._failure_result(
                    request=request,
                    target=target,
                    failure_stage="validation",
                    failure_kind="INVALID_ARGUMENT",
                    diagnostics={
                        "received_arguments": dict(call.arguments),
                    },
                ),
                error_code="INVALID_ARGUMENT",
                error_message=str(exc),
            )

        try:
            payload = self._build_payload(call.arguments, ctx.engine_data or {})
        except _ControlValidationError as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result=self._failure_result(
                    request=request,
                    target=target,
                    failure_stage="validation",
                    failure_kind=exc.failure_kind,
                    diagnostics={
                        "available_locators": self._available_locators(target.get("_device")),
                        "expected_arguments": self._expected_arguments_for_locator(target.get("_device"), request["locator"]),
                    },
                ),
                error_code=exc.failure_kind,
                error_message=exc.message,
            )
        except ValueError as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result=self._failure_result(
                    request=request,
                    target=target,
                    failure_stage="validation",
                    failure_kind="INVALID_ARGUMENT",
                    diagnostics={
                        "received_arguments": dict(call.arguments),
                    },
                ),
                error_code="INVALID_ARGUMENT",
                error_message=str(exc),
            )

        before = self._snapshot_device_state(ctx.env, payload["did"])
        obs, *_ = ctx.env.step(payload)
        error = getattr(obs, "error", None)
        if error is not None:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result=self._failure_result(
                    request=request,
                    target=target,
                    failure_stage="execution",
                    failure_kind="EXECUTION_ERROR",
                    diagnostics={
                        "available_locators": self._available_locators(target.get("_device")),
                        "expected_arguments": self._expected_arguments_for_locator(target.get("_device"), request["locator"]),
                    },
                ),
                error_code="EXECUTION_ERROR",
                error_message=str(error),
            )

        after = self._snapshot_device_state(ctx.env, payload["did"])
        state_changes = self._diff_device_state(before, after)
        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            ok=True,
            result=self._success_result(
                request=request,
                target=target,
                state_changes=state_changes,
            ),
        )

    def _build_payload(self, arguments: dict[str, Any], engine_data: dict[str, Any]) -> dict[str, Any]:
        request = self._build_request(arguments)
        device = self._find_device(engine_data, request["did"])
        self._validate_request(engine_data, request, device)
        action: dict[str, Any] = {
            "name": "control_device",
            "did": request["did"],
            "locator": request["locator"],
        }
        if "value" in arguments:
            raise ValueError("control_device only supports service locator; value is not supported")
        if "operator" in arguments:
            raise ValueError("control_device only supports service locator; operator is not supported")
        if "cron" in arguments:
            raise ValueError("control_device only supports immediate service calls; cron is not supported")
        action["arguments"] = request["arguments"]
        return self.action_simulator.normalize_action(engine_data, action)

    @staticmethod
    def _build_request(arguments: dict[str, Any]) -> dict[str, Any]:
        did = arguments.get("did")
        locator = arguments.get("locator")
        if not isinstance(did, str) or not did.strip():
            raise ValueError("missing required string argument: did")
        if not isinstance(locator, str) or not locator.strip():
            raise ValueError("missing required string argument: locator")
        call_args = arguments.get("arguments", {})
        if call_args is None:
            call_args = {}
        if not isinstance(call_args, dict):
            raise ValueError("arguments must be an object")
        return {
            "did": did.strip(),
            "locator": locator.strip(),
            "arguments": dict(call_args),
        }

    @staticmethod
    def _best_effort_request(arguments: dict[str, Any]) -> dict[str, Any]:
        did = arguments.get("did")
        locator = arguments.get("locator")
        call_args = arguments.get("arguments", {})
        if call_args is None:
            call_args = {}
        normalized_args = dict(call_args) if isinstance(call_args, dict) else {}
        return {
            "did": did.strip() if isinstance(did, str) else did,
            "locator": locator.strip() if isinstance(locator, str) else locator,
            "arguments": normalized_args,
        }

    def _best_effort_target(self, engine_data: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
        did = request.get("did")
        locator = request.get("locator")
        target: dict[str, Any] = {"did": did}
        if isinstance(locator, str) and "." in locator:
            target["component"] = locator.split(".", 1)[0]
        if not isinstance(did, str) or not did:
            return target
        device = self._find_device(engine_data, did)
        if device is None:
            return target
        userdata = device.get("userdata") or {}
        target["device_name"] = device.get("name") or userdata.get("subcategory")
        if userdata.get("room") is not None:
            target["room_id"] = userdata.get("room")
            room_name = self._room_name(engine_data, userdata.get("room"))
            if room_name:
                target["room_name"] = room_name
        target["_device"] = device
        return target

    def _resolve_target(self, engine_data: dict[str, Any], did: str, locator: str) -> dict[str, Any]:
        device = self._find_device(engine_data, did)
        target: dict[str, Any] = {"did": did}
        if "." in locator:
            target["component"] = locator.split(".", 1)[0]
        if device is None:
            return target
        userdata = device.get("userdata") or {}
        target["device_name"] = device.get("name") or userdata.get("subcategory")
        if userdata.get("room") is not None:
            target["room_id"] = userdata.get("room")
            room_name = self._room_name(engine_data, userdata.get("room"))
            if room_name:
                target["room_name"] = room_name
        target["_device"] = device
        return target

    def _validate_request(self, engine_data: dict[str, Any], request: dict[str, Any], device: dict[str, Any] | None) -> None:
        if device is None:
            raise _ControlValidationError("DEVICE_NOT_FOUND", f"device {request['did']} not found")
        service = self._service_spec(device, request["locator"])
        if service is None:
            available = self._available_locators(device)
            message = f"service {request['locator']} not found"
            if len(available) == 1:
                message += f"; expected {available[0]}"
            raise _ControlValidationError("SERVICE_NOT_FOUND", message)

        declared_args = list(service.get("arguments") or [])
        declared_names = {str(arg.get("name")) for arg in declared_args if arg.get("name") is not None}
        provided_names = set(request["arguments"].keys())

        missing = [arg for arg in declared_args if arg.get("name") not in provided_names]
        if missing:
            missing_names = ", ".join(str(arg.get("name")) for arg in missing if arg.get("name") is not None)
            raise _ControlValidationError("MISSING_ARGUMENT", f"missing required arguments: {missing_names}")

        unexpected = sorted(name for name in provided_names if name not in declared_names)
        if unexpected:
            raise _ControlValidationError("UNEXPECTED_ARGUMENT", f"unexpected arguments: {', '.join(unexpected)}")

        for arg in declared_args:
            self._validate_argument_value(arg, request["arguments"].get(arg.get("name")))

    @staticmethod
    def _validate_argument_value(arg_spec: dict[str, Any], value: Any) -> None:
        name = str(arg_spec.get("name"))
        options = arg_spec.get("options")
        if isinstance(options, list) and options and value not in options:
            raise _ControlValidationError("INVALID_ARGUMENT_VALUE", f"invalid value for {name}: {value}")
        value_range = arg_spec.get("range")
        if isinstance(value_range, list) and len(value_range) == 2 and value is not None:
            if not isinstance(value, (int, float)):
                raise _ControlValidationError("INVALID_ARGUMENT_VALUE", f"invalid value for {name}: {value}")
            low, high = value_range
            if value < low or value > high:
                raise _ControlValidationError("INVALID_ARGUMENT_VALUE", f"invalid value for {name}: {value}")

    def _find_device(self, engine_data: dict[str, Any], did: str) -> dict[str, Any] | None:
        finder = getattr(self.action_simulator.adapter, "find_device", None)
        if callable(finder):
            return finder(engine_data, did)
        return None

    def _room_name(self, engine_data: dict[str, Any], room_id: Any) -> str | None:
        resolver = getattr(self.action_simulator.adapter, "room_name", None)
        if callable(resolver):
            return resolver(engine_data, room_id)
        return None

    @staticmethod
    def _available_locators(device: dict[str, Any] | None) -> list[str]:
        if not isinstance(device, dict):
            return []
        locators: list[str] = []
        for service in device.get("services") or []:
            name = service.get("name")
            if name:
                locators.append(str(name))
        for component in device.get("components") or []:
            component_name = component.get("name")
            if not component_name:
                continue
            for service in component.get("services") or []:
                service_name = service.get("name")
                if service_name:
                    locators.append(f"{component_name}.{service_name}")
        return locators

    def _service_spec(self, device: dict[str, Any], locator: str) -> dict[str, Any] | None:
        if "." not in locator:
            for service in device.get("services") or []:
                if str(service.get("name")) == locator:
                    return service
            return None

        component_name, service_name = locator.split(".", 1)
        for component in device.get("components") or []:
            if str(component.get("name")) != component_name:
                continue
            for service in component.get("services") or []:
                if str(service.get("name")) == service_name:
                    return service
        return None

    def _expected_arguments_for_locator(self, device: dict[str, Any] | None, locator: str) -> list[dict[str, Any]]:
        if not isinstance(device, dict):
            return []
        service = self._service_spec(device, locator)
        if service is None:
            return []
        expected: list[dict[str, Any]] = []
        for arg in service.get("arguments") or []:
            if not isinstance(arg, dict):
                continue
            item = {"name": arg.get("name"), "required": True}
            for key in ("type", "range", "options", "unit", "precision"):
                if key in arg:
                    item[key] = arg.get(key)
            expected.append(item)
        return expected

    def _snapshot_device_state(self, env: Any, did: str) -> dict[str, Any]:
        snapshot = self.action_simulator._snapshot(env)
        return {attribute: value for (snapshot_did, attribute), value in snapshot.items() if str(snapshot_did) == str(did)}

    @staticmethod
    def _diff_device_state(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []
        for attribute in sorted(set(before.keys()) | set(after.keys())):
            prev_value = before.get(attribute)
            cur_value = after.get(attribute)
            if prev_value != cur_value:
                changes.append({"attribute": attribute, "before": prev_value, "after": cur_value})
        return changes

    def _success_result(
        self,
        request: dict[str, Any],
        target: dict[str, Any],
        state_changes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "request": request,
            "target": self._public_target(target),
            "execution": {
                "status": "changed" if state_changes else "noop",
                "accepted": True,
            },
            "diagnostics": {
                "state_changes": state_changes,
            },
        }

    def _failure_result(
        self,
        request: dict[str, Any],
        target: dict[str, Any],
        failure_stage: str,
        failure_kind: str,
        diagnostics: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "request": request,
            "target": self._public_target(target),
            "execution": {
                "status": "failed",
                "accepted": False,
                "failure_stage": failure_stage,
                "failure_kind": failure_kind,
            },
            "diagnostics": diagnostics,
        }

    @staticmethod
    def _public_target(target: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in target.items() if key != "_device"}
