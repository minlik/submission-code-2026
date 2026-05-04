from typing import Any, Dict, List, Optional, Tuple


class ConversationBuilder:
    def build(
        self,
        initial_query: str,
        history: List[Dict[str, Any]],
        initial_chat_history: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Tuple[str, str]]:
        messages: List[Tuple[str, str]] = []
        for turn in (initial_chat_history or []):
            self._append_turn(messages, turn)
        if initial_query:
            messages.append(("user", initial_query))
        for turn in history:
            self._append_turn(messages, turn)
        return messages

    def _append_turn(self, messages: List[Tuple[str, str]], turn: Dict[str, Any]) -> None:
        role = turn.get("role")
        content = turn.get("content")
        if role == "assistant":
            if isinstance(content, dict):
                mode = content.get("mode")
                if mode in {"clarification", "execution"}:
                    messages.append(("assistant", str(content.get("response") or "")))
                return
            if content is not None:
                messages.append(("assistant", str(content)))
            return
        if role == "user":
            if isinstance(content, str):
                messages.append(("user", content))
            elif content is not None:
                messages.append(("user", str(content)))

    def format(self, messages: List[Tuple[str, str]]) -> str:
        return "\n".join([f"{role}: {content}" for role, content in messages if content is not None])

    def build_messages(
        self,
        initial_query: str,
        history: List[Dict[str, Any]],
        initial_chat_history: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, str]]:
        conversation = self.build(
            initial_query=initial_query,
            history=history,
            initial_chat_history=initial_chat_history,
        )
        return [
            {"role": role, "content": content}
            for role, content in conversation
            if content is not None
        ]
