from typing import Optional, Sequence, Any, Set, Dict, List
import secrets
from dataclasses import dataclass, field
from mha.syntax import Attribute, Service
from mha.engine.core import ISerializer
from mha.engine.home import Device


__all__ = ["Rule", "Log"]


@dataclass
class Rule(ISerializer):

    id: str
    action: str
    key: str
    values: Set[Any]
    def __init__(self, action: str, key: str, values: Sequence[Any], id: Optional[str] = None):
        assert action in {"allow", "deny"}, ValueError(f"invalid rule action '{action}'")
        self.id = secrets.token_urlsafe(6)[:8] if id is None else id
        self.action = action
        self.key = key
        self.values = set(values)

    def check(self, device: Device) -> bool:
        value = getattr(device, self.key, None)
        hit = (value in self.values)
        return hit if self.action == "allow" else (not hit)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'action': self.action,
            'key': self.key,
            'values': list(self.values),
        }
    
    @classmethod
    def from_dict(cls, content) -> "Rule":
        return cls(**content)
    


@dataclass
class Log(ISerializer):

    did: str
    location: str
    object: str
    prev_value: Optional[Any] = None
    post_value: Optional[Any] = None
    args: Optional[List[Any]] = None
    kwargs: Optional[Dict[str, Any]] = None
    ret_value: Optional[Any] = None
    error: Optional[Exception] = None
    block_rules: Optional[List[str]] = None
    id: str = field(default_factory=lambda: secrets.token_urlsafe(6)[:8])
    
    def add_block_rule(self, rule_id: str) -> None:
        self.block_rules = self.block_rules or []
        self.block_rules.append(rule_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            k: str(getattr(self, k)) if k == "error" else getattr(self, k)
            for k, v in self.__annotations__.items()
            if getattr(self, k) is not None
        }
    
    @classmethod
    def from_dict(cls, content) -> "Log":
        return cls(**content)
    
