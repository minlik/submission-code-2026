from typing import Any, Dict, List, Optional

from .conversation import ConversationBuilder
from .home_env import HomeEnvironmentFormatter
from ..core.templates import TemplateLoader


class AssistantPromptBuilder:
    def __init__(
        self,
        template_loader: TemplateLoader,
        template_name: str = "assistant.md",
        formatter: Optional[HomeEnvironmentFormatter] = None,
        conversation_builder: Optional[ConversationBuilder] = None,
    ) -> None:
        self.template_loader = template_loader
        self.template_name = template_name
        self.formatter = formatter or HomeEnvironmentFormatter()
        self.conversation_builder = conversation_builder or ConversationBuilder()

    def build(
        self,
        engine_data: Dict[str, Any],
        entrance: Optional[str],
        initial_query: str,
        history: Any,
        initial_chat_history: Optional[List[Dict[str, Any]]] = None,
        memory_list: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        template = self.template_loader.load(self.template_name)
        home_env = self.formatter.format(engine_data, entrance)
        system_prompt = template.replace("{{home_environment}}", home_env)
        memory_text = self._format_memory(memory_list)
        system_prompt = system_prompt.replace("{{memory_list}}", memory_text)
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend(
            self.conversation_builder.build_messages(
                initial_query=initial_query,
                history=history or [],
                initial_chat_history=initial_chat_history or [],
            )
        )
        return messages

    @staticmethod
    def _format_memory(memory_list: Optional[List[str]]) -> str:
        if not memory_list:
            return "无"
        return "\n".join([f"- {str(item)}" for item in memory_list if item is not None])
