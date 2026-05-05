from typing import Optional, Sequence, Dict, Any, Tuple
from .attribute import Argument, Attribute
from .object import SyntaxObject, register


__all__ = ["Service"]



class Service(SyntaxObject):
    def __init__(
        self,
        code: Optional[str] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self._code = code
        self._compiled_code = None if code is None else compile(code, '<string>', 'exec')
    
    @property
    def arguments(self) -> Sequence[Argument]:
        return self._type_children.get(Argument, [])
    
    @property
    def code(self) -> Optional[str]:
        return self._code
    
    def __str__(self):
        args = ','.join([a.name for a in self.arguments])
        return f"{self.__class__.__name__}({self.name}, args=({args}))"
    
    __repr__ = __str__
    
    def to_dict(self) -> Dict[str, Any]:
        extras = {
            'code': self.code,
        }
        d = super().to_dict()
        d.update({**{k: v for k, v in extras.items() if v is not None}})
        return d
    
    def __call__(self, *args, **kwargs):
        args, kwargs = self.extract_arguments(*args, **kwargs)
        ret_value = error = None
        try:
            ret_value = self._execute(*args, **kwargs)
            return ret_value
        except Exception as e:
            error = e
            raise e
        finally:
            self.send_event('call_service', service=self, args=args, kwargs=kwargs, ret_value=ret_value, error=error)

    def _execute(self, *args, **kwargs):
        if self._compiled_code is None:
            return

        # get context
        ctx = {}
        def _dfs_parent(node: SyntaxObject):
            nonlocal ctx
            if node is None:
                return
            ctx[node.__class__.__name__.lower()] = node
            _dfs_parent(node.parent)

        input_args = self.make_arguments(*args, **kwargs)
        input_args.update(**ctx, **{"self": self.parent})

        # exec
        return exec(self._compiled_code, {}, input_args)
    
    def check_arguments(self, *args, **kwargs):
        args, kwargs = self.extract_arguments(*args, **kwargs)
        name2idxes = {a.name: i for i, a in enumerate(self.arguments)}
        states = [False] * len(self.arguments)

        # check args
        for i, v in enumerate(args):
            self.arguments[i].check_value(v)
            states[i] = True

        # check kwargs
        for k, v in kwargs.items():
            idx = name2idxes.get(k, None)
            if idx is None:
                raise TypeError(f"{self.name}() got an unexpected keyword argument '{k}'")
            if states[idx]:
                raise TypeError(f"{self.name}() got multiple values for argument '{k}'")
            self.arguments[idx].check_value(v)
            states[idx] = True

        # check default
        for i, arg in enumerate(self.arguments):
            if states[i]:
                continue
            if arg.assigned:
                continue
            raise TypeError(f"{self.name}() missing required argument '{arg.name}'")

    def make_arguments(self, *args, **kwargs) -> Dict[str, Any]:
        name2idxes = {a.name: i for i, a in enumerate(self.arguments)}
        states = [False] * len(self.arguments)
        inputs = [None] * len(self.arguments)

        # check args
        for i, v in enumerate(args):
            self.arguments[i].check_value(v)
            states[i] = True
            inputs[i] = v

        # check kwargs
        for k, v in kwargs.items():
            idx = name2idxes.get(k, None)
            if idx is None:
                raise TypeError(f"{self.name}() got an unexpected keyword argument '{k}'")
            if states[idx]:
                raise TypeError(f"{self.name}() got multiple values for argument '{k}'")
            self.arguments[idx].check_value(v)
            states[idx] = True
            inputs[idx] = v

        # check default
        for i, arg in enumerate(self.arguments):
            if states[i]:
                continue
            if not arg.assigned:
                raise TypeError(f"{self.name}() missing required argument '{arg.name}'")
            states[i] = True
            inputs[i] = arg.value
            
        # arguments
        return {arg.name: value for arg, value in zip(self.arguments, inputs)}
    

    @staticmethod
    def extract_arguments(*args, **kwargs) -> Tuple[Tuple, Dict]:
        def _dfs_extract(arg):
            if isinstance(arg, Attribute):
                return arg.value
            elif isinstance(arg, (list, tuple)):
                return type(arg)(map(_dfs_extract, arg))
            elif isinstance(arg, dict):
                return {k: _dfs_extract(v) for k, v in arg.items()}
            else:
                return arg
            
        return _dfs_extract(args), _dfs_extract(kwargs)
    

register(Service)
