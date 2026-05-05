from typing import Optional, Any, Sequence, Tuple, Dict
from mha.syntax.object import SyntaxObject
from mha.syntax.attribute_read_resolver import current_attribute_read_resolver
from .typing import Typing
from .base import Base


__all__ = ["TypeObject"]



class NotExistsType(object): pass
NotExists = NotExistsType()

class TypeObject(SyntaxObject):

    _type: Base
    _value: Any

    def __init__(
        self, 
        name: str, 
        type: str, 
        description = None, 
        value: Any = NotExists,
        **tp_kwds):
        super().__init__(name, description)

        # type
        self._type = Typing.make(type, **tp_kwds)
        
        # value
        if not isinstance(value, NotExistsType):
            self.force_assign(value)

    @property
    def type(self) -> Base:
        return self._type
    
    @property
    def range(self) -> Optional[Tuple]:
        return self._type.range
        
    @property
    def precision(self) -> Optional[float]:
        return self._type.precision
    
    @property
    def options(self) -> Optional[Sequence[Any]]:
        return self._type.options
    
    @property
    def value(self) -> Optional[Any]:
        resolver = current_attribute_read_resolver()
        if resolver is not None:
            result = resolver.on_read(self)
            if result.handled:
                self.send_event('get_attribute', attribute=self, value=result.value)
                return result.value
        v = self._value if hasattr(self, '_value') else None
        self.send_event('get_attribute', attribute=self, value=v)
        return v

    @value.setter
    def value(self, value: Any):
        self.force_assign(value)
        
    @property
    def assigned(self) -> bool:
        return hasattr(self, '_value')
    
    def force_assign(self, value: Any) -> bool:
        prev_value = self._value if hasattr(self, '_value') else None
        error = None
        try:
            if value is None:
                self._value = None
            else:
                value = value.value if isinstance(value, TypeObject) else value
                self.check_value(value, raise_error=True)
                self._value = self.type(value)
        except Exception as e:
            error = e
            raise e
        finally:
            self.send_event("set_attribute", attribute=self, prev_value=prev_value, post_value=(self._value if hasattr(self, '_value') else None), error=error)
        return error is None
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update(self._type.to_dict())
        if self.assigned:
            d['value'] = self.value
        return d
    
    def check_value(self, value: Any, raise_error=True):
        try:
            self.type.check(value, raise_error=raise_error)
        except Exception as e:
            raise ValueError(f"{e}, attribute: {self.name}, value: {value}")

    def rand_value(self) -> Any:
        try:
            return self.type.rand_value()
        except Exception as e:
            raise ValueError(f"{e}, attribute: {self.name}")
    
    def __eq__(self, other: Any) -> bool:
        return self._type.__meta_eq__(self.value, other.value if isinstance(other, TypeObject) else other)
    
    def __ne__(self, other: Any) -> bool:
        return self._type.__meta_ne__(self.value, other.value if isinstance(other, TypeObject) else other) 
    
    def __lt__(self, other: Any) -> bool:
        return self._type.__meta_lt__(self.value, other.value if isinstance(other, TypeObject) else other)
    
    def __le__(self, other: Any) -> bool:
        return self._type.__meta_le__(self.value, other.value if isinstance(other, TypeObject) else other)
    
    def __gt__(self, other: Any) -> bool:
        return self._type.__meta_gt__(self.value, other.value if isinstance(other, TypeObject) else other)
    
    def __ge__(self, other: Any) -> bool:
        return self._type.__meta_ge__(self.value, other.value if isinstance(other, TypeObject) else other)
    
    def __add__(self, other: Any) -> Any:
        return self._type.__meta_add__(self.value, other.value if isinstance(other, TypeObject) else other)
    
    def __sub__(self, other: Any) -> Any:
        return self._type.__meta_sub__(self.value, other.value if isinstance(other, TypeObject) else other)
    
    def __mul__(self, other: Any) -> Any:
        return self._type.__meta_mul__(self.value, other.value if isinstance(other, TypeObject) else other)
    
    def __truediv__(self, other: Any) -> Any:
        return self._type.__meta_true_div__(self.value, other.value if isinstance(other, TypeObject) else other)
    
    def __floordiv__(self, other: Any) -> Any:
        return self._type.__meta_floor_div__(self.value, other.value if isinstance(other, TypeObject) else other)
    
    def __mod__(self, other: Any) -> Any:
        return self._type.__meta_mod__(self.value, other.value if isinstance(other, TypeObject) else other)
    
    def __pow__(self, other: Any) -> Any:
        return self._type.__meta_pow__(self.value, other.value if isinstance(other, TypeObject) else other)
    
    def __bool__(self) -> bool:
        return self._type.__meta_bool__(self.value)
    
    def __contains__(self, other: Any) -> bool:
        return self._type.__meta_contains__(self.value, other.value if isinstance(other, TypeObject) else other)
    
    def __len__(self) -> int:
        return self._type.__meta_len__(self.value)
    
    def __iter__(self) -> Any:
        return self._type.__meta_iter__(self.value)
    
    def __getitem__(self, index: Any) -> Any:
        return self._type.__meta_getitem__(self.value, index)
    
    def __hash__(self) -> int:
        return self._type.__meta_hash__(self.value)
