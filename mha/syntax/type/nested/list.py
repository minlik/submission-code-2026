from typing import Optional, Sequence, Dict, Union, Tuple, Any
import random
from collections.abc import Iterator
from .nested import Nested


__all__ = ['List']


class List(Nested):
    def __init__(self, items: Dict, size: Union[int, Sequence[int]]):
        from mha.syntax.type.typing import Typing


        # check size
        assert isinstance(size, (tuple, list, int)), f"invalid size '{size}' for type '{self.name}', expected tuple, list or int"
        if isinstance(size, (tuple, list)):
            assert len(size) == 2, f"invalid size '{size}' for type '{self.name}', expected length 2"

        super().__init__()
        self._items = Typing.make(**items)
        self._size = (0, size) if isinstance(size, int) else tuple(size)
        
    @property
    def size(self) -> Tuple[int, int]:
        return self._size
    
    def __str__(self) -> str:
        return f"type={self.name}, size={self._size}, items=[{str(self._items)}]"
    
    def __call__(self, value: Any) -> Any:
        return list(self._items(v) for v in value)

    def to_dict(self):
        d = super().to_dict()
        d['items'] = self._items.to_dict()
        d['size'] = self._size[0] if self._size[0] == 0 else list(self._size)
        return d
    
    def check_type(self, value: Any):
        return isinstance(value, (tuple, list)) and \
                self._size[0] <= len(value) <= self._size[1]
    
    def check(self, value: Any, raise_error: bool = False) -> bool:
        if not self.check_type(value):
            if raise_error:
                raise ValueError(f"invalid type '{type(value)}' for type '{self.name}', expected tuple or list")
            return False
        for val in value:
            if not self._items.check(val, raise_error):
                return False
        return True
    
    def rand_value(self) -> Any:
        size = random.randint(self._size[0], self._size[1])
        return [self._items.rand_value() for _ in range(size)]
    
    def __meta_eq__(self, lhs: Any, rhs: Any) -> bool:
        if not self.check(rhs):
            return False
        tp = self._items
        for (l, r) in zip(lhs, rhs):
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

    