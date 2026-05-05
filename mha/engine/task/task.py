from typing import Optional, Dict, Any
from mha.engine.core import ISerializer


__all__ = ["Task"]



class Task(ISerializer):
    def __init__(self, id: str, condition: str, description: Optional[str] = None, finished: bool = False):
        self._id = id
        self._condition = condition
        self._description = description
        self._finished = finished

    @property
    def id(self) -> str:
        return self._id

    @property
    def condition(self) -> str:
        return self._condition
    
    @property
    def description(self) -> Optional[str]:
        return self._description
    
    @property
    def finished(self) -> bool:
        return self._finished
    
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self._id,
            'condition': self.condition,
            'description': self.description,
            'finished': self.finished
        }