from typing import Optional
from mha.syntax import IEvent, SyntaxObject, Attribute, Service
from .device import Device


__all__ = ["IEvent"]


class IHomeEvent(IEvent):

    def add_device_listener(self, device: Device):
        def _add_listener(obj: SyntaxObject):
            if type(obj) not in {Attribute, Service}:
                return
            obj.add_event_listener(self._on_device_event_trigger)
        device.traverse(_add_listener)

    def del_device_listener(self, device: Device):
        def _del_listener(obj: SyntaxObject):
            if type(obj) not in {Attribute, Service}:
                return
            obj.del_event_listener(self._on_device_event_trigger)
        device.traverse(_del_listener)

    def _on_device_event_trigger(self, event: str, *args, **kwargs) -> None:
        self.send_event(event, *args, **kwargs)