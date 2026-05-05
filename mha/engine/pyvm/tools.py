from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Dict, List, Optional, Type


__all__ = [
    "PyExecContext",
    "PyExecTool",
    "PyExecToolRegistry",
]


@dataclass
class PyExecContext(object):
    engine: Any
    vm: Any
    session_id: Optional[str] = None
    session_locals: Dict[str, Any] = field(default_factory=dict)


class PyExecTool(object):
    Name: ClassVar[str]
    Description: ClassVar[str] = ""

    @classmethod
    def field_names(cls) -> List[str]:
        model_fields = getattr(cls, "model_fields", None)
        if model_fields:
            return list(model_fields.keys())

        signature = inspect.signature(cls.__init__)
        names = []
        for name, param in signature.parameters.items():
            if name == "self":
                continue
            if param.kind in [inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD]:
                continue
            names.append(name)
        return names

    @classmethod
    def from_call(cls, *args, **kwargs) -> "PyExecTool":
        field_names = cls.field_names()
        if len(args) > len(field_names):
            raise TypeError(f"{cls.Name}() takes at most {len(field_names)} positional arguments but {len(args)} were given")

        call_kwargs = dict(kwargs)
        for name, value in zip(field_names, args):
            if name in call_kwargs:
                raise TypeError(f"{cls.Name}() got multiple values for argument '{name}'")
            call_kwargs[name] = value
        return cls(**call_kwargs)

    @classmethod
    def invoke(cls, ctx: PyExecContext, *args, **kwargs) -> Any:
        tool = cls.from_call(*args, **kwargs)
        return tool.execute(ctx)

    @classmethod
    def bind(cls, ctx: PyExecContext) -> Callable[..., Any]:
        def _tool(*args, **kwargs):
            return cls.invoke(ctx, *args, **kwargs)

        _tool.__name__ = cls.Name
        _tool.__doc__ = cls.Description
        return _tool

    @classmethod
    def definitions(cls) -> Dict[str, str]:
        signature = inspect.signature(cls.__init__)
        params = []
        for name, param in signature.parameters.items():
            if name == "self":
                continue
            if param.kind in [inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD]:
                continue

            param_str = name
            if param.annotation != inspect.Parameter.empty:
                annotation = param.annotation
                if hasattr(annotation, "__name__"):
                    param_str += f": {annotation.__name__}"
                else:
                    param_str += f": {annotation}"
            if param.default != inspect.Parameter.empty:
                param_str += f" = {repr(param.default)}"
            params.append(param_str)

        doc = ""
        if cls.Description:
            doc = f'    """{cls.Description}"""\n'
        return {
            cls.Name: f"def {cls.Name}({', '.join(params)}):\n{doc}"
        }

    def execute(self, ctx: PyExecContext) -> Any:
        raise NotImplementedError


class PyExecToolRegistry(object):
    _tools: ClassVar[Dict[str, Type[PyExecTool]]] = {}
    _toolsets: ClassVar[Dict[str, List[Type[PyExecTool]]]] = {}

    @classmethod
    def register_tool(cls, tool: Type[PyExecTool]) -> None:
        if not issubclass(tool, PyExecTool):
            raise TypeError(f"tool must inherit PyExecTool, got {tool}")
        current = cls._tools.get(tool.Name)
        if current is not None and current is not tool:
            raise ValueError(f"tool '{tool.Name}' already registered")
        cls._tools[tool.Name] = tool

    @classmethod
    def register_toolset(cls, name: str, tools: List[Type[PyExecTool]]) -> None:
        for tool in tools:
            cls.register_tool(tool)

        current = cls._toolsets.get(name)
        if current is not None:
            if [tool.Name for tool in current] == [tool.Name for tool in tools]:
                return
            raise ValueError(f"toolset '{name}' already registered")
        cls._toolsets[name] = list(tools)

    @classmethod
    def get_toolset(cls, name: str) -> List[Type[PyExecTool]]:
        toolset = cls._toolsets.get(name)
        if toolset is None:
            raise KeyError(f"toolset '{name}' is not registered")
        return list(toolset)

    @classmethod
    def resolve_toolsets(cls, names: List[str]) -> List[Type[PyExecTool]]:
        resolved: List[Type[PyExecTool]] = []
        seen: Dict[str, Type[PyExecTool]] = {}
        for name in names:
            for tool in cls.get_toolset(name):
                prev = seen.get(tool.Name)
                if prev is not None and prev is not tool:
                    raise ValueError(f"duplicate tool name '{tool.Name}' across toolsets")
                if prev is None:
                    seen[tool.Name] = tool
                    resolved.append(tool)
        return resolved

    @classmethod
    def describe_toolset(cls, name: str) -> str:
        definitions = []
        for tool in cls.get_toolset(name):
            definitions.extend(tool.definitions().values())
        return "\n".join(definitions)
