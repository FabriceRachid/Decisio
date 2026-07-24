"""
Notification service for DécisioBI.
Handles email, webhook, and in-app notification delivery.
"""

import json
import logging
from typing import List, Optional

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications through various channels."""

    def __init__(self, user: User):
        self.user = user

    def send_email_notification(
        self,
        recipients: List[str],
        subject: str,
        message: str,
        html_message: Optional[str] = None,
    ) -> bool:
        """Send email notification."""
        try:
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@decisiobi.local')
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipients,
                html_message=html_message or self._build_html_email(subject, message),
                fail_silently=False,
            )
            logger.info(f"Email sent to {recipients}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_webhook_notification(
        self,
        url: str,
        payload: dict,
        headers: Optional[dict] = None,
    ) -> bool:
        """Send webhook notification (POST JSON)."""
        try:
            default_headers = {"Content-Type": "application/json"}
            if headers:
                default_headers.update(headers)

            response = requests.post(
                url,
                data=json.dumps(payload, default=str),
                headers=default_headers,
                timeout=10,
            )
            response.raise_for_status()
            logger.info(f"Webhook sent to {url}: {response.status_code}")
            return True
        except Exception as e:
            logger.error(f"Failed to send webhook to {url}: {e}")
            return False

    def _build_html_email(self, subject: str, message: str) -> str:
        """Build a simple HTML email body."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; color: #1a1a1a;">
            <div style="max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #d4a843, #1a3a5c); padding: 24px; border-radius: 12px 12px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 20px;">DécisioBI</h1>
                </div>
                <div style="background: #f9fafb; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                    <h2 style="margin: 0 0 16px 0; font-size: 16px;">{subject}</h2>
                    <div style="white-space: pre-wrap; line-height: 1.6; font-size: 14px;">{message}</div>
                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
                    <p style="color: #6b7280; font-size: 12px; margin: 0;">
                        Ce message a été envoyé par DécisioBI. Ne répondez pas à cet email.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
