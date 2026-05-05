from typing import Optional, Dict, Any, Callable
from croniter import croniter
from mha.syntax import Attribute, Service
from mha.engine import HomeEngine
from .action import Action



__all__ = ['ControlDevice']


def _op_eq(a: Attribute, b: Any): a.value = b
def _op_add_eq(a: Attribute, b: Any): a.value += b
def _op_sub_eq(a: Attribute, b: Any): a.value -= b
def _op_mul_eq(a: Attribute, b: Any): a.value *= b
def _op_truediv_eq(a: Attribute, b: Any): a.value /= b
def _op_floordiv_eq(a: Attribute, b: Any): a.value //= b


class ControlDevice(Action):
    Name: str = 'control_device'
    Description: str = "control a device"

    OPERATORS: Dict[str, Callable] = {
        '=': _op_eq,
        '+=': _op_add_eq,
        '-=': _op_sub_eq,
        '*=': _op_mul_eq,
        '/=': _op_truediv_eq,
        '//=': _op_floordiv_eq,
    }

    def __init__(
        self, 
        did: str, 
        locator: str,
        arguments: Optional[Dict[str, Any]] = None,
        value: Optional[Any] = Any,
        operator: str = '=',
        cron: Optional[str] = None
    ):
        self._did = did
        self._locator = locator
        self._arguments = arguments
        self._value = value
        self._operator = operator
        self._cron = cron

    @property
    def did(self) -> str:
        return self._did
    
    @property
    def locator(self) -> str:
        return self._locator
    
    @property
    def arguments(self) -> Optional[Dict[str, Any]]:
        return self._arguments
    
    @property
    def value(self) -> Optional[Any]:
        return self._value
    
    @property
    def operator(self) -> str:
        return self._operator
    
    @property
    def cron(self) -> Optional[str]:
        return self._cron
    
    def to_dict(self) -> Dict:
        data = super().to_dict()
        data.update({"did": self._did, "locator": self._locator})
        if self._arguments is not None:
            data["arguments"] = self._arguments
        if self._value is not None:
            data["value"] = self._value
        if self._cron is not None:
            data["cron"] = self._cron
        return data
    
    def execute(self, engine: HomeEngine):
        # get device
        device = engine.home.get_device(self._did)
        assert device is not None, f"no such device '{self._did}'"

        # locate and check
        obj = device.locate(self._locator)
        if type(obj) == Attribute:
            assert self._value is not None, f"value is required for attribute control"
            assert self._operator in self.OPERATORS, f"invalid operator '{self._operator}'"
        elif type(obj) == Service:
            kwds = {} if self._arguments is None else self._arguments
            assert isinstance(kwds, dict), f"invalid arguments type '{type(kwds)}', expected: dict"
            obj.check_arguments(**kwds)
        else:
            raise AttributeError(f"can not control locator '{self._locator}', expected: attribute or service, got '{type(obj)}'")
        
        # cron todo
        if self._cron is not None:
            if not croniter.is_valid(self._cron, second_at_beginning=True):
                raise ValueError(f"invalid cron expression '{self._cron}'")
        
        # execute
        if type(obj) == Attribute: 
            self.OPERATORS[self._operator](obj, self._value)
        elif type(obj) == Service:
            obj(**({} if self._arguments is None else self._arguments))
        else:
            assert False, f"invalid object type '{type(obj)}'"


Action.register(ControlDevice)