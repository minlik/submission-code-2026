from typing import Optional, Any
import random
from .scalar import Scalar


__all__ = ['Bool']



class Bool(Scalar):
    def __call__(self, value: Any) -> Any:
        return bool(value)
    
    def check_type(self, value: Any):
        return isinstance(value, bool)
    
    def rand_value(self) -> Any:
        return random.random() < 0.5
    
    def __meta_bool__(self, lhs: Any) -> Any:
        return bool(lhs)
    
    