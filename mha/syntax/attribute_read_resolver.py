from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator, Protocol


@dataclass(frozen=True)
class AttributeReadResult:
    handled: bool
    value: Any = None


class AttributeReadResolver(Protocol):
    def on_read(self, attribute: Any) -> AttributeReadResult:
        ...


_current_attribute_read_resolver: ContextVar[AttributeReadResolver | None] = ContextVar(
    "current_attribute_read_resolver",
    default=None,
)


def current_attribute_read_resolver() -> AttributeReadResolver | None:
    return _current_attribute_read_resolver.get()


@contextmanager
def attribute_read_resolver(resolver: AttributeReadResolver | None) -> Iterator[None]:
    token = _current_attribute_read_resolver.set(resolver)
    try:
        yield
    finally:
        _current_attribute_read_resolver.reset(token)

