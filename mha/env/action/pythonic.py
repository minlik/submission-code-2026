from typing import Optional, Dict, Any
from mha.engine import HomeEngine
from .action import Action, ActionCallResult


__all__ = ['PyCall', 'PyExec', 'PyEval']



class PyCall(Action):
    Method: str

    def __init__(self, code: str):
        self._code = code

    @property
    def method(self) -> str:
        return self.Method

    @property
    def code(self) -> str:
        return self._code
    
    def __call__(self, *args, **kwds) -> ActionCallResult:
        result = ActionCallResult(input=self)
        pyres = self.execute(*args, **kwds)
        result.stdout = str(pyres.retvalue) if self.method == "eval" else pyres.stdout
        result.error = pyres.error
        result.stderr = pyres.stderr
        return result

    def execute(self, engine: HomeEngine):
        if self.method == 'eval':
            return engine.eval(self._code)
        elif self.method == 'exec':
            return engine.exec(self._code)
        else:
            raise ValueError(f'invalid method: {self.method}')
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({'code': self._code})
        return d
    


class PyExec(PyCall):
    Name = 'pyexec'
    Description = 'execute python code'
    Method = 'exec'


class PyEval(PyCall):
    Name = 'pyeval'
    Description = 'evaluate python code'
    Method = 'eval'


Action.register(PyExec)
Action.register(PyEval)