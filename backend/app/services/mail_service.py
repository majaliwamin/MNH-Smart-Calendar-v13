"""Small SMTP sender used for CRARA account-recovery links.

Delivery is configured entirely through environment variables so credentials
never enter source control. No mail is sent unless a host and from address are
configured; callers decide how to surface that condition to the user.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


class MailError(RuntimeError):
    """Raised when SMTP delivery is unavailable or fails."""


def _setting(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def configured() -> bool:
    return bool(_setting("MNH_SMTP_HOST") and _setting("MNH_SMTP_FROM"))


def status() -> dict:
    """Safe capability check: never returns credentials."""
    return {
        "configured": configured(),
        "host_set": bool(_setting("MNH_SMTP_HOST")),
        "from_set": bool(_setting("MNH_SMTP_FROM")),
        "user_set": bool(_setting("MNH_SMTP_USER")),
    }


def send_text(to: str, subject: str, body: str) -> None:
    """Send a plain-text message via the configured SMTP server."""
    host = _setting("MNH_SMTP_HOST")
    sender = _setting("MNH_SMTP_FROM")
    if not host or not sender:
        raise MailError("Email delivery is not configured.")
    recipient = str(to or "").strip()
    if "@" not in recipient:
        raise MailError("A valid recipient email address is required.")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = str(subject or "").replace("\r", " ").replace("\n", " ")[:200]
    message.set_content(str(body or ""))

    port_raw = _setting("MNH_SMTP_PORT", "587")
    try:
        port = int(port_raw or 587)
    except ValueError:
        port = 587
    security = _setting("MNH_SMTP_SECURITY", "starttls").lower()
    timeout = 10
    context = ssl.create_default_context()

    try:
        if security == "ssl":
            client = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
        else:
            client = smtplib.SMTP(host, port, timeout=timeout)
            if security != "none":
                client.starttls(context=context)
        try:
            user = _setting("MNH_SMTP_USER")
            password = os.getenv("MNH_SMTP_PASSWORD", "")
            if user and password:
                client.login(user, password)
            client.send_message(message)
        finally:
            try:
                client.quit()
            except Exception:  # pragma: no cover - connection already gone
                pass
    except MailError:
        raise
    except Exception as exc:
        raise MailError("The reset email could not be sent.") from exc
