from typing import Any, Dict, List, Optional


class MhaAdapter:
    def rooms(self, engine_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        home = engine_data.get("home") or {}
        return list(home.get("rooms") or [])

    def devices(self, engine_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        home = engine_data.get("home") or {}
        return list(home.get("devices") or [])

    def build_env(self, engine_data: Dict[str, Any]) -> Any:
        try:
            from mha.env import HomeEnv
        except ImportError as exc:
            raise RuntimeError("mha.env.HomeEnv is required") from exc
        engine_dict = dict(engine_data)
        home = dict(engine_dict.get("home") or {})
        if not home:
            raise ValueError("engine.home is required")
        home.setdefault("name", "home")
        engine_dict["home"] = home
        return HomeEnv.from_dict({"engine": engine_dict})

    def find_device(self, engine_data: Dict[str, Any], did: str) -> Optional[Dict[str, Any]]:
        for device in self.devices(engine_data):
            userdata = device.get("userdata") or {}
            if str(userdata.get("did")) == str(did):
                return device
        return None

    def room_name(self, engine_data: Dict[str, Any], room_id: Optional[str]) -> Optional[str]:
        if room_id is None:
            return None
        for room in self.rooms(engine_data):
            if str(room.get("id")) == str(room_id):
                return room.get("name")
        return None

    def room_id(self, engine_data: Dict[str, Any], room_ref: Optional[str]) -> Optional[str]:
        if room_ref is None:
            return None
        ref = str(room_ref)
        for room in self.rooms(engine_data):
            room_id = room.get("id")
            if room_id is not None and str(room_id) == ref:
                return str(room_id)
            name = room.get("name")
            if name is not None and str(name) == ref:
                return str(room.get("id"))
        return None
