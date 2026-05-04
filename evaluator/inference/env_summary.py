import json
from typing import Any, Dict, List


class EnvironmentSummarizer:
    def summarize(self, engine: Dict[str, Any]) -> str:
        home = engine.get("home") or {}
        rooms = home.get("rooms") or []
        devices = home.get("devices") or []
        outdoor = home.get("outdoor") or {}

        room_summary = [
            {
                "id": room.get("id"),
                "name": room.get("name"),
                "type": room.get("type"),
                "floor": room.get("floor"),
            }
            for room in rooms
        ]
        device_summary = [
            {
                "device_id": (device.get("userdata") or {}).get("did"),
                "type": (device.get("userdata") or {}).get("subcategory")
                or (device.get("userdata") or {}).get("category"),
                "room": (device.get("userdata") or {}).get("room"),
            }
            for device in devices
        ]
        summary = {
            "rooms": room_summary,
            "devices": device_summary,
            "outdoor": {
                "time": outdoor.get("time"),
                "weather": outdoor.get("weather"),
                "temperature": outdoor.get("temperature"),
            },
        }
        return json.dumps(summary, ensure_ascii=False)
