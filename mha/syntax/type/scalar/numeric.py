import typing
from typing import Optional, Sequence, Tuple, Union, Any
import random
import numpy as np
from .scalar import Scalar


__all__ = [
    'Numeric',
    'Uint8',
    'Uint16',
    'Uint32',
    'Uint64',
    'Int8',
    'Int16',
    'Int32',
    'Int64',
    'Float16',
    'Float32',
    'Float64',

    'Uint',
    'Int',
    'Float',
]


class Numeric(Scalar):
    __INT_TYPES__ = {np.uint8, np.uint16, np.uint32, np.uint64, np.int8, np.int16, np.int32, np.int64}
    __FLOAT_TYPES__ = {np.float16, np.float32, np.float64}
    __TYPE_IINFOS__ = {**{tp: np.iinfo(tp) for tp in __INT_TYPES__}, **{tp: np.finfo(tp) for tp in __FLOAT_TYPES__}}

    Type: typing.Type

    def __call__(self, value: Any) -> Any:
        if self._precision is not None:
            value = round(value / self._precision) * self._precision
        if self._range is not None:
            if value < self._range[0]:
                value = self._range[0]
            elif value > self._range[1]:
                value = self._range[1]
        return self.Type(value).item()

    def check_type(self, value: Any) -> bool:
        # type
        if self.is_integer_type(self.Type):
            if not (isinstance(value, int) or (isinstance(value, float) and value.is_integer())):
                return False
        elif self.is_float_type(self.Type):
            if not isinstance(value, (int, float)):
                return False
        else:
            return False

        # size
        iinfo = self.__TYPE_IINFOS__[self.Type]
        return iinfo.min <= value <= iinfo.max
    
    def set_range(self, range: Tuple):
        # check
        assert isinstance(range, (tuple, list)), f"invalid range {range}, expected tuple or list"
        assert len(range) == 2, f"invalid range {range}, expected tuple or list with length 2"
        for it in range:
            if self.check_type(it):
                continue
            raise ValueError(f"invalid range {range}, expected element type '{self.name}'")
        self._range = tuple(range)

    def set_precision(self, precision: Union[float, int]):
        if not self.check_type(precision):
            raise ValueError(f"invalid precision {precision} with type {type(precision)}, expected element type '{self.name}'")        
        self._precision = precision

    def set_options(self, options: Sequence[Union[float, int]]):
        assert isinstance(options, (tuple, list)), f"invalid options {options}, expected tuple or list"
        for it in options:
            if self.check_type(it):
                continue
            raise ValueError(f"invalid options {options}, expected element type '{self.name}'")
        self._options = options

    def check_range(self, value: Any) -> bool:
        if self._range is None:
            return True
        return self._range[0] <= value <= self._range[1]
    
    def check_precision(self, value: Any) -> bool:
        if self._precision is None:
            return True
        remainder = abs(value) % self._precision
        return (remainder < 1e-6) or (abs(remainder - self._precision) < 1e-6)
    
    def check_options(self, value: Any) -> bool:
        if self._options is None:
            return True
        return value in self._options
    
    def rand_value(self) -> Any:
        # options
        if self._options is not None:
            return random.sample(self._options, 1)[0]

        # min max
        if self._range is None:
            info = self.__TYPE_IINFOS__[self.Type]
            vmin, vmax = info.min/2, info.max/2
        else:
            vmin, vmax = self._range

        # value
        if self.is_integer_type(self.Type):
            value = np.random.randint(vmin, vmax+1)
        elif self.is_float_type(self.Type):
            value = np.random.uniform(vmin, vmax)

        # normalize
        return self(value)
    
    def __meta_lt__(self, lhs: Any, rhs: Any) -> bool:
        return lhs < rhs
    
    def __meta_gt__(self, lhs: Any, rhs: Any) -> bool:
        return lhs > rhs
    
    def __meta_le__(self, lhs: Any, rhs: Any) -> bool:
        return lhs <= rhs
    
    def __meta_ge__(self, lhs: Any, rhs: Any) -> bool:
        return lhs >= rhs
    
    def __meta_add__(self, lhs: Any, rhs: Any) -> Any:
        return lhs + rhs
    
    def __meta_sub__(self, lhs: Any, rhs: Any) -> Any:
        return lhs - rhs
    
    def __meta_mul__(self, lhs: Any, rhs: Any) -> Any:
        return lhs * rhs
    
    def __meta_true_div__(self, lhs: Any, rhs: Any) -> Any:
        return lhs / rhs
    
    def __meta_floor_div__(self, lhs: Any, rhs: Any) -> Any:
        return lhs // rhs
    
    def __meta_mod__(self, lhs: Any, rhs: Any) -> Any:
        return lhs % rhs
    
    def __meta_pow__(self, lhs: Any, rhs: Any) -> Any:
        return lhs ** rhs
    
    @staticmethod
    def is_integer_type(type: typing.Type) -> bool:
        return type in Numeric.__INT_TYPES__
    
    @staticmethod
    def is_float_type(type: typing.Type) -> bool:
        return type in Numeric.__FLOAT_TYPES__



class Uint8(Numeric):
    Type = np.uint8

class Uint16(Numeric):
    Type = np.uint16

class Uint32(Numeric):
    Type = np.uint32

class Uint64(Numeric):
    Type = np.uint64

class Int8(Numeric):
    Type = np.int8

class Int16(Numeric):
    Type = np.int16

class Int32(Numeric):
    Type = np.int32

class Int64(Numeric):
    Type = np.int64

class Float16(Numeric):
    Type = np.float16

class Float32(Numeric):
    Type = np.float32

class Float64(Numeric):
    Type = np.float64


class Uint(Numeric):
    Type = np.uint

class Int(Numeric):
    Type = np.int64

class Float(Numeric):
    Type = np.float64
