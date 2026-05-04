from __future__ import annotations

from typing import Protocol

from .specs import ToolCall, ToolContext, ToolResult, ToolSpec


class ToolRuntime(Protocol):
    def spec(self) -> ToolSpec: ...

    def execute(self, call: ToolCall, ctx: ToolContext) -> ToolResult: ...
