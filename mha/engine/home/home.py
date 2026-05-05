from typing import Optional, List, Dict, Any
from mha.engine.core import Plugin
from .device import Device
from .env import Outdoor
from .room import Room
from .event import IHomeEvent


__all__ = ['Home']


class Home(Plugin, IHomeEvent):
    Name = 'home'

    def __init__(
        self,
        rooms: List[Room],
        devices: List[Device],
        outdoor: Optional[Outdoor] = None,
    ):
        self._rooms = rooms
        self._devices = []
        self._device_map = {}
        self._outdoor = outdoor
        self._room_map = {r.id: r for r in rooms}
        
        # connect rooms
        for room in rooms:
            if room._parent_id is None:
                continue
            room.connect_parent(self._room_map[room._parent_id])

        # add device
        for device in devices:
            self.add_device(device)

    @property
    def outdoor(self) -> Optional[Outdoor]:
        return self._outdoor
    
    @property
    def rooms(self) -> List[Room]:
        return self._rooms
    
    @property
    def devices(self) -> List[Device]:
        return self._devices
    
    def get_room(self, id: str) -> Room:
        room = self._room_map.get(id, None)
        assert room is not None, f"no such room '{id}'"
        return room
    
    def find_room(self, id: str) -> Optional[Room]:
        return self._room_map.get(id)

    def get_device(self, did: str) -> Device:
        device = self._device_map.get(did, None)
        assert device is not None, f"no such device '{did}'"
        return device
    
    def find_device(self, did: str) -> Optional[Device]:
        return self._device_map.get(did)
    
    def add_device(self, device: Device):
        # add device
        if device.did in self._device_map:
            raise ValueError(f"Device '{device.did}' already exists")
        self._devices.append(device)
        self._device_map[device.did] = device

        # add to room
        self._room_map[device.room].add_device(device)

        # add listener
        self.add_device_listener(device)

    def del_device(self, did: str) -> None:
        # remove device
        device = self.get_device(did)
        if device is None:
            return
        self._devices.remove(device)
        del self._device_map[did]

        # remove from room
        self._room_map[device.room].del_device(device.did)

        # remove listener
        self.del_device_listener(device)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Home":
        outdoor = Outdoor.from_dict(data['outdoor']) if 'outdoor' in data else None
        rooms = [Room.from_dict(r) for r in data['rooms']]
        devices = [Device.from_dict(d) for d in data['devices']]
        return Home(rooms, devices, outdoor)
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update(
            rooms = [r.to_dict() for r in self.rooms],
            devices = [d.to_dict() for d in self.devices],
        )
        if self.outdoor is not None:
            d['outdoor'] = self.outdoor.to_dict()
        return d
    
    
Plugin.register(Home)
