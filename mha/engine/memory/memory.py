from typing import Optional, Any, Dict, List, Iterator
from collections import OrderedDict
from dataclasses import dataclass
import secrets
from mha.engine.core import Plugin


__all__ = ["Memory", "MemClip"]



@dataclass
class MemClip(object):
    id: str
    content: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'content': self.content,
        }
    
    @classmethod
    def from_dict(cls, data) -> "MemClip":
        return cls(**data)


class Memory(Plugin):
    Name: str = "memory"

    def __init__(
        self, 
        cache: List[MemClip] = None, 
        max_size: Optional[int] = 64
    ):
        self._max_size = max_size
        self._cache = OrderedDict[str, MemClip]()
        if cache is not None:
            for clip in cache:
                self._cache[clip.id] = clip

    @property
    def max_size(self) -> Optional[int]:
        return self._max_size

    @max_size.setter
    def max_size(self, value: Optional[int]):
        self._max_size = value
        if self._max_size is None:
            return
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def __getitem__(self, id: str) -> MemClip:
        clip = self._cache.get(id, None)
        if clip is None:
            raise KeyError(f"memory clip '{id}' not found")
        return clip

    def __iter__(self) -> Iterator[MemClip]:
        return iter(self._cache.values())

    def __len__(self) -> int:
        return len(self._cache)

    def full(self) -> bool:
        return self._max_size is not None and len(self._cache) >= self._max_size
    
    def append(self, content: str, id: Optional[str] = None) -> str:
        if id is not None and id in self._cache:
            del self._cache[id]
        id = secrets.token_urlsafe(6)[:8] if id is None else id
        self._cache[id] = MemClip(id, content)
        if self._max_size is not None and len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def remove(self, id: str) -> None:
        if id in self._cache:
            del self._cache[id]

    def clear(self) -> None:
        self._cache.clear()

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            'max_size': self._max_size,
            'cache': [clip.to_dict() for clip in self._cache.values()],
        })
        return d

    @classmethod
    def from_dict(cls, data):
        return cls(
            max_size=data.get('max_size', None),
            cache=[MemClip.from_dict(d) for d in data.get('cache', [])]
        )

    

Plugin.register(Memory)
