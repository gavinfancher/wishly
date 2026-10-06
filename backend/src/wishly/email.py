"""Sending email. Plain text through Resend's HTTP API."""

import httpx2

from wishly.settings import Settings


def send_via_resend(
    settings: Settings, *, to: str, subject: str, text: str, idempotency_key: str
) -> None:
    response = httpx2.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
            # If we retry a send that actually went through (say the response
            # timed out), Resend sees the same key and doesn't send it again.
            "Idempotency-Key": idempotency_key,
        },
        json={"from": settings.email_from, "to": [to], "subject": subject, "text": text},
        timeout=10,
    )
    response.raise_for_status()


def print_email(*, to: str, subject: str, text: str, idempotency_key: str) -> None:
    """Stand-in for local development, when no Resend key is configured."""
    print(f"--- email to {to} ---\nSubject: {subject}\n\n{text}\n")
