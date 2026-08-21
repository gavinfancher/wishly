"""Current-user routes: ``GET /me``, ``PATCH /me``, and ``POST /me/test-email``."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException, status
from starlette.concurrency import run_in_threadpool

from wishly.api import crud
from wishly.api.deps import CurrentUser, DBSession
from wishly.api.errors import not_found
from wishly.api.schemas import UserOut, UserUpdate
from wishly.core.logging import get_logger
from wishly.email.render import build_manage_url, render_email
from wishly.email.resend_client import EmailSendError, ResendClient

logger = get_logger("wishly.api.me")

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserOut)
async def get_me(principal: CurrentUser, session: DBSession) -> UserOut:
    """Return the current user, creating the row on first authenticated request.

    The Clerk session token is the source of identity (PLAN §10). If this
    ``sub`` has never been seen we insert a ``users`` row from the JWT claims —
    a fallback for a missed/raced Clerk webhook (PLAN §2).
    """
    user = await crud.provision_user(session, principal)
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_me(body: UserUpdate, principal: CurrentUser, session: DBSession) -> UserOut:
    """Update onboarding preferences (``timezone`` and/or ``send_hour``)."""
    # Ensure the row exists even if ``PATCH /me`` is somehow the first call.
    user = await crud.provision_user(session, principal)
    if user is None:  # pragma: no cover — provision_user always returns a row
        raise not_found("User not found.")

    if body.timezone is not None:
        user.timezone = body.timezone
    if body.send_hour is not None:
        user.send_hour = body.send_hour
    # Stamp once and never move it: this records *when* onboarding was finished,
    # so re-saving preferences later must not rewrite it.
    if body.onboarded and user.onboarded_at is None:
        user.onboarded_at = dt.datetime.now(dt.UTC)

    await session.flush()
    # Refresh so server-side ``onupdate`` columns (``updated_at``) are loaded before
    # Pydantic reads attributes — otherwise async SQLAlchemy raises MissingGreenlet.
    await session.refresh(user)

    logger.info(
        "preferences updated",
        extra={
            "user_id": user.id,
            "timezone": user.timezone,
            "send_hour": user.send_hour,
            "onboarding_completed": bool(body.onboarded),
        },
    )
    return UserOut.model_validate(user)


@router.post("/me/test-email", status_code=status.HTTP_202_ACCEPTED)
async def send_test_email(principal: CurrentUser, session: DBSession) -> dict[str, str]:
    """Send the current user a sample reminder so they can check deliverability.

    This deliberately does **not** touch ``notification_log``: that table is the
    idempotency ledger for real sends (PLAN §7), and writing a synthetic row would
    let a test suppress a genuine reminder for the same occurrence.

    ``ResendClient`` is blocking, so it runs in a threadpool rather than stalling
    the event loop for the duration of the API call.
    """
    user = await crud.provision_user(session, principal)

    rendered = render_email(
        event_type="birthday",
        recipient_name=user.first_name or "there",
        title="A test reminder",
        days_before=7,
        occurrence_date=dt.date.today() + dt.timedelta(days=7),
        manage_url=build_manage_url(user.id),
        message="This is a test from Wishly — your reminder emails will look like this.",
    )

    try:
        resend_id = await run_in_threadpool(
            ResendClient().send_email,
            to=user.email,
            subject=rendered.subject,
            html=rendered.html,
            text=rendered.text,
        )
    except EmailSendError:
        logger.exception("test email failed", extra={"user_id": user.id})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send the test email.",
        ) from None

    logger.info("test email sent", extra={"user_id": user.id, "resend_id": resend_id})
    return {"status": "sent"}
