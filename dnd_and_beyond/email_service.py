"""Email verification delivery.

Local development writes verification messages to a text outbox. Production can
use SMTP by setting the SMTP_* environment variables.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

from dnd_and_beyond.data_access import DB_PATH


OUTBOX_PATH = DB_PATH.parent / "dev_email_outbox.log"


def send_verification_email(email: str, token: str) -> str:
    app_base_url = os.getenv("APP_BASE_URL", "http://localhost:3000").rstrip("/")
    verify_url = f"{app_base_url}/?verify_token={token}"
    subject = "Verify your DND and Beyond account"
    body = (
        "Welcome to DND and Beyond.\n\n"
        "Use this verification code in the app:\n\n"
        f"{token}\n\n"
        f"Verification link: {verify_url}\n\n"
        "If you did not create this account, you can ignore this email."
    )

    smtp_host = os.getenv("SMTP_HOST", "").strip()
    if smtp_host:
        _send_smtp(email, subject, body)
        return "smtp"

    OUTBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTBOX_PATH.open("a", encoding="utf-8") as outbox:
        outbox.write(f"TO: {email}\nSUBJECT: {subject}\n{body}\n{'-' * 72}\n")
    return str(OUTBOX_PATH)


def _send_smtp(email: str, subject: str, body: str) -> None:
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "noreply@dnd-and-beyond.local")

    message = EmailMessage()
    message["From"] = smtp_from
    message["To"] = email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        server.starttls()
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
        server.send_message(message)
