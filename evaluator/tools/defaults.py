from __future__ import annotations

from ..data.mha_adapter import MhaAdapter
from ..inference.action_simulator import ActionSimulator
from .builtins.control_device_batch import ControlDeviceBatchToolRuntime
from .builtins.control_device import ControlDeviceToolRuntime
from .builtins.create_automation_actions import CreateAutomationActionsToolRuntime
from .builtins.create_automation_batch_actions import CreateAutomationBatchActionsToolRuntime
from .builtins.create_automation_code import CreateAutomationCodeToolRuntime
from .builtins.pyexec import PyExecToolRuntime
from .builtins.query_device_spec import QueryDeviceSpecToolRuntime
from .builtins.query_device_status import QueryDeviceStatusToolRuntime
from .builtins.query_device import QueryDeviceToolRuntime
from .builtins.query_room import QueryRoomToolRuntime
from .builtins.select_device import SelectDeviceToolRuntime
from .registry import ToolRegistry


def build_default_tool_registry(
    adapter: MhaAdapter | None = None,
    action_simulator: ActionSimulator | None = None,
) -> ToolRegistry:
    resolved_adapter = adapter or MhaAdapter()
    resolved_simulator = action_simulator or ActionSimulator(adapter=resolved_adapter)
    registry = ToolRegistry()
    registry.register(QueryRoomToolRuntime())
    registry.register(QueryDeviceToolRuntime(adapter=resolved_adapter))
    registry.register(SelectDeviceToolRuntime())
    registry.register(QueryDeviceSpecToolRuntime(adapter=resolved_adapter))
    registry.register(QueryDeviceStatusToolRuntime(adapter=resolved_adapter))
    registry.register(ControlDeviceToolRuntime(action_simulator=resolved_simulator))
    registry.register(ControlDeviceBatchToolRuntime(action_simulator=resolved_simulator))
    registry.register(CreateAutomationActionsToolRuntime(action_simulator=resolved_simulator))
    registry.register(CreateAutomationBatchActionsToolRuntime(action_simulator=resolved_simulator))
    registry.register(PyExecToolRuntime())
    registry.register(CreateAutomationCodeToolRuntime())
    return registry
