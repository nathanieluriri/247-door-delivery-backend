"""
Simple SMTP email sender using environment vars.
"""
import os
import smtplib
from email.message import EmailMessage

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") in {"1", "true", "True"}


def send_email(to_email: str, subject: str, body: str) -> bool:
    if not (EMAIL_HOST and EMAIL_USERNAME and EMAIL_PASSWORD):
        return False
    msg = EmailMessage()
    msg["From"] = EMAIL_USERNAME
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=10) as server:
            if EMAIL_USE_TLS:
                server.starttls()
            server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception:
        return False
