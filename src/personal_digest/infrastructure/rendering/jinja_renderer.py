from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from personal_digest.domain.ports import DigestRenderer


@dataclass(slots=True)
class JinjaDigestRenderer(DigestRenderer):
    template_dir: Path
    template_name: str = "digest_email.html.j2"
    environment: Environment = field(init=False)

    def __post_init__(self) -> None:
        self.environment = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render_html(self, markdown_text: str, subject: str) -> str:
        html_content = markdown.markdown(markdown_text, extensions=["fenced_code", "tables"])
        template = self.environment.get_template(self.template_name)
        return template.render(subject=subject, html_content=html_content)
