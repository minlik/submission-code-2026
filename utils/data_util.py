import json
from typing import Any, Dict, Tuple, Union


def extract_reasoning(text: str) -> Dict[str, Any]:
    if text is None:
        return {"content": "", "reasoning_content": None}
    content = text
    reasoning = None
    for start_tag, end_tag in (("<think>", "</think>"), ("<reasoning>", "</reasoning>")):
        start_idx = content.find(start_tag)
        if start_idx == -1:
            continue
        end_idx = content.find(end_tag, start_idx + len(start_tag))
        if end_idx == -1:
            continue
        reasoning = content[start_idx + len(start_tag) : end_idx].strip()
        content = (content[:start_idx] + content[end_idx + len(end_tag) :]).strip()
        break
    return {"content": content.strip(), "reasoning_content": reasoning}


def extract_json(text: str, return_prefix: bool = False) -> Union[str, Tuple[str, str]]:
    if text is None:
        raise ValueError("empty response")
    stripped = text.strip()
    if stripped.startswith("```"):
        block = _extract_fenced_block(stripped)
        if block is not None:
            return _finalize_extract(block, text, return_prefix)
    json_str, prefix = _extract_braced_json(stripped)
    if return_prefix:
        return json_str, prefix
    return json_str


def safe_load_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _extract_fenced_block(text: str) -> Any:
    start = text.find("```")
    if start == -1:
        return None
    start = text.find("\n", start)
    if start == -1:
        return None
    end = text.find("```", start + 1)
    if end == -1:
        return None
    return text[start + 1 : end].strip()


def _extract_braced_json(text: str) -> Tuple[str, str]:
    start = None
    depth = 0
    for idx, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = idx
            depth += 1
        elif ch == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start is not None:
                json_str = text[start : idx + 1]
                prefix = text[:start].strip()
                return json_str, prefix
    raise ValueError("no JSON object found")


def _finalize_extract(block: str, raw: str, return_prefix: bool) -> Union[str, Tuple[str, str]]:
    json_str = block.strip()
    if return_prefix:
        prefix = raw[: raw.find(block)].strip()
        return json_str, prefix
    return json_str
