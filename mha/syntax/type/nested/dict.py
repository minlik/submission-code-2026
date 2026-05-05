from typing import Optional, Sequence, Any, Dict
from collections.abc import ItemsView, ValuesView, KeysView, Iterator
from .nested import Nested


__all__ = ['Dict']


class Dict(Nested):
    def __init__(self, items: Dict):
        from mha.syntax.type.typing import Typing

        assert isinstance(items, dict), f"invalid items '{items}' for type {self.name}, expected dict"
        super().__init__()
        self._items = {k: Typing.make(**v) for k, v in items.items()}

    def __iter__(self) -> Iterator:
        return iter(self._items)
    
    def __len__(self) -> int:
        return len(self._items)
    
    def __str__(self) -> str:
        items = ", ".join(f"{k}=[{str(v)}]" for k, v in self._items.items())
        return f"type={self.name}, items=[{items}]"
    
    def __call__(self, value: Any) -> Any:
        return {k: self._items[k](v) for k, v in value.items()}

    def keys(self) -> KeysView:
        return self._items.keys()

    def values(self) -> ValuesView:
        return self._items.values()
    
    def items(self) -> ItemsView:
        return self._items.items()
    
    def to_dict(self):
        d = super().to_dict()
        d['items'] = {k: v.to_dict() for k, v in self._items.items()}
        return d
    
    def check_type(self, value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        for k, tp in self._items.items():
            v = value.get(k, None)
            if v is None or not tp.check_type(v):
                return False
        return True
    
    def check(self, value: Any, raise_error: bool = False) -> bool:
        if not self.check_type(value):
            if raise_error:
                raise ValueError(f"invalid type '{type(value)}' for type '{self.name}', expected tuple or list")
            return False
        for k, tp in self._items.items():
            v = value.get(k, None)
            if v is None or not tp.check(v):
                return False
        return True
    
    def rand_value(self) -> Any:
        return {k: tp.rand_value() for k, tp in self._items.items()}
    
    def __meta_eq__(self, lhs: Any, rhs: Any) -> bool:
        if not self.check(rhs):
            return False
        for k, tp in self._items.items():
            if not tp.__meta_eq__(lhs[k], rhs[k]):
                return False
        return True

    def __meta_ne__(self, lhs: Any, rhs: Any) -> bool:
        return not self.__meta_eq__(lhs, rhs)
    
    def __meta_mul__(self, lhs: Any, rhs: Any) -> bool:
        return lhs * rhs
    
    def __meta_contains__(self, lhs: Any, rhs: Any) -> bool:
        return rhs in lhs
    
    def __meta_len__(self, lhs: Any) -> int:
        return len(lhs)
    
    def __meta_iter__(self, lhs) -> Iterator:
        return iter(lhs)
    
    def __meta_getitem__(self, lhs: Any, index: Any) -> Any:
        return lhs[index]

    