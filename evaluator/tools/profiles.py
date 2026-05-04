from __future__ import annotations

from .specs import ToolProfile


def code_profile() -> ToolProfile:
    return ToolProfile(
        name="code",
        tool_ids=[
            "pyexec",
            "create_automation_code",
        ],
    )


def tool_profile() -> ToolProfile:
    return ToolProfile(
        name="tool",
        tool_ids=[
            "query_device",
            "control_device",
            "create_automation_actions",
        ],
    )


def advanced_tool_profile() -> ToolProfile:
    return ToolProfile(
        name="advanced_tool",
        tool_ids=[
            "select_device",
            "query_device_spec",
            "query_device_status",
            "control_device_batch",
            "create_automation_batch_actions",
        ],
    )


def full_context_tool_profile() -> ToolProfile:
    return ToolProfile(
        name="full_context_tool",
        tool_ids=[
            "control_device",
            "create_automation_actions",
        ],
    )
