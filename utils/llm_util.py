import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from utils.data_util import extract_json, extract_reasoning


@dataclass
class LLMOutput:
    content: Any = None
    reasoning_content: Optional[str] = None
    raw_message: Optional[Any] = None
    tool_calls: Optional[Any] = None
    token_usage: Optional[Dict[str, int]] = None


class LLMClient:
    def __init__(
        self,
        model_url: str,
        api_key: str,
        model_name: str,
        temperature: float = 0,
        enable_thinking: bool = False,
        **kwargs: Any,
    ) -> None:
        self.model_url = model_url
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.enable_thinking = enable_thinking
        self.user = kwargs.get("user")
        self.reasoning_effort = kwargs.get("reasoning_effort", "medium")
        self.verbosity = kwargs.get("verbosity", "medium")
        self.max_tokens = kwargs.get("max_tokens")

    async def get_response(
        self,
        session: Any,
        prompt: Optional[str],
        messages: Optional[Any] = None,
        is_json_output: bool = False,
        tools: Optional[Any] = None,
        tool_choice: Optional[Any] = None,
        parallel_tool_calls: Optional[bool] = None,
        retries: int = 5,
        return_nothink_prefix: bool = False,
    ) -> LLMOutput:
        resolved_messages = self._resolve_messages(prompt=prompt, messages=messages)
        headers = self._build_headers()
        data = self._build_payload(
            messages=resolved_messages,
            tools=tools,
            tool_choice=tool_choice,
            parallel_tool_calls=parallel_tool_calls,
        )
        try:
            response_payload = await self._post_with_retry(
                session=session,
                headers=headers,
                data=data,
                retries=retries,
            )
            return self._parse_output(
                response_payload=response_payload,
                is_json_output=is_json_output,
                return_nothink_prefix=return_nothink_prefix,
            )
        except Exception as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc

    @staticmethod
    def _resolve_messages(prompt: Optional[str], messages: Optional[Any]) -> Optional[Any]:
        if prompt is not None:
            return [{"role": "user", "content": prompt}]
        return messages

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "AIGC-USER": self.user,
        }
        if _requires_aimp_biz_id(model_url=self.model_url, model_name=self.model_name):
            headers["Aimp-Biz-Id"] = self.model_name
        return headers

    def _build_payload(
        self,
        messages: Optional[Any],
        tools: Optional[Any],
        tool_choice: Optional[Any],
        parallel_tool_calls: Optional[bool],
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
        }
        if tools is not None:
            data["tools"] = tools
        if tool_choice is not None:
            data["tool_choice"] = tool_choice
        if parallel_tool_calls is not None:
            data["parallel_tool_calls"] = parallel_tool_calls
        if self.max_tokens is not None:
            data["max_tokens"] = self.max_tokens
        data.update(self._build_model_options())
        return data

    def _build_model_options(self) -> Dict[str, Any]:
        if _is_openrouter_url(self.model_url):
            options: Dict[str, Any] = {"temperature": self.temperature}
            if self.enable_thinking:
                options["reasoning"] = {
                    "effort": self.reasoning_effort,
                    "exclude": False,
                }
            return options

        if _is_gpt5_model(self.model_name):
            return {
                "reasoning_effort": self.reasoning_effort,
                "verbosity": self.verbosity,
            }

        options: Dict[str, Any] = {"temperature": self.temperature}
        if "DeepSeek" in self.model_name:
            options["chat_template_kwargs"] = {"thinking": bool(self.enable_thinking)}
        else:
            options["chat_template_kwargs"] = {"enable_thinking": bool(self.enable_thinking)}
        return options

    async def _post_with_retry(
        self,
        session: Any,
        headers: Dict[str, str],
        data: Dict[str, Any],
        retries: int,
    ) -> Dict[str, Any]:
        delay = 1
        for attempt in range(retries):
            try:
                return await self._post_once(session=session, headers=headers, data=data)
            except Exception:
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                raise
        return {}

    async def _post_once(self, session: Any, headers: Dict[str, str], data: Dict[str, Any]) -> Dict[str, Any]:
        async with session.post(self.model_url, headers=headers, json=data) as response:
            text = await response.text()
            if response.status >= 400:
                error_detail = _extract_error_detail(text)
                reason = f" {response.reason}" if getattr(response, "reason", None) else ""
                raise RuntimeError(f"HTTP {response.status}{reason}: {error_detail}")
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"invalid JSON response from LLM API: {text[:1000]}") from exc

    def _parse_output(
        self,
        response_payload: Dict[str, Any],
        is_json_output: bool,
        return_nothink_prefix: bool,
    ) -> LLMOutput:
        token_usage = normalize_token_usage(response_payload.get("usage"))
        choices = response_payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError(f"LLM response missing choices: {response_payload}")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise RuntimeError(f"LLM response choice must be object: {response_payload}")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise RuntimeError(f"LLM response missing message: {response_payload}")
        tool_calls = message.get("tool_calls")
        final_reasoning_content = message.get("reasoning_content") or message.get("reasoning")
        if not final_reasoning_content:
            final_reasoning_content = _reasoning_details_to_text(message.get("reasoning_details"))
        extract_result = extract_reasoning(message.get("content", ""))
        final_content = extract_result["content"]
        if not final_reasoning_content:
            final_reasoning_content = extract_result.get("reasoning_content")

        if is_json_output:
            return self._parse_json_output(
                message=message,
                tool_calls=tool_calls,
                token_usage=token_usage,
                final_content=final_content,
                final_reasoning_content=final_reasoning_content,
                return_nothink_prefix=return_nothink_prefix,
            )

        return LLMOutput(
            content=final_content,
            reasoning_content=final_reasoning_content,
            raw_message=message,
            tool_calls=tool_calls,
            token_usage=token_usage,
        )

    def _parse_json_output(
        self,
        message: Dict[str, Any],
        tool_calls: Optional[Any],
        token_usage: Dict[str, int],
        final_content: Any,
        final_reasoning_content: Optional[str],
        return_nothink_prefix: bool,
    ) -> LLMOutput:
        if not isinstance(final_content, str):
            raise ValueError("JSON output must be a string")
        if return_nothink_prefix and not final_reasoning_content:
            final_reasoning_content = ""
        try:
            parsed = json.loads(final_content)
        except json.JSONDecodeError as exc:
            try:
                parsed = json.loads(extract_json(final_content))
            except (ValueError, json.JSONDecodeError):
                raise ValueError(_json_content_error_message(message=message, content=final_content)) from exc
        return self._build_output(
            message=message,
            tool_calls=tool_calls,
            token_usage=token_usage,
            content=parsed,
            reasoning_content=final_reasoning_content,
        )

    @staticmethod
    def _build_output(
        message: Dict[str, Any],
        tool_calls: Optional[Any],
        token_usage: Dict[str, int],
        content: Any,
        reasoning_content: Optional[str],
    ) -> LLMOutput:
        return LLMOutput(
            content=content,
            reasoning_content=reasoning_content,
            raw_message=message,
            tool_calls=tool_calls,
            token_usage=token_usage,
        )


def normalize_token_usage(usage: Any) -> Dict[str, int]:
    if not isinstance(usage, dict) or not usage:
        return {}

    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}
    input_details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}
    prompt_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
    completion_tokens = int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)
    total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "reasoning_tokens": int(
            completion_details.get("reasoning_tokens", output_details.get("reasoning_tokens", 0)) or 0
        ),
        "cached_tokens": int(
            prompt_details.get("cached_tokens", input_details.get("cached_tokens", 0)) or 0
        ),
        "llm_calls": 1,
    }


def merge_token_usage(*usages: Optional[Dict[str, int]]) -> Dict[str, int]:
    merged: Dict[str, int] = {}
    for usage in usages:
        if not usage:
            continue
        for key, value in usage.items():
            merged[key] = merged.get(key, 0) + int(value or 0)
    return merged


def _extract_error_detail(text: str) -> str:
    error_detail = text.strip()
    try:
        error_json = json.loads(text)
        if isinstance(error_json, dict):
            nested_error = error_json.get("error")
            if isinstance(nested_error, dict):
                error_detail = nested_error.get("message") or json.dumps(nested_error, ensure_ascii=False)
            else:
                error_detail = error_json.get("message") or nested_error or json.dumps(error_json, ensure_ascii=False)
        else:
            error_detail = json.dumps(error_json, ensure_ascii=False)
    except json.JSONDecodeError:
        pass
    return error_detail


def _reasoning_details_to_text(reasoning_details: Any) -> Optional[str]:
    if not isinstance(reasoning_details, list):
        return None

    parts = []
    for item in reasoning_details:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "reasoning.text":
            parts.append(item.get("text") or "")
        elif item.get("type") == "reasoning.summary":
            parts.append(item.get("summary") or "")

    text = "\n".join(part.strip() for part in parts if isinstance(part, str) and part.strip())
    return text or None


def _json_content_error_message(message: Dict[str, Any], content: str) -> str:
    return (
        "invalid model JSON content: "
        f"content_preview={_preview_text(content)!r}, "
        f"reasoning_present={bool(message.get('reasoning') or message.get('reasoning_content'))}, "
        f"reasoning_details_present={bool(message.get('reasoning_details'))}"
    )


def _preview_text(text: str, limit: int = 300) -> str:
    compact = text.replace("\n", "\\n")
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "...[truncated]"


def _is_gpt5_model(model_name: str) -> bool:
    normalized = (model_name or "").strip().lower()
    return normalized.startswith("gpt-5")


def _is_qwen35_plus_model(model_name: str) -> bool:
    normalized = (model_name or "").strip().lower()
    return normalized == "qwen3.5-plus"


def _is_aimpapi_url(model_url: str) -> bool:
    return False


def _requires_aimp_biz_id(model_url: str, model_name: str) -> bool:
    return _is_aimpapi_url(model_url) and (
        _is_gpt5_model(model_name) or _is_qwen35_plus_model(model_name)
    )


def _is_openrouter_url(model_url: str) -> bool:
    hostname = (urlparse(model_url or "").hostname or "").lower()
    return hostname == "openrouter.ai" or hostname.endswith(".openrouter.ai")
