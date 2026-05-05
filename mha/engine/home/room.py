from typing import Optional, Dict, Any, List
from mha.engine.core import ISerializer
from .env import Indoor
from .device import Device


__all__ = ['Room']


class Room(ISerializer):
    def __init__(
        self, 
        id: str, 
        type: str, 
        name: str, 
        floor: int,
        parent: Optional[str] = None,
        env: Optional[Indoor] = None,
        floor_id: str = "",
        floor_name: str = "",
    ):
        self._id = id
        self._type = type
        self._floor = floor
        self._name = name
        self._floor_id = floor_id
        self._floor_name = floor_name
        self._parent_id = parent
        self._parent = None
        self._env = env
        self._devices = []
        self._device_map = {d.did: d for d in self._devices}

    @property
    def id(self) -> str:
        return self._id
    
    @property
    def type(self) -> str:
        return self._type

    @property
    def name(self) -> str:
        return self._name
    
    @property
    def floor(self) -> int:
        return self._floor

    @property
    def floor_id(self) -> str:
        return self._floor_id

    @property
    def floor_name(self) -> str:
        return self._floor_name
    
    @property
    def parent(self) -> Optional["Room"]:
        return self._parent
    
    @property
    def env(self) -> Optional[Indoor]:
        return self._env
    
    @property
    def devices(self) -> List[Device]:
        return self._devices
    
    def connect_parent(self, room: "Room") -> None:
        assert self._parent is None, f"room '{self._id}' already has a parent '{self._parent.id}'"
        assert room.id == self._parent_id, f"room '{self._id}' parent '{self._parent_id}' does not match '{room.id}'"
        self._parent = room

    def add_device(self, device: Device) -> None:
        self._devices.append(device)
        self._device_map[device.did] = device

    def del_device(self, did: str) -> None:
        device = self._device_map[did]
        del self._device_map[did]
        self._devices.remove(device)

    def get_device(self, did: str) -> Device:
        device = self._device_map.get(did, None)
        assert device is not None, f"no such device '{did}'"
        return device
    
    def find_device(self, did: str) -> Optional[Device]:
        return self._device_map.get(did)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Room":
        _make = lambda env=None, **kwds: Room(env=(env if env is None else Indoor.from_dict(env)), **kwds)
        return _make(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        d = {
            'id': self._id,
            'type': self._type,
            'name': self._name,
            'floor': self._floor
        }
        if self._floor_id:
            d['floor_id'] = self._floor_id
        if self._floor_name:
            d['floor_name'] = self._floor_name
        if self._parent is not None:
            d['parent'] = self._parent.id
        if self._env is not None:
            d['env'] = self._env.to_dict()
        return d
