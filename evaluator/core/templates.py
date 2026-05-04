import os
from typing import Dict


class TemplateLoader:
    def __init__(self, template_dir: str) -> None:
        self.template_dir = template_dir

    def load(self, filename: str) -> str:
        path = os.path.join(self.template_dir, filename)
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()


class TemplateRenderer:
    def render(self, template: str, values: Dict[str, str]) -> str:
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace("{" + key + "}", value)
        return rendered
