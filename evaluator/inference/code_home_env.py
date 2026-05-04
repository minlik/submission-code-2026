from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..data.mha_adapter import MhaAdapter


class CodeHomeEnvironmentFormatter:
    def __init__(self, adapter: Optional[MhaAdapter] = None) -> None:
        self.adapter = adapter or MhaAdapter()

    def format(self, engine_data: Dict[str, Any], entrance: Optional[str]) -> str:
        lines: List[str] = []

        room_lines = self._format_rooms(engine_data)
        if room_lines:
            lines.append("家庭房间：")
            lines.extend(room_lines)

        device_lines = self._format_device_index(engine_data)
        if device_lines:
            if lines:
                lines.append("")
            lines.append("家庭设备索引：")
            lines.extend(device_lines)

        entrance_line = self._format_entrance(engine_data, entrance)
        if entrance_line:
            if lines:
                lines.append("")
            lines.append(entrance_line)

        outdoor_context_line = self._format_outdoor_context(engine_data)
        if outdoor_context_line:
            if lines:
                lines.append("")
            lines.append(outdoor_context_line)

        return "\n".join(lines).strip()

    def _format_rooms(self, engine_data: Dict[str, Any]) -> List[str]:
        lines: List[str] = []
        for room in self.adapter.rooms(engine_data):
            room_id = room.get("id", "unknown")
            name = room.get("name") or room.get("type") or "未命名房间"
            room_type = room.get("type") or "unknown"
            floor = room.get("floor", "unknown")
            parent = room.get("parent")
            line = f'- {name}(id="{room_id}") type={room_type} floor={floor}'
            if parent is not None:
                line += f' parent="{parent}"'
            lines.append(line)
        return lines

    def _format_device_index(self, engine_data: Dict[str, Any]) -> List[str]:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for device in self.adapter.devices(engine_data):
            userdata = device.get("userdata") or {}
            room_id = str(userdata.get("room") or "unknown")
            grouped[room_id].append(device)

        room_names = self._room_names(engine_data)
        ordered_room_ids = list(room_names.keys())
        for room_id in grouped.keys():
            if room_id not in room_names:
                ordered_room_ids.append(room_id)

        lines: List[str] = []
        for room_id in ordered_room_ids:
            room_devices = grouped.get(room_id) or []
            if not room_devices:
                continue
            room_name = room_names.get(room_id) or room_id
            lines.append(f'{room_name}(id="{room_id}")')
            for device in room_devices:
                userdata = device.get("userdata") or {}
                name = device.get("name") or userdata.get("subcategory") or "未命名设备"
                did = userdata.get("did") or "unknown"
                spid = userdata.get("spid") or "unknown"
                category = userdata.get("category") or "unknown"
                subcategory = userdata.get("subcategory") or "unknown"
                tags = userdata.get("tags") or []
                brand = userdata.get("brand") or "unknown"
                lines.append(
                    f"- {name}: did={did} spid={spid} category={category} "
                    f"subcategory={subcategory} tags={tags} brand={brand}"
                )
        return lines

    def _format_entrance(self, engine_data: Dict[str, Any], entrance: Optional[str]) -> Optional[str]:
        if not entrance:
            return None
        device = self.adapter.find_device(engine_data, entrance)
        if not device:
            return f"用户指令入口: did={entrance}"
        userdata = device.get("userdata") or {}
        room_name = self.adapter.room_name(engine_data, userdata.get("room"))
        device_name = device.get("name") or userdata.get("subcategory") or "unknown"
        room_desc = room_name or userdata.get("room") or "unknown"
        return f"用户指令入口: did={entrance}; device={device_name}; room={room_desc}"

    def _format_outdoor_context(self, engine_data: Dict[str, Any]) -> Optional[str]:
        outdoor = (engine_data.get("home") or {}).get("outdoor") or {}
        raw_time = str(outdoor.get("time") or "").strip()
        if not raw_time:
            return None
        weekday = self._weekday_from_time(raw_time)
        if weekday:
            return f"当前时间: {raw_time}; 今天是: {weekday}"
        return f"当前时间: {raw_time}"

    @staticmethod
    def _weekday_from_time(raw_time: str) -> Optional[str]:
        normalized = raw_time.strip()
        for parser in (
            lambda value: datetime.strptime(value, "%Y-%m-%d %H:%M:%S"),
            lambda value: datetime.strptime(value, "%Y-%m-%d %H:%M"),
            lambda value: datetime.strptime(value, "%Y-%m-%d"),
            lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")),
        ):
            try:
                dt = parser(normalized)
                break
            except ValueError:
                continue
        else:
            return None
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return weekdays[dt.weekday()]

    def _room_names(self, engine_data: Dict[str, Any]) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for room in self.adapter.rooms(engine_data):
            room_id = room.get("id")
            if room_id is None:
                continue
            result[str(room_id)] = room.get("name") or room.get("type") or str(room_id)
        return result
