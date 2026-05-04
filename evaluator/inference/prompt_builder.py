from __future__ import annotations

from typing import Any, Dict, List, Optional

from .code_home_env import CodeHomeEnvironmentFormatter
from .conversation import ConversationBuilder
from ..core.templates import TemplateLoader


class ToolAwarePromptBuilder:
    def __init__(
        self,
        template_loader: TemplateLoader,
        template_name: str = "assistant_tool_v3.md",
        formatter: Optional[Any] = None,
        conversation_builder: Optional[ConversationBuilder] = None,
        instruction_role: str = "system",
    ) -> None:
        self.template_loader = template_loader
        self.template_name = template_name
        self.formatter = formatter or CodeHomeEnvironmentFormatter()
        self.conversation_builder = conversation_builder or ConversationBuilder()
        self.instruction_role = instruction_role

    def build_messages(
        self,
        engine_data: Dict[str, Any],
        entrance: Optional[str],
        initial_query: str,
        history: Any,
        initial_chat_history: Optional[List[Dict[str, Any]]] = None,
        memory_list: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        template = self.template_loader.load(self.template_name)
        system_prompt = self._render_template(template, engine_data, entrance, memory_list)
        messages: List[Dict[str, str]] = [{"role": self.instruction_role, "content": system_prompt}]
        messages.extend(
            self.conversation_builder.build_messages(
                initial_query=initial_query,
                history=history or [],
                initial_chat_history=initial_chat_history or [],
            )
        )
        return messages

    def _render_template(
        self,
        template: str,
        engine_data: Dict[str, Any],
        entrance: Optional[str],
        memory_list: Optional[List[str]],
    ) -> str:
        rendered = template.replace("{{home_environment}}", self.formatter.format(engine_data, entrance))
        rendered = rendered.replace("{{memory_list}}", self._format_memory(memory_list))
        return rendered

    @staticmethod
    def _format_memory(memory_list: Optional[List[str]]) -> str:
        if not memory_list:
            return "无"
        return "\n".join([f"- {str(item)}" for item in memory_list if item is not None])
