"""
Brevo (ex-Sendinblue) email backend for DécisioBI.

Render's free tier blocks outbound SMTP (ports 25/465/587), so we send emails
through Brevo's HTTPS API (port 443) which is not blocked.
"""

import base64
import logging
from typing import List

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMessage

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoEmailBackend(BaseEmailBackend):
    """Django email backend that sends via the Brevo transactional email API."""

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, "BREVO_API_KEY", "")
        self.from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "")

    def send_messages(self, email_messages: List[EmailMessage]) -> int:
        if not self.api_key:
            if not self.fail_silently:
                raise RuntimeError("BREVO_API_KEY is not configured")
            return 0

        sent = 0
        for message in email_messages:
            try:
                if self._send(message):
                    sent += 1
            except Exception as exc:
                logger.exception("Brevo send failed for %s: %s", message.to, exc)
                if not self.fail_silently:
                    raise
        return sent

    def _send(self, message: EmailMessage) -> bool:
        payload = self._build_payload(message)
        resp = requests.post(
            BREVO_API_URL,
            headers={
                "api-key": self.api_key,
                "accept": "application/json",
                "content-type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        if resp.status_code >= 400:
            logger.error("Brevo API error %s: %s", resp.status_code, resp.text[:500])
            if not self.fail_silently:
                raise RuntimeError(f"Brevo API error {resp.status_code}: {resp.text[:200]}")
            return False
        return True

    def _build_payload(self, message: EmailMessage) -> dict:
        from_email = self.from_email or message.from_email
        sender_name, sender_email = _split_from(from_email)

        recipients = [{"email": addr} for addr in (message.to or [])]

        html = None
        for content, mimetype in message.alternatives or []:
            if mimetype == "text/html":
                html = content

        attachments = []
        for name, content, mimetype in message.attachments or []:
            if isinstance(content, str):
                content = content.encode("utf-8")
            attachments.append({
                "name": name,
                "content": base64.b64encode(content).decode("ascii"),
                "contentType": mimetype or "application/octet-stream",
            })

        payload = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": recipients,
            "subject": message.subject,
            "textContent": message.body or "",
        }
        if html:
            payload["htmlContent"] = html
        if attachments:
            payload["attachment"] = attachments
        return payload


def _split_from(from_email: str):
    """Split 'Name <email@x.com>' into (name, email)."""
    if not from_email:
        return "", ""
    if "<" in from_email and ">" in from_email:
        name = from_email.split("<")[0].strip()
        email = from_email.split("<")[1].split(">")[0].strip()
        return name, email
    return "", from_email.strip()
