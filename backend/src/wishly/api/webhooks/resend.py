"""Resend inbound webhook → ``suppressions`` (PLAN T4.4).

``POST /webhooks/resend`` receives Svix-signed Resend events. On a
``email.bounced`` or ``email.complained`` event we upsert the recipient
address(es) into ``suppressions`` so the sender (Epic 5) skips them.

This handler is **inbound only**: it never sends email and does not import from
``wishly.email``. An invalid/missing signature returns ``400``.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request

from wishly.api import crud
from wishly.api.deps import DBSession
from wishly.api.errors import bad_request
from wishly.api.webhooks.verify import verify_request
from wishly.core.logging import get_logger
from wishly.core.settings import settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger("wishly.webhooks.resend")

# ``app.state`` attribute a test may set to override signature verification.
VERIFIER_STATE_ATTR = "resend_webhook_verifier"

# Resend event types we act on, mapped to the stored suppression ``reason``.
_BOUNCE_TYPES = {"email.bounced": "bounce", "email.complained": "complaint"}


def _recipients(data: dict[str, Any]) -> list[str]:
    """Extract recipient address(es) from a Resend event ``data`` object.

    Resend places recipients under ``to`` (string or list). We also accept a
    bare ``email`` field defensively.
    """
    out: list[str] = []
    to = data.get("to")
    if isinstance(to, str):
        out.append(to)
    elif isinstance(to, list):
        out.extend(addr for addr in to if isinstance(addr, str))
    email = data.get("email")
    if isinstance(email, str):
        out.append(email)
    # De-dupe while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for addr in out:
        if addr and addr not in seen:
            seen.add(addr)
            unique.append(addr)
    return unique


@router.post("/resend", status_code=200)
async def resend_webhook(request: Request, session: DBSession) -> dict[str, Any]:
    """Verify and process a Resend delivery-event webhook."""
    body, _ = await verify_request(
        request,
        state_attr=VERIFIER_STATE_ATTR,
        secret=settings.resend_webhook_signing_secret,
    )

    try:
        payload: dict[str, Any] = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise bad_request("Malformed webhook body.") from exc

    event_type = payload.get("type")
    data = payload.get("data")
    if not isinstance(event_type, str) or not isinstance(data, dict):
        raise bad_request("Webhook payload missing 'type' or 'data'.")

    reason = _BOUNCE_TYPES.get(event_type)
    if reason is None:
        # Delivered/opened/clicked/etc. — acknowledge and ignore.
        logger.info("resend webhook ignored", extra={"type": event_type})
        return {"status": "ignored"}

    recipients = _recipients(data)
    if not recipients:
        raise bad_request("Resend event has no recipient address.")

    for email in recipients:
        await crud.upsert_suppression(session, email=email, reason=reason)
    logger.info(
        "resend suppression upsert",
        extra={"type": event_type, "reason": reason, "count": len(recipients)},
    )
    return {"status": "suppressed", "reason": reason, "count": len(recipients)}
