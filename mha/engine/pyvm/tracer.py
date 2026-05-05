from typing import Optional, Callable, Self
import sys
import time


__all__ = ["Tracer", "TracerTimeoutError"]


class TracerTimeoutError(BaseException):
    pass


class Tracer(object):
    def __init__(self, timeout: Optional[float] = None):
        self._timeout = timeout
        self._deadline: Optional[float] = None
        self._origin_trace: Optional[Callable] = None

    @property
    def timeout(self) -> Optional[float]:
        return self._timeout
    
    @property
    def deadline(self) -> Optional[float]:
        return self._deadline
    
    @property
    def origin_trace(self) -> Optional[Callable]:
        return self._origin_trace

    def __enter__(self) -> Self:
        if self._timeout is not None:
            self._deadline = time.monotonic() + self._timeout
            sys.settrace(self.tracefunc)
        return self
    
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._timeout is not None:
            sys.settrace(self._origin_trace)

    def tracefunc(self, frame, event, arg):
        if time.monotonic() >= self._deadline:
            raise TracerTimeoutError(f"Code execute timeout, timeout: {self._timeout}s")
        return self.tracefunc