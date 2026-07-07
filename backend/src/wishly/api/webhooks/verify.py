"""Svix signature verification shared by the Clerk and Resend webhooks.

Both Clerk and Resend sign webhooks with **Svix**, sending the
``svix-id`` / ``svix-timestamp`` / ``svix-signature`` headers. Verification uses
the raw request **body bytes** (not the parsed JSON) and the endpoint's signing
secret (``whsec_...``).

Testability. The verifier is resolved through :func:`get_webhook_verifier`,
which prefers an override on ``app.state`` so tests can either disable
verification or supply a secret and sign payloads with :class:`svix.webhooks.Webhook`.
"""

from __future__ import annotations

from typing import Protocol

from fastapi import Request
from svix.webhooks import Webhook, WebhookVerificationError

from wishly.api.errors import bad_request

# Header names Svix uses (lower-case; Starlette headers are case-insensitive).
_SVIX_HEADERS = ("svix-id", "svix-timestamp", "svix-signature")


class WebhookVerifier(Protocol):
    """Verifies a raw webhook body+headers, raising on failure."""

    def verify(self, body: bytes, headers: dict[str, str]) -> None: ...


class SvixVerifier:
    """A :class:`WebhookVerifier` backed by a Svix signing secret."""

    def __init__(self, secret: str) -> None:
        self._wh = Webhook(secret)

    def verify(self, body: bytes, headers: dict[str, str]) -> None:
        # ``svix`` raises ``WebhookVerificationError`` on any mismatch; let it
        # propagate to the caller, which maps it to a 400.
        self._wh.verify(body, headers)


def _svix_headers(request: Request) -> dict[str, str]:
    """Extract the Svix headers from the request (missing ones become empty)."""
    return {name: request.headers.get(name, "") for name in _SVIX_HEADERS}


def get_webhook_verifier(request: Request, state_attr: str, secret: str | None) -> WebhookVerifier:
    """Return a verifier, preferring ``app.state.<state_attr>`` if present.

    Args:
        request: the incoming request (for ``app.state`` lookup).
        state_attr: attribute name a test may set on ``app.state`` to override.
        secret: the configured signing secret; if absent and no override exists,
            verification cannot proceed and the request is rejected.
    """
    override: WebhookVerifier | None = getattr(request.app.state, state_attr, None)
    if override is not None:
        return override
    if not secret:
        raise bad_request("Webhook signing secret is not configured.")
    return SvixVerifier(secret)


async def verify_request(
    request: Request, *, state_attr: str, secret: str | None
) -> tuple[bytes, dict[str, str]]:
    """Verify the request signature and return ``(raw_body, svix_headers)``.

    Raises ``400`` on a missing/invalid signature. On success the caller may
    parse ``raw_body`` as JSON.
    """
    body = await request.body()
    headers = _svix_headers(request)
    verifier = get_webhook_verifier(request, state_attr, secret)
    try:
        verifier.verify(body, headers)
    except WebhookVerificationError as exc:
        raise bad_request("Invalid webhook signature.") from exc
    return body, headers
