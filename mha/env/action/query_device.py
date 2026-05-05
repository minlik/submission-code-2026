from typing import Optional, Dict, Any, Sequence, Union
from mha.engine import HomeEngine
from .action import Action


__all__ = [
    'QueryDevice'
]


class QueryDevice(Action):
    Name = 'query_device'
    Description: str = "query device"
    
    def __init__(
        self, 
        what: Union[str, Sequence[str]],
        did: Optional[Union[str, Sequence[str]]] = None,
        category: Optional[Union[str, Sequence[str]]] = None,
        subcategory: Optional[Union[str, Sequence[str]]] = None,
        spid: Optional[Union[str, Sequence[str]]] = None,
        room: Optional[Union[str, Sequence[str]]] = None,
        tags: Optional[Union[str, Sequence[str]]] = None,
    ):
        self._what = what
        self._did = did
        self._category = category
        self._subcategory = subcategory
        self._spid = spid
        self._room = room
        self._tags = tags
            
    
    def execute(self, engine: HomeEngine):
        return engine.query.query_device(
            what=self._what,
            did=self._did,
            category=self._category,
            subcategory=self._subcategory,
            spid=self._spid,
            room=self._room,
            tags=self._tags,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            'what': self._what,
            'did': self._did,
            'category': self._category,
            'subcategory': self._subcategory,
            'spid': self._spid,
            'room': self._room,
        })
        return d
    


Action.register(QueryDevice)