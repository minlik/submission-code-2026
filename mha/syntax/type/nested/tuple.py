from typing import Optional, Sequence, Dict, Union, Any
from collections.abc import Iterator
from .nested import Nested, Base


__all__ = ['Tuple']


class Tuple(Nested):
    def __init__(self, items: Union[Dict, Sequence[Dict]], size: int = None):
        from mha.syntax.type.typing import Typing

        super().__init__()

        if isinstance(items, (tuple, list)):
            assert size is None, f"fixed-size items do not support the size parameter, type: {self.name}"
            self._homogenous = False
            self._items = [Typing.make(**it) for it in items]
        elif isinstance(items, dict):
            assert isinstance(size, int), f"invalid size '{size}' for type '{self.name}', expected int"
            self._homogenous = True
            self._items = [Typing.make(**items)] * size
        else:
            raise TypeError(f"invalid item '{items}' for type '{self.name}', expected tuple, list or dict")

    @property
    def homogenous(self) -> bool:
        return self._homogenous

    def __getitem__(self, index: int) -> Base:
        return self._items[index]

    def __len__(self) -> int:
        return len(self._items)
    
    def __iter__(self) -> Iterator[Base]:
        return iter(self._items)
    
    def __str__(self) -> str:
        if self._homogenous:
            items = str(self._items[0]) if len(self._items) > 0 else ""
            return f"type={self.name}, items=[{items}]*{len(self._items)}"
        else:
            items = ", ".join(f"[{str(it)}]" for it in self._items)
            return f"type={self.name}, items=[{items}]"

    def __call__(self, value: Any) -> Any:
        return tuple(tp(val) for (tp, val) in zip(self._items, value))

    def to_dict(self):
        d = super().to_dict()
        if self.homogenous:
            if len(self._items) > 0:
                d['items'] = self._items[0].to_dict()
            d['size'] = len(self._items)
        else:
            d['items'] = [it.to_dict() for it in self._items]
        return d
    
    def check_type(self, value: Any) -> bool:
        if not isinstance(value, (tuple, list)):
            return False
        if len(value) != len(self._items):
            return False
        return True
    
    def check(self, value: Any, raise_error: bool = False) -> bool:
        if not self.check_type(value):
            if raise_error:
                raise ValueError(f"invalid type '{type(value)}' for type '{self.name}', expected tuple or list")
            return False
        for (tp, val) in zip(self._items, value):
            if not tp.check(val, raise_error):
                return False
        return True
    
    def rand_value(self) -> Any:
        return tuple(tp.rand_value() for tp in self._items)

    def __meta_eq__(self, lhs: Any, rhs: Any) -> bool:
        if not self.check(rhs):
            return False
        for (tp, l, r) in zip(self._items, lhs, rhs):
            if not tp.__meta_eq__(l, r):
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
    
    def __meta_hash__(self, lhs) -> int:
        return hash(lhs)
