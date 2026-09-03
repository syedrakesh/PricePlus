"""
Email sender for alert notifications.

Uses Python's built-in smtplib with async wrapping via asyncio.run_in_executor
so it doesn't block the event loop.

For MVP: sends plain-text emails. HTML templates can be added later.
"""

import asyncio
import logging
import smtplib
from email.mime.text import MIMEText

from sqlalchemy import select

logger = logging.getLogger(__name__)


async def send_alert_email(
    to_user_id: str,
    subject: str,
    body: str,
) -> None:
    """
    Send a plain-text alert email to the user identified by to_user_id.

    Fetches the user's email address from the DB then sends via SMTP.
    Runs SMTP in a thread pool to avoid blocking the event loop.
    """
    from app.core.config import get_settings
    from app.core.db import AsyncSessionLocal
    from app.modules.auth.models import User

    settings = get_settings()

    # Fetch user email
    async with AsyncSessionLocal() as db:
        import uuid
        result = await db.execute(
            select(User.email).where(User.id == uuid.UUID(to_user_id))
        )
        email = result.scalar_one_or_none()

    if not email:
        logger.warning("Cannot send alert email: user %s not found", to_user_id)
        return

    # Build message
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = email

    # Send in executor (SMTP is blocking)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: _send_smtp(settings, email, msg.as_string()),
    )
    logger.info("Alert email sent to %s", email)


def _send_smtp(settings: object, to_email: str, message: str) -> None:
    """Synchronous SMTP send — runs in a thread pool."""
    from app.core.config import Settings
    assert isinstance(settings, Settings)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.ehlo()
        if settings.smtp_port == 587:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(settings.smtp_from_email, to_email, message)
