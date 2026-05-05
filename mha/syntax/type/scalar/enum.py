from typing import Optional, Any, Sequence, Dict, Union
import random
from dataclasses import dataclass
from .scalar import Scalar


__all__ = ['Enum']


@dataclass
class Item:
    name: str
    value: Union[str, int]
    description: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict):
        return cls(**d)
    
    def to_dict(self) -> Dict:
        return {
            k: v
            for k, v in {
                'name': self.name,
                'value': self.value,
                'description': self.description
            }.items()
            if v is not None
        }


class Enum(Scalar):
    def __init__(self, items: Sequence[Dict]):
        super().__init__()
        self._items = [Item.from_dict(d) for d in items]
        self._n2v = {item.name: item.value for item in self._items}
        self._v2n = {item.value: item.name for item in self._items}

    @property
    def items(self) -> Sequence[Item]:
        return self._items

    def __str__(self) -> str:
        enum = ", ".join([f"{e.value}:{e.name}" for e in self._items])
        return f"type={self.name}, enum=[{enum}]"
    
    def __call__(self, value: Any) -> Any:
        v = self._n2v.get(value, None)
        if v is not None:
            return v
        if value not in self._v2n:
            raise ValueError(f"{value} is not a valid value for {self.name}")
        return value
    
    def to_dict(self) -> Dict:
        d = super().to_dict()
        d['items'] = [item.to_dict() for item in self._items]
        return d

    def check_type(self, value: Any):
        return value in self._n2v or value in self._v2n
    
    def rand_value(self) -> Any:
        item = self._items[random.randint(0, len(self._items)-1)]
        return item.value
    
    def __meta_eq__(self, lhs: Any, rhs: Any) -> bool:
        if not self.check(rhs):
            return False
        return lhs == self(rhs)
    