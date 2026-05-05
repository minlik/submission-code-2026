from typing import Optional, Sequence
from mha.syntax import Entity


__all__ = ['Device']


class Device(Entity):

    STATIC_USERDATA_KEYS: Sequence = ['spid', 'category', 'subcategory', 'tags']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # check
        spid = self._userdata.get('spid', None)
        category = self._userdata.get('category', None)
        subcategory = self._userdata.get('subcategory', None)
        tags =  self._userdata.get('tags', None)

        did = self._userdata.get('did', None)
        room = self._userdata.get('room', None)
        
        assert isinstance(spid, str), f"spid must be a string, got {spid}"
        assert isinstance(category, str), f"category must be a string, got {category}"
        assert isinstance(subcategory, str), f"subcategory must be a string, got {subcategory}"
        assert isinstance(tags, list), f"subcategory must be a list, got {tags}"

        assert isinstance(did, str), f"id must be a string, got {did}"
        assert isinstance(room, str), f"room must be a string, got {room}"
        
        
    @property
    def did(self) -> str:
        return self._userdata['did']
    
    @property
    def spid(self) -> str:
        return self._userdata['spid']
    
    @property
    def category(self) -> str:
        return self._userdata['category']
    
    @property
    def subcategory(self) -> str:
        return self._userdata['subcategory']
    
    @property
    def tags(self) -> Sequence[str]:
        return self._userdata['tags']

    @property
    def room(self) -> str:
        return self._userdata['room']
    
    @staticmethod
    def make(entity: Entity, **ud) -> 'Device':
        data = entity.to_dict()
        data['userdata'].update(ud)
        return Device.from_dict(data)