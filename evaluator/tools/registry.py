from __future__ import annotations

from typing import Any

from .runtime import ToolRuntime
from .specs import ToolCall, ToolContext, ToolProfile, ToolResult, ToolSpec


class ToolRegistry:
    def __init__(self) -> None:
        self._runtimes: dict[str, ToolRuntime] = {}

    def register(self, runtime: ToolRuntime) -> None:
        spec = runtime.spec()
        self._runtimes[spec.tool_id] = runtime

    def get_by_id(self, tool_id: str) -> ToolRuntime:
        try:
            return self._runtimes[tool_id]
        except KeyError as exc:
            raise KeyError(f"unknown tool id: {tool_id}") from exc

    def resolve_model_name(self, profile: ToolProfile, model_name: str) -> ToolRuntime:
        for tool_id in profile.tool_ids:
            runtime = self._runtimes.get(tool_id)
            if runtime is None:
                continue
            if runtime.spec().model_name == model_name:
                return runtime
        raise KeyError(f"tool {model_name!r} is not available in profile {profile.name!r}")

    def specs(self, profile: ToolProfile) -> list[ToolSpec]:
        return [self.get_by_id(tool_id).spec() for tool_id in profile.tool_ids]

    def schemas(self, profile: ToolProfile) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.model_name,
                    "description": spec.description,
                    "strict": spec.strict,
                    "parameters": spec.input_schema,
                },
            }
            for spec in self.specs(profile)
        ]

    def execute(self, profile: ToolProfile, call: ToolCall, ctx: ToolContext) -> ToolResult:
        runtime = self.resolve_model_name(profile, call.tool_name)
        return runtime.execute(call, ctx)

    def reset_runtime_state(self, profile: ToolProfile) -> None:
        for runtime in self._iter_profile_runtimes(profile):
            reset = getattr(runtime, "reset_created_automations", None)
            if callable(reset):
                reset()

    def drain_created_automations(self, profile: ToolProfile) -> list[dict[str, Any]]:
        drained: list[dict[str, Any]] = []
        for runtime in self._iter_profile_runtimes(profile):
            drain = getattr(runtime, "drain_created_automations", None)
            if not callable(drain):
                continue
            items = drain()
            if isinstance(items, list):
                drained.extend(dict(item) for item in items if isinstance(item, dict))
        return drained

    def _iter_profile_runtimes(self, profile: ToolProfile) -> list[ToolRuntime]:
        runtimes: list[ToolRuntime] = []
        for tool_id in profile.tool_ids:
            runtime = self._runtimes.get(tool_id)
            if runtime is not None:
                runtimes.append(runtime)
        return runtimes
