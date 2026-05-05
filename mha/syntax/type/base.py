from typing import Optional, Type, Sequence, Tuple, Any, Dict
from collections.abc import Iterator
from abc import ABC, abstractmethod


__all__ = ['Base']


class Base(ABC):

    @property
    def name(self) -> str:
        return self.__class__.__name__.lower()

    @property
    @abstractmethod
    def nested(self) -> bool:
        pass
    
    @property
    def scalar(self) -> bool:
        return not self.nested
    
    @classmethod
    def from_dict(cls, value: Dict) -> "Base":
        return cls(**value)
    
    @property
    def range(self) -> Optional[Tuple]:
        raise NotImplementedError(f"{self.name} does not support range")
        
    @property
    def precision(self) -> Optional[float]:
        raise NotImplementedError(f"{self.name} does not support precision")
    
    @property
    def options(self) -> Optional[Sequence[Any]]:
        raise NotImplementedError(f"{self.name} does not support options")

    @property
    def has_range(self) -> bool:
        try:
            return self.range is not None
        except:
            return False
        
    @property
    def has_precision(self) -> bool:
        try:
            return self.precision is not None
        except:
            return False
        
    @property
    def has_options(self) -> bool:
        try:
            return self.options is not None
        except:
            return False
        
    def __str__(self) -> str:
        return f"type={self.name}"
    
    @abstractmethod
    def __call__(self, value: Any) -> Any:
        pass
    
    def to_dict(self) -> Dict:
        return {'type': self.name}
    
    @abstractmethod
    def check_type(self, value: Any) -> bool:
        pass

    @abstractmethod
    def check(self, value: Any, raise_error: bool = False) -> bool:
        pass

    @abstractmethod
    def rand_value(self) -> Any:
        pass

    def __meta_eq__(self, lhs: Any, rhs: Any) -> bool:
        raise NotImplementedError(f"type '{self.name}' does not support eq")
    
    def __meta_ne__(self, lhs: Any, rhs: Any) -> bool:
        raise NotImplementedError(f"type '{self.name}' does not support ne")
    
    def __meta_lt__(self, lhs: Any, rhs: Any) -> bool:
        raise NotImplementedError(f"type '{self.name}' does not support lt")
    
    def __meta_gt__(self, lhs: Any, rhs: Any) -> bool:
        raise NotImplementedError(f"type '{self.name}' does not support gt")
    
    def __meta_le__(self, lhs: Any, rhs: Any) -> bool:
        raise NotImplementedError(f"type '{self.name}' does not support le")
    
    def __meta_ge__(self, lhs: Any, rhs: Any) -> bool:
        raise NotImplementedError(f"type '{self.name}' does not support ge")
    
    def __meta_add__(self, lhs: Any, rhs: Any) -> Any:
        raise NotImplementedError(f"type '{self.name}' does not support add")
    
    def __meta_sub__(self, lhs: Any, rhs: Any) -> Any:
        raise NotImplementedError(f"type '{self.name}' does not support sub")
    
    def __meta_mul__(self, lhs: Any, rhs: Any) -> Any:
        raise NotImplementedError(f"type '{self.name}' does not support mul")
    
    def __meta_true_div__(self, lhs: Any, rhs: Any) -> Any:
        raise NotImplementedError(f"type '{self.name}' does not support true_div")
    
    def __meta_floor_div__(self, lhs: Any, rhs: Any) -> Any:
        raise NotImplementedError(f"type '{self.name}' does not support floor_div")
    
    def __meta_mod__(self, lhs: Any, rhs: Any) -> Any:
        raise NotImplementedError(f"type '{self.name}' does not support mod")
    
    def __meta_pow__(self, lhs: Any, rhs: Any) -> Any:
        raise NotImplementedError(f"type '{self.name}' does not support pow")
    
    def __meta_bool__(self, lhs: Any) -> Any:
        raise NotImplementedError(f"type '{self.name}' does not support bool")
    
    def __meta_contains__(self, lhs: Any, rhs: Any) -> bool:
        raise NotImplementedError(f"type '{self.name}' does not support contains")
    
    def __meta_len__(self, lhs: Any) -> int:
        raise NotImplementedError(f"type '{self.name}' does not support len")
    
    def __meta_iter__(self, lhs: Any) -> Iterator:
        raise NotImplementedError(f"type '{self.name}' does not support iter")
    
    def __meta_getitem__(self, lhs: Any, index: Any) -> Any:
        raise NotImplementedError(f"type '{self.name}' does not support getitem")
    
    def __meta_hash__(self, lhs: Any) -> int:
        raise NotImplementedError(f"type '{self.name}' does not support hash")

