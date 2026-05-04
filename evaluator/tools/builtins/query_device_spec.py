from __future__ import annotations

from typing import Any

from ...data.mha_adapter import MhaAdapter
from ..specs import ToolCall, ToolResult, ToolSpec
from .device_helpers import (
    device_did,
    devices,
    device_spid,
    device_userdata,
    room_lookup,
    strip_attribute_specs,
    strip_component_specs,
    strip_service_specs,
)


class QueryDeviceSpecToolRuntime:
    def __init__(self, adapter: MhaAdapter | None = None) -> None:
        self.adapter = adapter or MhaAdapter()

    def spec(self) -> ToolSpec:
        return ToolSpec(
            tool_id="query_device_spec",
            model_name="query_device_spec",
            description=(
                "Query capability specs for resolved device ids or a coarse candidate scope. Provide "
                "either `dids` or `scope`, but not both. Use this tool to discover supported "
                "attributes, services, and components before selection or control. Results are "
                "deduplicated by spid: each returned group contains one shared spec and the member "
                "dids. Live status is not included."
            ),
            strict=False,
            input_schema={
                "type": "object",
                "properties": {
                    "dids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "description": (
                            "Resolved device ids to inspect. Use this after the target devices are "
                            "already selected. Do not provide `dids` together with `scope`."
                        ),
                    },
                    "scope": {
                        "type": "object",
                        "description": (
                            "Coarse candidate scope for capability discovery only. Use this before "
                            "`select_device` when you need to know which attributes or services exist "
                            "in a candidate device set. Do not provide `scope` together with `dids`."
                        ),
                        "properties": {
                            "room_names": {"type": "array", "items": {"type": "string"}},
                            "categories": {"type": "array", "items": {"type": "string"}},
                            "subcategories": {"type": "array", "items": {"type": "string"}},
                            "tags_any": {"type": "array", "items": {"type": "string"}},
                        },
                        "additionalProperties": False,
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        )

    def execute(self, call: ToolCall, ctx: Any) -> ToolResult:
        try:
            requested_dids, resolved_dids, scope = self._normalize_selector(call.arguments, ctx.engine_data or {})
        except Exception as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result={"received_arguments": dict(call.arguments)},
                error_code="INVALID_ARGUMENT",
                error_message=str(exc),
            )

        groups: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        unresolved: list[str] = []
        for did in resolved_dids:
            device = self.adapter.find_device(ctx.engine_data or {}, did)
            if device is None:
                unresolved.append(did)
                continue
            spid = device_spid(device) or f"did:{did}"
            if spid not in groups:
                userdata = device_userdata(device)
                groups[spid] = {
                    "spid": spid,
                    "dids": [],
                    "name": device.get("name"),
                    "category": userdata.get("category"),
                    "subcategory": userdata.get("subcategory"),
                    "attributes": strip_attribute_specs(list(device.get("attributes") or [])),
                    "services": strip_service_specs(list(device.get("services") or [])),
                    "components": strip_component_specs(list(device.get("components") or [])),
                }
                order.append(spid)
            groups[spid]["dids"].append(did)

        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            ok=True,
            result={
                "requested_dids": requested_dids,
                "requested_scope": scope,
                "spec_groups": [groups[spid] for spid in order],
                "unresolved_dids": unresolved,
            },
        )

    def _normalize_selector(
        self,
        arguments: dict[str, Any],
        engine_data: dict[str, Any],
    ) -> tuple[list[str], list[str], dict[str, Any] | None]:
        raw_dids = arguments.get("dids")
        raw_scope = arguments.get("scope")

        has_dids = raw_dids is not None
        has_scope = raw_scope is not None
        if has_dids == has_scope:
            raise ValueError("exactly one of dids or scope must be provided")

        if has_dids:
            dids = self._normalize_dids(raw_dids)
            return dids, dids, None

        scope = self._normalize_scope(raw_scope)
        return [], self._resolve_scope_dids(scope, engine_data), scope

    @staticmethod
    def _normalize_dids(raw_dids: Any) -> list[str]:
        if not isinstance(raw_dids, list) or not raw_dids:
            raise ValueError("dids must be a non-empty list")
        normalized: list[str] = []
        for index, did in enumerate(raw_dids):
            if not isinstance(did, str) or not did.strip():
                raise ValueError(f"dids[{index}] must be a non-empty string")
            normalized.append(did.strip())
        return normalized

    @staticmethod
    def _normalize_scope(raw_scope: Any) -> dict[str, Any]:
        if not isinstance(raw_scope, dict) or not raw_scope:
            raise ValueError("scope must be a non-empty object")
        allowed_keys = {"room_names", "categories", "subcategories", "tags_any"}
        unexpected = set(raw_scope.keys()) - allowed_keys
        if unexpected:
            unexpected_list = ", ".join(sorted(unexpected))
            raise ValueError(f"scope contains unsupported fields: {unexpected_list}")

        normalized: dict[str, Any] = {}
        for key in ("room_names", "categories", "subcategories", "tags_any"):
            value = raw_scope.get(key)
            if value is None:
                continue
            if not isinstance(value, list) or not value:
                raise ValueError(f"scope.{key} must be a non-empty list when provided")
            normalized[key] = []
            for index, item in enumerate(value):
                if not isinstance(item, str) or not item.strip():
                    raise ValueError(f"scope.{key}[{index}] must be a non-empty string")
                normalized[key].append(item.strip())

        if not normalized:
            raise ValueError("scope must contain at least one populated filter")
        return normalized

    def _resolve_scope_dids(self, scope: dict[str, Any], engine_data: dict[str, Any]) -> list[str]:
        rooms_by_id = room_lookup(engine_data)
        matched_dids: list[str] = []
        for device in devices(engine_data):
            if not self._matches_scope(device, scope, rooms_by_id):
                continue
            did = device_did(device)
            if did is not None:
                matched_dids.append(did)
        return matched_dids

    @staticmethod
    def _matches_scope(
        device: dict[str, Any],
        scope: dict[str, Any],
        rooms_by_id: dict[str, dict[str, Any]],
    ) -> bool:
        userdata = device_userdata(device)
        room_id = userdata.get("room")
        room = rooms_by_id.get(str(room_id)) if room_id is not None else None

        room_names = scope.get("room_names")
        if room_names is not None and (room is None or room.get("name") not in room_names):
            return False

        categories = scope.get("categories")
        if categories is not None and userdata.get("category") not in categories:
            return False

        subcategories = scope.get("subcategories")
        if subcategories is not None and userdata.get("subcategory") not in subcategories:
            return False

        tags_any = scope.get("tags_any")
        if tags_any is not None:
            device_tags = {str(tag) for tag in userdata.get("tags") or []}
            if not device_tags.intersection(tags_any):
                return False

        return True
