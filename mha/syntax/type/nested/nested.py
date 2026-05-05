from typing import Optional, Any
from mha.syntax.type.base import Base


__all__ = ['Nested']



class Nested(Base):
    def __init__(self):
        assert self.nested, f"type '{self.name}' is not nested type"

    @property
    def nested(self) -> bool:
        return True
    
    def __meta_bool__(self, lhs: Any) -> bool:
        return bool(lhs)