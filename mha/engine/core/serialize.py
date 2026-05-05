from typing import Optional, Dict
from abc import ABC, abstractmethod


__all__ = ['ISerializer']



class ISerializer(ABC):

    @classmethod
    def from_dict(cls, data: Dict) -> "ISerializer":
        return cls(**data)

    @abstractmethod
    def to_dict(self) -> "ISerializer":
        pass


    def copy(self) -> "ISerializer":
        return type(self).from_dict(self.to_dict())