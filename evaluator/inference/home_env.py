import json
from typing import Any, Dict, List, Optional

from ..data.mha_adapter import MhaAdapter


class HomeEnvironmentFormatter:
    def __init__(self, adapter: Optional[MhaAdapter] = None) -> None:
        self.adapter = adapter or MhaAdapter()

    def format(self, engine_data: Dict[str, Any], entrance: Optional[str]) -> str:
        payload = self._build_payload(engine_data, entrance)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def _build_payload(self, engine_data: Dict[str, Any], entrance: Optional[str]) -> Dict[str, Any]:
        home = engine_data.get("home") or {}
        type_defs: List[Dict[str, Any]] = []
        type_id_by_signature: Dict[str, str] = {}
        devices: List[Dict[str, Any]] = []

        for device in home.get("devices") or []:
            signature = self._device_type_signature(device)
            type_id = type_id_by_signature.get(signature)
            if type_id is None:
                type_id = f"t{len(type_defs) + 1}"
                type_id_by_signature[signature] = type_id
                type_defs.append(self._build_device_type(device, type_id))
            devices.append(self._build_device_instance(device, type_id))

        payload: Dict[str, Any] = {
            "home": {
                "name": home.get("name"),
                "rooms": list(home.get("rooms") or []),
                "devices": devices,
                "device_types": type_defs,
            }
        }
        if entrance is not None:
            payload["entrance"] = entrance

        outdoor = home.get("outdoor") or {}
        current_time = outdoor.get("time")
        if current_time:
            payload["current_time"] = str(current_time)

        return payload

    def _device_type_signature(self, device: Dict[str, Any]) -> str:
        userdata = device.get("userdata") or {}
        payload = {
            "description": device.get("description"),
            "category": userdata.get("category"),
            "subcategory": userdata.get("subcategory"),
            "attributes": self._static_attributes(device.get("attributes") or []),
            "services": self._static_services(device.get("services") or []),
            "components": self._static_components(device.get("components") or []),  
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _build_device_type(self, device: Dict[str, Any], type_id: str) -> Dict[str, Any]:
        userdata = device.get("userdata") or {}
        result: Dict[str, Any] = {
            "type_id": type_id,
            "description": device.get("description"),
            "category": userdata.get("category"),
            "subcategory": userdata.get("subcategory"),
            "attributes": self._static_attributes(device.get("attributes") or []),
            "services": self._static_services(device.get("services") or []),
        }
        # Task 6: include component specs so component-architecture devices
        # (e.g. fan_light) expose their capabilities to the model
        components = self._static_components(device.get("components") or [])
        if components:
            result["components"] = components
        return result

    def _build_device_instance(self, device: Dict[str, Any], type_id: str) -> Dict[str, Any]:
        userdata = device.get("userdata") or {}
        state: Dict[str, Any] = {}
        # Top-level attributes
        for attr in device.get("attributes") or []:
            name = attr.get("name")
            if name is not None:
                state[str(name)] = attr.get("value")
        # component attributes, keyed as "component_name.attr_name"
        for comp in device.get("components") or []:
            comp_name = comp.get("name")
            if not comp_name:
                continue
            for attr in comp.get("attributes") or []:
                attr_name = attr.get("name")
                if attr_name is not None:
                    state[f"{comp_name}.{attr_name}"] = attr.get("value")
        return {
            "did": userdata.get("did"),
            "name": device.get("name"),
            "room": userdata.get("room"),
            "type_id": type_id,
            "state": state,
        }

    @staticmethod
    def _static_attributes(attributes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{k: v for k, v in attr.items() if k != "value"} for attr in attributes]

    @staticmethod
    def _static_services(services: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{k: v for k, v in service.items() if k != "code"} for service in services]

    @staticmethod
    def _static_components(components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build a spec-only view of components (no runtime values)."""
        result = []
        for comp in components:
            entry: Dict[str, Any] = {"name": comp.get("name")}
            attrs = [{k: v for k, v in a.items() if k != "value"}
                     for a in comp.get("attributes") or []]
            svcs = [{k: v for k, v in s.items() if k != "code"}
                    for s in comp.get("services") or []]
            if attrs:
                entry["attributes"] = attrs
            if svcs:
                entry["services"] = svcs
            result.append(entry)
        return result
