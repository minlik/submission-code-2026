from typing import Optional, Any, Dict, Union
from .type import TypeObject
from .object import register


__all__ = [
    'Attribute',
    'Argument',
]


class Attribute(TypeObject):

    _unit: Optional[str] = None
    _mode: Optional[str] = None,

    def __init__(
        self,  
        unit: Optional[str] = None,
        mode: Optional[str] = None,
        **kwargs
    ):
        super().__init__(**kwargs)

        # mode
        for c in ('' if mode is None else mode):
            if c not in 'rw':
                raise ValueError(f"invalid mode '{mode}' for attribute '{self.name}'")
        self._mode = mode

        # unit
        self._unit = unit
        
             
    @property
    def unit(self) -> Optional[str]:
        return self._unit
    
    @property
    def mode(self) -> Optional[str]:
        return self._mode
    
    @property
    def readable(self) -> bool:
        return self._mode is not None and 'r' in self._mode
    
    @property
    def writable(self) -> bool:
        return self._mode is not None and 'w' in self._mode

    def __str__(self) -> str:
        return str(self._value)
    
    def __repr__(self):
        s_desc = None if self.description is None else f"{self.description[:10]}..." if len(self.description) > 10 else self.description

        args = ', '.join([str(a) for a in (
            self.name,
            None if not self.assigned else f"value={getattr(self, '_value', None)}",
            None if self.unit is None else f"unit={self.unit}",
            None if self.mode is None else f"mode={self.mode}",
            self._type,
            s_desc,
        ) if a is not None])
        return f"{self.__class__.__name__}({args})"
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update(self._type.to_dict())
        if self._unit is not None:
            d['unit'] = self.unit
        if self._mode is not None:
            d['mode'] = self.mode
        if self.assigned:
            d['value'] = self.value
        return d
    
    

class Argument(Attribute):
    @property
    def value(self) -> Any:
        return super().value

    @value.setter
    def value(self, value: Any):
        raise RuntimeError(f"cannot set value for read only argument '{self.name}'")
    


register(Attribute)
register(Argument)