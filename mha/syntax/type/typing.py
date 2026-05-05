import typing
from .base import *
from .scalar import *
from .nested import *


__all__ = ['Typing']



class Typing(object):

    NumericTypes: typing.Sequence[typing.Type[Base]] = [
        Uint8, Uint16, Uint32, Uint64, Uint,
        Int8, Int16, Int32, Int64, Int,
        Float16, Float32, Float64, Float,
    ]

    ScalarTypes: typing.Sequence[typing.Type[Base]] = NumericTypes + [
        Str, Bool, Hex, Enum,
    ]

    NestedTypes: typing.Sequence[typing.Type[Base]] = [
        List, Tuple, Dict,
    ]

    Types = ScalarTypes + NestedTypes

    Names = [tp.__name__.lower() for tp in Types]

    Name2Types = {k: v for (k, v) in zip(Names, Types)}

    @staticmethod
    def make(type: str, **kwargs) -> Base:
        cls = Typing.Name2Types.get(type, None)
        if cls is None:
            raise ValueError(f"'{type}' is not a valid type to make")
        return cls(**kwargs)
