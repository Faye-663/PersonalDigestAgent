from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid

from personal_digest.domain.exceptions import ConfigurationError
from personal_digest.domain.models import SendResult
from personal_digest.domain.ports import Notifier
from personal_digest.settings import EmailSettings


@dataclass(slots=True)
class SmtpNotifier(Notifier):
    settings: EmailSettings

    def send(self, digest_markdown: str, digest_html: str, recipients: list[str], subject: str) -> SendResult:
        if not recipients:
            raise ConfigurationError("Email recipients are missing.")
        if not self.settings.host:
            raise ConfigurationError("SMTP host is missing.")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.settings.sender
        message["To"] = ", ".join(recipients)
        message["Message-Id"] = make_msgid(domain="personal-digest.local")
        message.set_content(digest_markdown)
        message.add_alternative(digest_html, subtype="html")

        if self.settings.use_ssl:
            with smtplib.SMTP_SSL(self.settings.host, self.settings.port) as client:
                self._send_message(client, message)
        else:
            with smtplib.SMTP(self.settings.host, self.settings.port) as client:
                if self.settings.use_tls:
                    client.starttls()
                self._send_message(client, message)
        return SendResult(recipients=recipients, message_id=message["Message-Id"])

    def _send_message(self, client: smtplib.SMTP, message: EmailMessage) -> None:
        # 单独拆出发送逻辑，方便测试时替换 SMTP 客户端。
        if self.settings.username:
            client.login(self.settings.username, self.settings.password)
        client.send_message(message)

