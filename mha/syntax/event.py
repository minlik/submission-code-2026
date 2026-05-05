from typing import Optional, Union, Dict, Set, Callable, Sequence


__all__ = ['IEvent', 'Sniffer']


class Sniffer(object):
    def __init__(self, ievent: 'IEvent', callback: Callable, event: Optional[Union[str, Sequence[str]]] = None):
        self._ievent = ievent
        self._callback = callback
        self._event = event

    def __enter__(self):
        self._ievent.add_event_listener(self._callback, self._event)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._ievent.del_event_listener(self._callback, self._event)



class IEvent(object):
    
    @property
    def event_listeners(self) -> Dict[str, Set[Callable]]:
        listeners = getattr(self, '__event_listeners__', None)
        if listeners is None:
            listeners = {}
            setattr(self, '__event_listeners__', listeners)
        return listeners
        

    def add_event_listener(self, callback: Callable, event: Optional[Union[str, Sequence[str]]] = None) -> None:
        events = event if isinstance(event, (tuple, list)) else [event]
        for e in events:
            s = self.event_listeners.get(e, None)
            if s is None:
                s = self.event_listeners[e] = set()
            s.add(callback)

    def del_event_listener(self, callback: Callable, event: Optional[Union[str, Sequence[str]]] = None) -> None:
        events = event if isinstance(event, (tuple, list)) else [event]
        for e in events:
            s = self.event_listeners.get(e, None)
            if s is None:
                continue
            try:
                s.remove(callback)
            except KeyError:
                pass

    def send_event(self, event: str, *args, **kwargs) -> None:
        # event
        for callback in self.event_listeners.get(event, []):
            callback(event, *args, **kwargs)

        # all
        for callback in self.event_listeners.get(None, []):
            callback(event, *args, **kwargs)

    def make_sniffer(self, callback: Callable, event: Optional[Union[str, Sequence[str]]] = None) -> Sniffer:
        return Sniffer(self, callback, event)

