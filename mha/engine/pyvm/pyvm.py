from typing import Optional, Any, Dict, List
import io
import sys
import builtins
import traceback
from dataclasses import dataclass
from contextlib import redirect_stdout, redirect_stderr
from mha.engine.core import Plugin
from mha.engine.home import Home, HomeRender, Device, Room
from .stacktrace import Stacktrace
from .tracer import Tracer, TracerTimeoutError
from .tools import PyExecContext, PyExecToolRegistry


__all__ = ["PyVM", "PyCallResult"]



@dataclass
class PyCallResult(object):
    method: str
    input: str
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error: Optional[Exception] = None
    stack: Optional[str] = None
    retvalue: Optional[Any] = None



class PyVM(Plugin):
    Name: str = "pyvm"
    Depends = ["home"]

    def __init__(
        self, 
        stack_mode: str = "codestack", 
        allow_builtins: Optional[List[str]] = None,
        deny_builtins: Optional[List[str]] = None,
        timeout: Optional[float] = None,
        toolsets: Optional[List[str]] = None,
    ):
        self._stack_mode = stack_mode
        self._allow_builtins = allow_builtins
        self._deny_builtins = deny_builtins
        self._timeout = timeout if timeout is not None else 30.0
        self._toolsets = [] if toolsets is None else list(toolsets)

        # reset builtins
        self._reset_builtins()
        
    @property
    def _home(self) -> Home:
        return self.manager.get_plugin("home")

    @property
    def stack_mode(self) -> str:
        return self._stack_mode

    @stack_mode.setter
    def stack_mode(self, value: str) -> None:
        self._stack_mode = value 
    
    @property
    def allow_builtins(self) -> Optional[List[str]]:
        return self._allow_builtins

    @allow_builtins.setter
    def allow_builtins(self, value: Optional[List[str]]):
        self._allow_builtins = value
        self._reset_builtins()
    
    @property
    def deny_builtins(self) -> Optional[List[str]]:
        return self._deny_builtins

    @deny_builtins.setter
    def deny_builtins(self, value: Optional[List[str]]):
        self._deny_builtins = value
        self._reset_builtins()
    
    @property
    def timeout(self) -> Optional[float]:
        return self._timeout

    @timeout.setter
    def timeout(self, value: Optional[float]) -> None:
        self._timeout = value
    
    @property
    def builtins(self) -> Dict:
        return self._builtins
    
    def setup(self, manager):
        super().setup(manager)
        self._out_buf = io.StringIO()
        self._err_buf = io.StringIO()
        PyExecToolRegistry.resolve_toolsets(self._toolsets)

    def exec(self, code: str) -> PyCallResult:
        return self._call("exec", code)
    
    def eval(self, code: str) -> PyCallResult:
        return self._call("eval", code)
    
    def _call(self, method: str, code: str, filename: Optional[str] = None) -> PyCallResult:
        assert method in ["exec", "eval"], f"{method} is not supported"
        f_method = exec if method == "exec" else eval
        filename = filename if filename is not None else "exec_code.py" if method == "exec" else "<eval_code>"
        result = PyCallResult(method=method, input=code)

        # compile and run
        with redirect_stdout(self._out_buf), redirect_stderr(self._err_buf):
            # compile
            try:
                code_obj = compile(code, filename, method)
            except Exception as e:
                traceback.print_exc()
                result.stack = ''.join(traceback.format_exception(*sys.exc_info()))
                result.error = e

            # run
            if result.error is None:
                try:
                    with Tracer(timeout=self._timeout):
                        result.retvalue = f_method(code_obj, self.make_vm_globals())
                except TracerTimeoutError as e:
                    Stacktrace.print_exec(e, code, filename, mode=self._stack_mode)
                    result.stack = ''.join(traceback.format_exception(*sys.exc_info()))
                    result.error = e
                except BaseException as e:
                    Stacktrace.print_exec(e, code, filename, mode=self._stack_mode)
                    result.stack = ''.join(traceback.format_exception(*sys.exc_info()))
                    result.error = e
        

        # read and clear buffers
        if self._out_buf.tell() > 0:
            result.stdout = self._out_buf.getvalue()
        if self._err_buf.tell() > 0:
            result.stderr = self._err_buf.getvalue()
        self.clear_buf()
        return result

    def clear_buf(self):
        self._out_buf.truncate(0)
        self._out_buf.seek(0)
        self._err_buf.truncate(0)
        self._err_buf.seek(0)

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d.update(stack_mode=self._stack_mode)
        if self._timeout is not None:
            d.update(timeout=self._timeout)
        if self._allow_builtins is not None:
            d.update(allow_builtins=self._allow_builtins)
        if self._deny_builtins is not None:
            d.update(deny_builtins=self._deny_builtins)
        if self._toolsets:
            d.update(toolsets=self._toolsets)
        return d

    def make_pyexec_context(self) -> PyExecContext:
        return PyExecContext(engine=self.manager, vm=self)

    def make_tool_globals(self) -> Dict[str, Any]:
        if not self._toolsets:
            return {}

        ctx = self.make_pyexec_context()
        return {
            tool.Name: tool.bind(ctx)
            for tool in PyExecToolRegistry.resolve_toolsets(self._toolsets)
        }

    def make_core_globals(self):
        return dict(
            # home
            home=self._home,
            device=self._home.get_device,
            get_device=self._home.get_device,
            get_devices=lambda : self._home.devices,
            get_room=self._home.get_room,
            get_rooms=lambda: self._home.rooms,

            # render
            render_device=lambda device, mode="spec": HomeRender.render(Device, mode, device, self._home),
            render_room=lambda room: HomeRender.render(Room, 'detail', room, self._home),
        )

    def make_vm_globals(self):
        globals_ = self.make_core_globals()
        globals_.update(self.make_tool_globals())
        globals_["__builtins__"] = self._builtins
        return globals_

    def _reset_builtins(self):
        self._builtins = {
            k: v 
            for k, v in vars(builtins).items()
            if (
                (self._allow_builtins is None or k in self._allow_builtins) and
                (self._deny_builtins is None or k not in self._deny_builtins)
            )
        }


Plugin.register(PyVM)
