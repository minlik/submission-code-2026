from typing import Optional, Sequence, Tuple, Any
import string
import random
import numpy as np
from collections.abc import Iterator
from .scalar import Scalar


__all__ = ['Str', 'Hex']


class Str(Scalar):
    def __call__(self, value: Any) -> Any:
        return str(value)
    
    def set_options(self, options: Tuple[str, str]):
        for opt in options:
            if self.check_type(opt):
                continue
            raise TypeError(f"invalid option: {options}, expected: Tuple[str, str]")
        self._options = options

    def check_type(self, value: Any) -> bool:
        return isinstance(value, str)
    
    def check_options(self, value: Any):
        if self._options is None:
            return True
        return value in self._options
    
    def rand_value(self) -> Any:
        if self._options is not None:
            return random.sample(self._options, 1)[0]
        else:
            characters = string.ascii_letters + string.digits
            return ''.join(random.choice(characters) for _ in range(16))
    
    def __meta_contains__(self, lhs: Any, rhs: Any) -> bool:
        return rhs in lhs
    
    def __meta_len__(self, lhs: Any) -> int:
        return len(lhs)
    
    def __meta_iter__(self, lhs) -> Iterator:
        return iter(lhs)
    
    

class Hex(Str):
    def __call__(self, value: Any) -> Any:
        ival = int(value, 16) if isinstance(value, str) else value
        return hex(ival)
    
    def check_type(self, value: Any) -> bool:
        if isinstance(value, str):
            try:
                ival = int(value, 16)
            except:
                return False
        elif isinstance(value, int):
            ival = value
        else:
            return False
        try:
            hex(ival)
        except:
            return False
        return True
    
    def rand_value(self) -> Any:
        info = np.iinfo(np.int32)
        v = np.random.randint(info.min, info.max)
        return hex(v)
