from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolSpec:
    tool_id: str
    model_name: str
    description: str
    input_schema: dict[str, Any]
    strict: bool = False


@dataclass
class ToolCall:
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    raw_call: Any = None


@dataclass
class ToolResult:
    call_id: str
    tool_name: str
    ok: bool
    result: dict[str, Any]
    error_code: str | None = None
    error_message: str | None = None
    meta: dict[str, Any] | None = None


@dataclass
class ToolProfile:
    name: str
    tool_ids: list[str]


@dataclass
class ToolContext:
    env: Any
    engine_data: dict[str, Any]
    profile_name: str
    step_index: int
    sample_meta: dict[str, Any]
