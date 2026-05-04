import json
import os
from typing import Any, Dict, Optional


class JudgeRecorder:
    def __init__(self, path: str) -> None:
        self.path = path

    def record(self, payload: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def build_record(
    judge_type: str,
    uuid: Optional[str],
    query_idx: Optional[int],
    prompt: str,
    input_payload: Dict[str, Any],
    response_raw: Any,
    parsed: Any,
    passed: Optional[bool],
    reason: Optional[str],
    error: Optional[str],
) -> Dict[str, Any]:
    return {
        "judge_type": judge_type,
        "uuid": uuid,
        "query_idx": query_idx,
        "prompt": prompt,
        "input": input_payload,
        "response_raw": response_raw,
        "parsed": parsed,
        "passed": passed,
        "reason": reason,
        "error": error,
    }
