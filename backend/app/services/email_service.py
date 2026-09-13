"""
Minimal transactional email sender (verification + password reset links).

Uses aiosmtplib directly against SMTP_HOST so this works with any provider
(SES SMTP interface, Postmark, SendGrid SMTP, etc.) without an extra SDK
dependency. In production, SMTP_HOST/USER/PASSWORD come from AWS Secrets
Manager via the same Settings/env interface as everything else.

If SMTP_HOST is not configured (e.g. local dev), emails are logged instead
of sent, so the rest of the auth flow can be exercised without a mail server.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import Settings

logger = logging.getLogger(__name__)


async def _send(settings: Settings, *, to: str, subject: str, html_body: str) -> None:
    if not settings.SMTP_HOST:
        logger.info("Transactional email skipped: SMTP is not configured")
        return

    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content("Please view this email in an HTML-capable client.")
    message.add_alternative(html_body, subtype="html")

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=settings.SMTP_USE_TLS,
    )


async def send_verification_email(settings: Settings, *, to: str, token: str) -> None:
    link = f"{settings.FRONTEND_BASE_URL}/verify-email?token={token}"
    await _send(
        settings,
        to=to,
        subject="Verify your KnowledgeGPT account",
        html_body=(
            f"<p>Welcome to KnowledgeGPT. Please verify your email address:</p>"
            f'<p><a href="{link}">{link}</a></p>'
            f"<p>This link expires in {settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS} hours.</p>"
        ),
    )


async def send_password_reset_email(settings: Settings, *, to: str, token: str) -> None:
    link = f"{settings.FRONTEND_BASE_URL}/reset-password?token={token}"
    await _send(
        settings,
        to=to,
        subject="Reset your KnowledgeGPT password",
        html_body=(
            f"<p>We received a request to reset your password.</p>"
            f'<p><a href="{link}">{link}</a></p>'
            f"<p>If you didn't request this, you can safely ignore this email. "
            f"This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes.</p>"
        ),
    )
