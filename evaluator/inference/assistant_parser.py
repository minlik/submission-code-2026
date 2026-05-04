import json
from typing import Any, Dict, Optional

class AssistantResponseParser:
    def parse(self, content: Any) -> Dict[str, Any]:
        if content is None:
            raise ValueError("empty response")
        if isinstance(content, dict):
            return content
        if not isinstance(content, str):
            raise ValueError("unsupported response type")
        text = content.strip()
        if not text:
            raise ValueError("empty response")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            raise ValueError("invalid JSON response")
        if not isinstance(parsed, dict):
            raise ValueError("response must be a JSON object")
        return parsed

    def normalize_mode(self, payload: Dict[str, Any]) -> Optional[str]:
        mode = payload.get("mode")
        if not isinstance(mode, str):
            return None
        return mode.strip().lower()
