from typing import Optional, Dict, Any, Sequence, Union
from mha.engine import HomeEngine
from .action import Action


__all__ = [
    'QueryRoom'
]


class QueryRoom(Action):
    Name = 'query_room'
    Description: str = "query room"
    
    def __init__(self):
        pass
            
    
    def execute(self, engine: HomeEngine) -> str:
        return engine.query.query_room()
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({})
        return d
    


Action.register(QueryRoom)