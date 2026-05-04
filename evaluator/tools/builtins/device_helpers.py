from __future__ import annotations

from collections import defaultdict
from typing import Any


def room_lookup(engine_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rooms = ((engine_data.get("home") or {}).get("rooms") or [])
    return {str(room.get("id")): dict(room) for room in rooms if room.get("id") is not None}


def devices(engine_data: dict[str, Any]) -> list[dict[str, Any]]:
    return list(((engine_data.get("home") or {}).get("devices") or []))


def device_userdata(device: dict[str, Any]) -> dict[str, Any]:
    return dict(device.get("userdata") or {})


def device_did(device: dict[str, Any]) -> str | None:
    did = device_userdata(device).get("did")
    return None if did is None else str(did)


def device_spid(device: dict[str, Any]) -> str | None:
    spid = device_userdata(device).get("spid")
    return None if spid is None else str(spid)


def device_room_id(device: dict[str, Any]) -> str | None:
    room_id = device_userdata(device).get("room")
    return None if room_id is None else str(room_id)


def device_summary(device: dict[str, Any], rooms_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    userdata = device_userdata(device)
    room_id = device_room_id(device)
    room = rooms_by_id.get(str(room_id)) if room_id is not None else None
    return {
        "did": device_did(device),
        "spid": device_spid(device),
        "name": device.get("name"),
        "category": userdata.get("category"),
        "subcategory": userdata.get("subcategory"),
        "room_id": room_id,
        "room_name": None if room is None else room.get("name"),
        "room_type": None if room is None else room.get("type"),
        "floor": None if room is None else room.get("floor"),
    }


def group_summaries_by_spid(
    device_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in device_items:
        spid = item.get("spid")
        if spid is None:
            continue
        if spid not in grouped:
            grouped[spid] = {
                "spid": spid,
                "category": item.get("category"),
                "subcategory": item.get("subcategory"),
                "dids": [],
            }
            order.append(spid)
        grouped[spid]["dids"].append(item.get("did"))
    return [grouped[spid] for spid in order]


def group_summaries_by_room(
    device_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in device_items:
        room_id = item.get("room_id")
        if room_id is None:
            continue
        if room_id not in grouped:
            grouped[room_id] = {
                "room_id": room_id,
                "room_name": item.get("room_name"),
                "dids": [],
            }
            order.append(room_id)
        grouped[room_id]["dids"].append(item.get("did"))
    return [grouped[room_id] for room_id in order]


def top_level_status(device: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for attr in device.get("attributes") or []:
        name = attr.get("name")
        if name is not None:
            result[str(name)] = attr.get("value")
    return result


def component_status(device: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for component in device.get("components") or []:
        component_name = component.get("name")
        if component_name is None:
            continue
        for attr in component.get("attributes") or []:
            attr_name = attr.get("name")
            if attr_name is not None:
                result[f"{component_name}.{attr_name}"] = attr.get("value")
    return result


def device_status_map(device: dict[str, Any]) -> dict[str, Any]:
    result = top_level_status(device)
    result.update(component_status(device))
    return result


def device_attribute_paths(device: dict[str, Any]) -> set[str]:
    return set(device_status_map(device).keys())


def device_service_locators(device: dict[str, Any]) -> list[str]:
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


def resolve_field_path(candidates: set[str] | list[str], field: str) -> tuple[str | None, list[str]]:
    field_name = str(field)
    candidate_set = [str(item) for item in candidates]
    if field_name in candidate_set:
        return field_name, []
    suffix_matches = [item for item in candidate_set if item.endswith(f".{field_name}")]
    if len(suffix_matches) == 1:
        return suffix_matches[0], []
    if len(suffix_matches) > 1:
        return None, suffix_matches
    return None, []


def resolve_status_value(device: dict[str, Any], field: str) -> tuple[str | None, Any, list[str]]:
    status = device_status_map(device)
    resolved, candidates = resolve_field_path(set(status.keys()), field)
    if resolved is None:
        return None, None, candidates
    return resolved, status.get(resolved), []


def resolve_attribute_exists(device: dict[str, Any], field: str) -> tuple[bool, list[str]]:
    resolved, candidates = resolve_field_path(device_attribute_paths(device), field)
    return resolved is not None, candidates


def resolve_has_service(device: dict[str, Any], field: str) -> tuple[bool, list[str]]:
    resolved, candidates = resolve_field_path(device_service_locators(device), field)
    return resolved is not None, candidates


def has_component(device: dict[str, Any], component_name: str) -> bool:
    return any(str(component.get("name")) == str(component_name) for component in device.get("components") or [])


def strip_attribute_specs(attributes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in attr.items() if k != "value"} for attr in attributes]


def strip_service_specs(services: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in service.items() if k != "code"} for service in services]


def strip_component_specs(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for component in components:
        item: dict[str, Any] = {"name": component.get("name")}
        attrs = strip_attribute_specs(list(component.get("attributes") or []))
        services = strip_service_specs(list(component.get("services") or []))
        if attrs:
            item["attributes"] = attrs
        if services:
            item["services"] = services
        result.append(item)
    return result


def devices_grouped_by_room(engine_data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for device in devices(engine_data):
        room_id = device_room_id(device)
        if room_id is not None:
            grouped[room_id].append(device)
    return dict(grouped)
