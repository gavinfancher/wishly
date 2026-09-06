"""Clerk webhook → ``users`` sync (PLAN T2.3).

``POST /webhooks/clerk`` receives Svix-signed Clerk events. We verify the
signature, then:

* ``user.created`` / ``user.updated`` → upsert the ``users`` row from the
  event's user object.
* ``user.deleted`` → soft-delete (set ``deleted_at``).

Any other event type is acknowledged with ``200`` and ignored. An invalid or
missing signature returns ``400``.

This keeps Postgres current for the send-time path (the worker), which has no JWT
and cannot call Clerk per send (PLAN §3).
"""

from __future__ import annotations

import json
from typing import Any

import pendulum
from fastapi import APIRouter, Request
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from wishly.api.deps import DBSession
from wishly.api.errors import bad_request
from wishly.api.webhooks.verify import verify_request
from wishly.core.logging import get_logger
from wishly.core.settings import settings
from wishly.db.models import User

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger("wishly.webhooks.clerk")

# ``app.state`` attribute a test may set to override signature verification.
VERIFIER_STATE_ATTR = "clerk_webhook_verifier"


def _primary_email(data: dict[str, Any]) -> str | None:
    """Resolve the user's primary email from a Clerk user object.

    Prefers the address whose id matches ``primary_email_address_id``; falls
    back to the first address present.
    """
    addresses = data.get("email_addresses") or []
    if not isinstance(addresses, list) or not addresses:
        return None
    primary_id = data.get("primary_email_address_id")
    for addr in addresses:
        if isinstance(addr, dict) and addr.get("id") == primary_id:
            email = addr.get("email_address")
            if isinstance(email, str):
                return email
    first = addresses[0]
    if isinstance(first, dict):
        email = first.get("email_address")
        if isinstance(email, str):
            return email
    return None


async def _upsert_user(
    session: AsyncSession,
    *,
    user_id: str,
    email: str,
    first_name: str | None,
    last_name: str | None,
) -> None:
    """Upsert a user from a ``user.created`` / ``user.updated`` event.

    Updates the synced identity fields and clears any prior ``deleted_at`` (a
    re-created Clerk user reactivates the row). Onboarding-owned columns
    (``timezone``, ``send_hour``) are deliberately left untouched.
    """
    insert_stmt = pg_insert(User).values(
        id=user_id,
        email=email,
        first_name=first_name,
        last_name=last_name,
    )
    await session.execute(
        insert_stmt.on_conflict_do_update(
            index_elements=[User.id],
            set_={
                "email": insert_stmt.excluded.email,
                "first_name": insert_stmt.excluded.first_name,
                "last_name": insert_stmt.excluded.last_name,
                "deleted_at": None,
                "updated_at": pendulum.now("UTC"),
            },
        )
    )


async def _soft_delete_user(session: AsyncSession, user_id: str) -> None:
    """Mark a user deleted (``user.deleted`` event). No-op if unknown."""
    user = await session.get(User, user_id)
    if user is not None and user.deleted_at is None:
        user.deleted_at = pendulum.now("UTC")


@router.post("/clerk", status_code=200)
async def clerk_webhook(request: Request, session: DBSession) -> dict[str, str]:
    """Verify and process a Clerk user lifecycle webhook."""
    body, _ = await verify_request(
        request,
        state_attr=VERIFIER_STATE_ATTR,
        secret=settings.clerk_webhook_signing_secret,
    )

    try:
        payload: dict[str, Any] = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise bad_request("Malformed webhook body.") from exc

    event_type = payload.get("type")
    data = payload.get("data")
    if not isinstance(event_type, str) or not isinstance(data, dict):
        raise bad_request("Webhook payload missing 'type' or 'data'.")

    user_id = data.get("id")
    if not isinstance(user_id, str) or not user_id:
        raise bad_request("Webhook user object missing 'id'.")

    if event_type in ("user.created", "user.updated"):
        email = _primary_email(data)
        if email is None:
            raise bad_request("Clerk user has no email address.")
        await _upsert_user(
            session,
            user_id=user_id,
            email=email,
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
        )
        logger.info("clerk webhook upsert", extra={"clerk_user_id": user_id, "type": event_type})
        return {"status": "upserted"}

    if event_type == "user.deleted":
        await _soft_delete_user(session, user_id)
        logger.info("clerk webhook soft-delete", extra={"clerk_user_id": user_id})
        return {"status": "deleted"}

    logger.info("clerk webhook ignored", extra={"type": event_type})
    return {"status": "ignored"}
