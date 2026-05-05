from typing import Optional, Type, Sequence, Tuple, Any, Dict
from mha.syntax.type.base import Base


__all__ = ['Scalar']


class Scalar(Base):

    _range: Optional[Tuple] = None
    _precision: Optional[float] = None
    _options: Optional[Tuple[Any, Any]] = None

    def __init__(
        self,
        range: Optional[Tuple] = None,
        precision: Optional[float] = None,
        options: Optional[Tuple[Any, Any]] = None
    ):
        assert self.scalar, f"type '{self.name}' is not scalar type"
        if range is not None:
            self.set_range(range)
        if precision is not None:
            self.set_precision(precision)
        if options is not None:
            self.set_options(options)

    @property
    def nested(self) -> bool:
        return False

    @property
    def range(self) -> Optional[Tuple]:
        return self._range
        
    @property
    def precision(self) -> Optional[float]:
        return self._precision
    
    @property
    def options(self) -> Optional[Sequence[Any]]:
        return self._options
    
    def __str__(self) -> str:
        return ", ".join([v for v in [
            f"type={self.name}",
            f"range={self.range}" if self.range is not None else None,
            f"options={self.options}" if self.options is not None else None,
            f"precision={self.precision}" if self.precision is not None else None,
        ] if v is not None])
    
    def to_dict(self) -> Dict:
        d = super().to_dict()
        if self.range is not None:
            d['range'] = list(self.range)
        if self.precision is not None:
            d['precision'] = self.precision
        if self.options is not None:
            d['options'] = self.options
        return d

    def set_range(self, range: Tuple):
        raise NotImplementedError(f"Type '{self.name}' does not support set_range")
    
    def set_precision(self, precision: float):
        raise NotImplementedError(f"Type '{self.name}' does not support set_precision")
    
    def set_options(self, range: Sequence):
        raise NotImplementedError(f"Type '{self.name}' does not support set_options")
    
    def check_range(self, value: Any) -> bool:
        if self._range is None:
            return True
        raise NotImplementedError(f"Type '{self.name}' does not support check_range")
    
    def check_precision(self, value: Any) -> bool:
        if self._precision is None:
            return True
        raise NotImplementedError(f"Type '{self.name}' does not support check_precision")
    
    def check_options(self, value: Any) -> bool:
        if self._options is None:
            return True
        if value not in self._options:
            raise ValueError(f"value '{value}' is not in options {self._options}")

    def check(self, value: Any, raise_error: bool = False) -> bool:
        if not self.check_type(value):
            if raise_error:
                raise ValueError(f"invalid value '{repr(value)}' for type '{self.name}'")
            return False
        if not self.check_range(value):
            if raise_error:
                raise ValueError(f"value '{value}' is outside the range '{self.range}', type: '{self.name}'")
            return False
        if not self.check_precision(value):
            if raise_error:
                raise ValueError(f"value '{value}' does not have enough precision, type: '{self.name}' precision: '{self.precision}'")
            return False
        if not self.check_options(value):
            if raise_error:
                raise ValueError(f"value '{value}' is not in options {self._options}, type: '{self.name}'")
            return False
        return True
    
    def __meta_eq__(self, lhs: Any, rhs: Any) -> bool:
        return lhs == rhs
    
    def __meta_ne__(self, lhs: Any, rhs: Any) -> bool:
        return not self.__meta_eq__(lhs, rhs)
    
    def __meta_hash__(self, lhs: Any) -> int:
        return hash(lhs)
    
    def __meta_bool__(self, lhs: Any) -> bool:
        return bool(lhs)
