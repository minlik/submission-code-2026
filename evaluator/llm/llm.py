import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict

from utils.llm_util import LLMClient
from utils.data_util import extract_json


@dataclass
class LLMResponse:
    content: Any
    reasoning_content: Any = None
    raw_message: Any = None
    tool_calls: Any = None
    token_usage: Any = None


class LLMRunner:
    async def generate(self, prompt: str, is_json_output: bool = True) -> LLMResponse:
        raise NotImplementedError

    async def generate_chat(
        self,
        messages: Any,
        is_json_output: bool = False,
        tools: Any = None,
        tool_choice: Any = None,
        parallel_tool_calls: Any = None,
    ) -> LLMResponse:
        raise NotImplementedError


class LLMClientRunner(LLMRunner):
    def __init__(
        self,
        model_url: str,
        api_key: str,
        model_name: str,
        temperature: float = 0,
        **kwargs: Any,
    ) -> None:
        self._client = LLMClient(
            model_url=model_url,
            api_key=api_key,
            model_name=model_name,
            temperature=temperature,
            **kwargs,
        )

    async def generate(self, prompt: str, is_json_output: bool = True) -> LLMResponse:
        import aiohttp

        async with aiohttp.ClientSession(trust_env=True) as session:
            output = await self._client.get_response(
                session=session,
                prompt=prompt,
                messages=None,
                is_json_output=is_json_output,
            )
        return LLMResponse(content=output.content, token_usage=output.token_usage)

    async def generate_chat(
        self,
        messages: Any,
        is_json_output: bool = False,
        tools: Any = None,
        tool_choice: Any = None,
        parallel_tool_calls: Any = None,
    ) -> LLMResponse:
        import aiohttp

        async with aiohttp.ClientSession(trust_env=True) as session:
            output = await self._client.get_response(
                session=session,
                prompt=None,
                messages=messages,
                is_json_output=is_json_output,
                tools=tools,
                tool_choice=tool_choice,
                parallel_tool_calls=parallel_tool_calls,
            )
        return LLMResponse(
            content=output.content,
            reasoning_content=output.reasoning_content,
            raw_message=output.raw_message,
            tool_calls=output.tool_calls,
            token_usage=output.token_usage,
        )


class JsonResponseParser:
    def __init__(self) -> None:
        self.required_keys = ("passed", "reason")

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
            try:
                parsed = json.loads(extract_json(text))
            except (ValueError, json.JSONDecodeError):
                raise ValueError("invalid JSON response")
        if not isinstance(parsed, dict):
            raise ValueError("response must be a JSON object")
        return parsed

    def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        for key in self.required_keys:
            if key not in payload:
                raise ValueError(f"missing key: {key}")
        if not isinstance(payload.get("passed"), bool):
            raise ValueError("passed must be boolean")
        if not isinstance(payload.get("reason"), str):
            raise ValueError("reason must be string")
        return payload

def run_async(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("async loop already running")
