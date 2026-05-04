from __future__ import annotations

from typing import Any

from ..specs import ToolCall, ToolResult, ToolSpec
from .device_helpers import (
    device_summary,
    device_userdata,
    devices,
    devices_grouped_by_room,
    group_summaries_by_room,
    group_summaries_by_spid,
    has_component,
    resolve_attribute_exists,
    resolve_has_service,
    resolve_status_value,
    room_lookup,
)


class SelectDeviceToolRuntime:
    def spec(self) -> ToolSpec:
        spec_filter_schema = {
            "type": "object",
            "description": "Capability and structure filters. All items are ANDed.",
            "properties": {
                "field": {
                    "type": "string",
                    "description": (
                        "Attribute path, service locator, or component name depending on op. "
                        "Attribute and service fields support exact path or unique suffix matching."
                    ),
                },
                "op": {
                    "type": "string",
                    "enum": ["has_attribute", "has_service", "has_component"],
                    "description": "One of has_attribute, has_service, or has_component.",
                },
            },
            "required": ["field", "op"],
            "additionalProperties": False,
        }
        status_filter_schema = {
            "type": "object",
            "description": "Live status comparisons. All items are ANDed.",
            "properties": {
                "field": {
                    "type": "string",
                    "description": (
                        "Status field path such as state, brightness, or fan.preset_mode. "
                        "Supports exact path or unique suffix matching."
                    ),
                },
                "op": {
                    "type": "string",
                    "enum": ["=", "!=", ">", ">=", "<", "<=", "in", "not_in"],
                    "description": "Comparison operator.",
                },
                "value": {
                    "description": "Comparison value for the selected operator.",
                },
            },
            "required": ["field", "op", "value"],
            "additionalProperties": False,
        }
        scope_schema = {
            "type": "object",
            "description": "Optional identity filters. All populated subfields are ANDed.",
            "properties": {
                "categories": {"type": "array", "items": {"type": "string"}},
                "subcategories": {"type": "array", "items": {"type": "string"}},
                "spids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Exact spid filter. Low-level override; usually omit unless spid is already known.",
                },
                "tags_any": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Require at least one overlapping device tag.",
                },
                "name_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Device name must contain at least one of these substrings.",
                },
            },
            "additionalProperties": False,
        }
        subquery_schema = {
            "type": "object",
            "description": "Subquery evaluated only against devices in the same room as the candidate device.",
            "properties": {
                "device_scope": scope_schema,
                "spec_filters": {
                    "type": "array",
                    "description": "Capability and structure filters for same-room matching.",
                    "items": spec_filter_schema,
                },
                "status_filters": {
                    "type": "array",
                    "description": "Live status comparisons for same-room matching.",
                    "items": status_filter_schema,
                },
            },
            "additionalProperties": False,
        }
        return ToolSpec(
            tool_id="select_device",
            model_name="select_device",
            description=(
                "Select devices with structured device, room, spec, and status filters. "
                "All provided filters are ANDed. same_room_has and same_room_lacks only inspect "
                "devices in the same room as each candidate. Supports simple status-based sorting, "
                "top-N limiting with ties at the boundary, and lightweight aggregations."
            ),
            strict=False,
            input_schema={
                "type": "object",
                "properties": {
                    "device_scope": scope_schema,
                    "room_scope": {
                        "type": "object",
                        "description": "Optional room metadata filters. All populated subfields are ANDed.",
                        "properties": {
                            "include_room_names": {"type": "array", "items": {"type": "string"}},
                            "exclude_room_names": {"type": "array", "items": {"type": "string"}},
                            "include_room_types": {"type": "array", "items": {"type": "string"}},
                            "exclude_room_types": {"type": "array", "items": {"type": "string"}},
                            "floors": {"type": "array", "items": {"type": "integer"}},
                        },
                        "additionalProperties": False,
                    },
                    "spec_filters": {
                        "type": "array",
                        "description": (
                            "Capability and structure filters. Use this for attribute existence, "
                            "supported services, or component presence, not for current status values."
                        ),
                        "items": spec_filter_schema,
                    },
                    "status_filters": {
                        "type": "array",
                        "description": "Live status comparisons. All items are ANDed.",
                        "items": status_filter_schema,
                    },
                    "same_room_has": {
                        "type": "array",
                        "description": (
                            "Each subquery must be satisfied by at least one device in the same room "
                            "as the candidate. Current implementation checks all room devices, "
                            "including the candidate itself if it matches."
                        ),
                        "items": subquery_schema,
                    },
                    "same_room_lacks": {
                        "type": "array",
                        "description": (
                            "Each subquery must be absent from the candidate's room. Current "
                            "implementation checks all room devices, including the candidate itself."
                        ),
                        "items": subquery_schema,
                    },
                    "sort": {
                        "type": "object",
                        "description": (
                            "Sort matched devices by a live status field before applying limit. "
                            "Missing or ambiguous values sort last."
                        ),
                        "properties": {
                            "field": {"type": "string", "description": "Status field used for sorting."},
                            "order": {"type": "string", "enum": ["asc", "desc"], "description": "Sort order."},
                        },
                        "required": ["field", "order"],
                        "additionalProperties": False,
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "description": (
                            "Maximum rank cutoff after sorting. If the limit boundary is tied, "
                            "all devices with the same comparable value are kept, so the final "
                            "result may contain more than this number of devices."
                        ),
                    },
                    "aggregate": {
                        "type": "object",
                        "description": "Optional aggregate over the matched device set.",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": [
                                    "list",
                                    "count",
                                    "exists",
                                    "distinct_rooms",
                                    "distinct_room_count",
                                    "max",
                                    "min",
                                ],
                                "description": "Aggregate type.",
                            },
                            "field": {
                                "type": "string",
                                "description": "Required for max and min. Status field used for comparison.",
                            },
                        },
                        "required": ["type"],
                        "additionalProperties": False,
                    },
                },
                "additionalProperties": False,
            },
        )

    def execute(self, call: ToolCall, ctx: Any) -> ToolResult:
        try:
            result = self._select(call.arguments, ctx.engine_data or {})
        except Exception as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                result={"received_arguments": dict(call.arguments)},
                error_code="INVALID_ARGUMENT",
                error_message=str(exc),
            )
        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            ok=True,
            result=result,
        )

    def _select(self, arguments: dict[str, Any], engine_data: dict[str, Any]) -> dict[str, Any]:
        rooms_by_id = room_lookup(engine_data)
        room_devices = devices_grouped_by_room(engine_data)
        matched: list[dict[str, Any]] = []
        for device in devices(engine_data):
            if not self._matches_device_scope(device, arguments.get("device_scope")):
                continue
            if not self._matches_room_scope(device, arguments.get("room_scope"), rooms_by_id):
                continue
            if not self._matches_spec_filters(device, arguments.get("spec_filters") or []):
                continue
            if not self._matches_status_filters(device, arguments.get("status_filters") or []):
                continue
            if not self._matches_same_room(device, room_devices, arguments.get("same_room_has") or [], expect_match=True):
                continue
            if not self._matches_same_room(device, room_devices, arguments.get("same_room_lacks") or [], expect_match=False):
                continue
            matched.append(device_summary(device, rooms_by_id))

        matched = self._apply_sort_and_limit(matched, devices(engine_data), arguments, rooms_by_id)
        aggregate = dict(arguments.get("aggregate") or {"type": "list"})
        return {
            "count": len(matched),
            "devices": matched,
            "groups_by_spid": group_summaries_by_spid(matched),
            "groups_by_room": group_summaries_by_room(matched),
            "aggregate_result": self._aggregate_result(matched, devices(engine_data), aggregate),
        }

    @staticmethod
    def _matches_device_scope(device: dict[str, Any], scope: Any) -> bool:
        if not isinstance(scope, dict):
            return True
        userdata = device_userdata(device)
        category = userdata.get("category")
        subcategory = userdata.get("subcategory")
        spid = userdata.get("spid")
        tags = {str(tag) for tag in userdata.get("tags") or []}
        name = str(device.get("name") or "")

        categories = scope.get("categories") or []
        if categories and category not in categories:
            return False
        subcategories = scope.get("subcategories") or []
        if subcategories and subcategory not in subcategories:
            return False
        spids = scope.get("spids") or []
        if spids and spid not in spids:
            return False
        tags_any = scope.get("tags_any") or []
        if tags_any and not (tags & {str(tag) for tag in tags_any}):
            return False
        name_keywords = [str(item) for item in (scope.get("name_keywords") or []) if str(item).strip()]
        if name_keywords and not any(keyword in name for keyword in name_keywords):
            return False
        return True

    @staticmethod
    def _matches_room_scope(
        device: dict[str, Any],
        scope: Any,
        rooms_by_id: dict[str, dict[str, Any]],
    ) -> bool:
        if not isinstance(scope, dict):
            return True
        room = rooms_by_id.get(str(device_userdata(device).get("room")))
        room_name = None if room is None else room.get("name")
        room_type = None if room is None else room.get("type")
        floor = None if room is None else room.get("floor")

        include_names = scope.get("include_room_names") or []
        if include_names and room_name not in include_names:
            return False
        exclude_names = scope.get("exclude_room_names") or []
        if exclude_names and room_name in exclude_names:
            return False
        include_types = scope.get("include_room_types") or []
        if include_types and room_type not in include_types:
            return False
        exclude_types = scope.get("exclude_room_types") or []
        if exclude_types and room_type in exclude_types:
            return False
        floors = scope.get("floors") or []
        if floors and floor not in floors:
            return False
        return True

    def _matches_spec_filters(self, device: dict[str, Any], filters: list[dict[str, Any]]) -> bool:
        for item in filters:
            field = item.get("field")
            op = item.get("op")
            if not isinstance(field, str) or not isinstance(op, str):
                return False
            if op == "has_attribute":
                exists, candidates = resolve_attribute_exists(device, field)
                if candidates or not exists:
                    return False
                continue
            if op == "has_service":
                supports, candidates = resolve_has_service(device, field)
                if candidates or not supports:
                    return False
                continue
            if op == "has_component":
                if not has_component(device, field):
                    return False
                continue
            return False
        return True

    def _matches_status_filters(self, device: dict[str, Any], filters: list[dict[str, Any]]) -> bool:
        for item in filters:
            field = item.get("field")
            op = item.get("op")
            if not isinstance(field, str) or not isinstance(op, str):
                return False
            _, value, candidates = resolve_status_value(device, field)
            if candidates:
                return False
            if value is None and op not in {"=", "!="}:
                return False
            if not _compare(value, op, item.get("value")):
                return False
        return True

    def _matches_same_room(
        self,
        device: dict[str, Any],
        room_devices: dict[str, list[dict[str, Any]]],
        queries: list[dict[str, Any]],
        expect_match: bool,
    ) -> bool:
        room_id = str(device_userdata(device).get("room"))
        peers = room_devices.get(room_id, [])
        for query in queries:
            found = any(
                self._matches_device_scope(peer, query.get("device_scope"))
                and self._matches_spec_filters(peer, query.get("spec_filters") or [])
                and self._matches_status_filters(peer, query.get("status_filters") or [])
                for peer in peers
            )
            if found != expect_match:
                return False
        return True

    def _apply_sort_and_limit(
        self,
        matched: list[dict[str, Any]],
        all_devices: list[dict[str, Any]],
        arguments: dict[str, Any],
        rooms_by_id: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        did_to_device = {item.get("did"): device for device in all_devices for item in [device_summary(device, rooms_by_id)]}
        sort = arguments.get("sort")
        sort_keys_by_did: dict[str, tuple[int, Any]] = {}
        if isinstance(sort, dict):
            field = sort.get("field")
            reverse = sort.get("order") == "desc"
            if isinstance(field, str):
                comparable: list[tuple[dict[str, Any], Any]] = []
                incomparable: list[dict[str, Any]] = []
                for item in matched:
                    did = str(item.get("did"))
                    sort_key = _sort_key(did_to_device.get(item.get("did")), field)
                    sort_keys_by_did[did] = sort_key
                    if sort_key[0] == 0:
                        comparable.append((item, sort_key[1]))
                    else:
                        incomparable.append(item)
                comparable.sort(key=lambda entry: entry[1], reverse=reverse)
                matched = [item for item, _ in comparable] + incomparable
        limit = arguments.get("limit")
        if isinstance(limit, int) and limit > 0 and len(matched) > limit:
            boundary_did = str(matched[limit - 1].get("did"))
            boundary_key = sort_keys_by_did.get(boundary_did)
            if boundary_key is None:
                matched = matched[:limit]
            elif boundary_key[0] != 0:
                matched = matched[:limit]
            else:
                end = limit
                while end < len(matched):
                    candidate_did = str(matched[end].get("did"))
                    if sort_keys_by_did.get(candidate_did) != boundary_key:
                        break
                    end += 1
                matched = matched[:end]
        elif isinstance(limit, int) and limit > 0:
            matched = matched[:limit]
        return matched

    def _aggregate_result(
        self,
        matched: list[dict[str, Any]],
        all_devices: list[dict[str, Any]],
        aggregate: dict[str, Any],
    ) -> dict[str, Any]:
        agg_type = str(aggregate.get("type") or "list")
        if agg_type == "list":
            return {"type": "list", "value": None}
        if agg_type == "count":
            return {"type": "count", "value": len(matched)}
        if agg_type == "exists":
            return {"type": "exists", "value": bool(matched)}
        if agg_type == "distinct_rooms":
            rooms = []
            seen: set[str] = set()
            for item in matched:
                room_id = item.get("room_id")
                if room_id is None or room_id in seen:
                    continue
                seen.add(room_id)
                rooms.append(
                    {
                        "room_id": room_id,
                        "room_name": item.get("room_name"),
                        "room_type": item.get("room_type"),
                        "floor": item.get("floor"),
                    }
                )
            return {"type": "distinct_rooms", "value": rooms}
        if agg_type == "distinct_room_count":
            return {"type": "distinct_room_count", "value": len({item.get("room_id") for item in matched if item.get("room_id") is not None})}
        if agg_type in {"max", "min"}:
            field = aggregate.get("field")
            if not isinstance(field, str) or not field.strip():
                raise ValueError("aggregate.field is required for max/min")
            did_to_device = {str(device_userdata(device).get("did")): device for device in all_devices}
            best_value = None
            best_items: list[dict[str, Any]] = []
            for item in matched:
                device = did_to_device.get(str(item.get("did")))
                if device is None:
                    continue
                _, value, candidates = resolve_status_value(device, field)
                if candidates or value is None:
                    continue
                if best_value is None:
                    best_value = value
                    best_items = [item]
                    continue
                if (agg_type == "max" and value > best_value) or (agg_type == "min" and value < best_value):
                    best_value = value
                    best_items = [item]
                elif value == best_value:
                    best_items.append(item)
            return {"type": agg_type, "field": field, "value": best_value, "devices": best_items}
        raise ValueError(f"unsupported aggregate.type: {agg_type}")


def _compare(left: Any, op: str, right: Any) -> bool:
    if op == "=":
        return left == right
    if op == "!=":
        return left != right
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == "in":
        return isinstance(right, list) and left in right
    if op == "not_in":
        return isinstance(right, list) and left not in right
    return False


def _sort_key(device: dict[str, Any] | None, field: str) -> tuple[int, Any]:
    if not isinstance(device, dict):
        return (1, None)
    _, value, candidates = resolve_status_value(device, field)
    if candidates or value is None:
        return (1, None)
    return (0, value)
